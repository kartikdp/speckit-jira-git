"""Install a portable, repo-local speckit-jira-git policy."""
from __future__ import annotations

import argparse
from pathlib import Path


START = "<!-- speckit-jira-git:start -->"
END = "<!-- speckit-jira-git:end -->"
SKILL_ROOT = Path(__file__).resolve().parents[1]
POLICY_TEMPLATE = SKILL_ROOT / "assets" / "templates" / "consumer-policy.md"


def _policy() -> str:
    return POLICY_TEMPLATE.read_text(encoding="utf-8").strip()


def _upsert(path: Path, block: str, dry_run: bool = False) -> str:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if START in original and END in original:
        before = original.split(START, 1)[0].rstrip()
        after = original.split(END, 1)[1].lstrip()
        prefix = f"{before}\n\n" if before else ""
        updated = f"{prefix}{block.rstrip()}\n"
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


def _ensure_claude_import(path: Path, dry_run: bool = False) -> str:
    import_line = "@AGENTS.md"
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    if any(line.strip() == import_line for line in original.splitlines()):
        return "unchanged"
    updated = f"{original.rstrip()}\n\n{import_line}\n" if original.strip() else f"{import_line}\n"
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(updated, encoding="utf-8")
    return "created" if not path.exists() else "appended"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Install portable speckit-jira-git policy into repository instructions"
    )
    parser.add_argument(
        "--target",
        choices=("agents", "claude"),
        action="append",
        help="Instruction target; repeatable. Defaults to AGENTS.md.",
    )
    parser.add_argument(
        "--target-file",
        action="append",
        default=[],
        help="Additional instruction file receiving the marked policy block; repeatable.",
    )
    parser.add_argument("--all", action="store_true", help="Update AGENTS.md and ensure CLAUDE.md imports it")
    parser.add_argument("--dry-run", action="store_true", help="Report planned changes without writing")
    args = parser.parse_args()

    targets = ["agents", "claude"] if args.all else (args.target or ["agents"])
    seen: set[Path] = set()
    for target in targets:
        path = Path("AGENTS.md") if target == "agents" else Path("CLAUDE.md")
        if path in seen:
            continue
        seen.add(path)
        action = (
            _upsert(path, _policy(), dry_run=args.dry_run)
            if target == "agents"
            else _ensure_claude_import(path, dry_run=args.dry_run)
        )
        suffix = " (dry-run)" if args.dry_run else ""
        print(f"{action}{suffix}: {path}")

    for raw_path in args.target_file:
        path = Path(raw_path)
        if path in seen:
            continue
        seen.add(path)
        action = _upsert(path, _policy(), dry_run=args.dry_run)
        suffix = " (dry-run)" if args.dry_run else ""
        print(f"{action}{suffix}: {path}")


if __name__ == "__main__":
    main()
