"""Install repo-local agent instructions for speckit-jira-git."""
from __future__ import annotations

import argparse
from pathlib import Path


START = "<!-- speckit-jira-git:start -->"
END = "<!-- speckit-jira-git:end -->"

BLOCK = f"""{START}
## speckit-jira-git

When creating, updating, reviewing, approving, requesting changes on, closing, or merging a pull request, always use the `speckit-jira-git` skill/CLI to add a Jira comment to the linked issue.

Detect the Jira key from the branch name, commit messages, PR title, or PR body. If no key is found, ask for it before continuing.

Before running commands, resolve `<SPECKIT_JIRA_GIT>` for the current machine:

- Prefer `speckit-jira-git` if it is installed on `PATH`.
- If this repo vendors the package, use its repo-relative CLI path, for example `node .agents/speckit-jira-git/bin/speckit-jira-git.js`.
- If the agent has installed this as a skill, use the local skill/package source path exposed by that agent.
- Use `npx github:kartikdp/speckit-jira-git ...` only to install, bootstrap, or refresh the tool. Do not use GitHub `npx` for every routine PR/comment sync.

Use this for PR activity:

```bash
<SPECKIT_JIRA_GIT> pr-to-jira --pr-url <PR_URL> --event <opened|ready|updated|closed|merged>
```

Use this for review activity:

```bash
<SPECKIT_JIRA_GIT> review-to-jira --pr-url <PR_URL> --status <approved|changes_requested|commented|review_requested> --reviewer "<name>" --round <N> --area <frontend|backend|fullstack|general> --summary "<summary>"
```

Run with `--dry-run` first when the PR URL, Jira issue key, review area, or summary is uncertain.
{END}
"""

TARGETS = {
    "agents": Path("AGENTS.md"),
    "claude": Path("CLAUDE.md"),
    "cursor": Path(".cursor/rules/speckit-jira-git.mdc"),
    "windsurf": Path(".windsurf/rules/speckit-jira-git.md"),
}


def _upsert(path: Path, block: str, dry_run: bool = False) -> str:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if START in original and END in original:
        before = original.split(START, 1)[0].rstrip()
        after = original.split(END, 1)[1].lstrip()
        updated = f"{before}\n\n{block.rstrip()}\n"
        if after:
            updated += f"\n{after}"
        action = "updated"
    else:
        separator = "\n\n" if original.strip() else ""
        updated = f"{original.rstrip()}{separator}{block.rstrip()}\n"
        action = "created" if not path.exists() else "appended"
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
    return action


def main() -> None:
    parser = argparse.ArgumentParser(description="Install speckit-jira-git instructions into repo agent files")
    parser.add_argument(
        "--target",
        choices=sorted(TARGETS),
        action="append",
        help="Target to update. Can be passed multiple times. Defaults to agents.",
    )
    parser.add_argument("--all", action="store_true", help="Update AGENTS.md, CLAUDE.md, Cursor, and Windsurf files")
    parser.add_argument("--dry-run", action="store_true", help="Print planned changes without writing")
    args = parser.parse_args()

    targets = sorted(TARGETS) if args.all else (args.target or ["agents"])
    for target in targets:
        path = TARGETS[target]
        action = _upsert(path, BLOCK, dry_run=args.dry_run)
        suffix = " (dry-run)" if args.dry_run else ""
        print(f"{action}{suffix}: {path}")


if __name__ == "__main__":
    main()
