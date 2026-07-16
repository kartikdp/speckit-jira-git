<!-- speckit-jira-git:start -->
## speckit-jira-git

Use the installed `speckit-jira-git` skill for all Jira, Spec Kit-to-Jira, and
linked GitHub PR or review activity. This is mandatory: load the skill's
`SKILL.md` before running commands or writing to Jira or GitHub.

Resolve the skill through the agent's skill catalog first. If it is not exposed
there, check the project-vendored copies at
`.claude/skills/speckit-jira-git/SKILL.md` and
`.agents/skills/speckit-jira-git/SKILL.md`. Resolve the CLI from `PATH` or from
`bin/speckit-jira-git.js` relative to the loaded skill root; do not hardcode an
external, agent-specific installation directory.

Resolve project-vendored paths from the repository containing the canonical
`CLAUDE.md` and `AGENTS.md`, not from the process working directory. When an
agent starts in a parent workspace, locate the nested repository containing
those canonical files first. Workspace-root instruction files MUST point to
the canonical files and skill roots; do not copy the full instructions or
skill tree into the parent workspace.

If the skill file or CLI cannot be found or read, stop before any Jira or
GitHub write and clearly tell the user:

> The required `speckit-jira-git` skill was not found or could not be loaded.
> Please check the project structure and ensure the skill is installed in a
> supported project or agent skill directory.

Include the paths or command locations that were checked. Do not silently fall
back to direct Jira REST calls, generic Jira tools, `gh` mutations, or manual
payload construction.

Before creating or updating a pull request, read the applicable template under
`.github/`: the default `PULL_REQUEST_TEMPLATE.md`, or the dedicated hotfix or
release template. Preserve its section structure and fill every applicable
section with observed information; do not replace it with an ad hoc body.
Validate the PR title against the canonical shape in `CLAUDE.md` and
`AGENTS.md`; `feat` and `fix` titles require both the Jira key and WBS code. If
either required identifier is unavailable, ask the user instead of opening or
renaming the PR with a partial title.

Detect the Jira key from the branch, commits, PR title, or PR body. If no key is available, request it before writing to Jira. Run `--dry-run` first whenever the target issue, PR, review area, or activity content is uncertain.

Create Spec Kit Jira work in this order:

1. Specs Generation
2. Specs Review
3. Clarification Round(s)
4. Implementation Phase(s)
5. Code Review Round(s)
6. PR Review(s)

Use the CLI-generated stage-coded titles. Do not infer Jira transitions from checked source tasks, parent status, commits, CI, or PR state. Transition only when an explicit target status is requested.

Keep attribution and assignment separate. `review-to-jira --reviewer` identifies the actual human reviewer. PR Review tasks remain unassigned unless a human reviewer is explicitly supplied with `standard-tasks --pr-reviewer`. Configure reusable names in `.speckit-jira-git.toml`; never bake personal identities into shared instructions.

For Specs Review, attach the complete review packet with repeatable `--spec-file` arguments, including `spec.md`, `plan.md`, `tasks.md`, and available supporting research, data model, quickstart, checklist, and contracts.

After every successful push containing commits, verify the remote SHA and open PR. Post one structured PR conversation update containing all pushed commit SHAs, changes, truthful validation, observed CI/merge state, and remaining work, then synchronize it to Jira:

```bash
speckit-jira-git pr-to-jira --pr-url <PR_URL> --event updated \
  --commit <PUSHED_SHA> \
  --change "<change>" \
  --validation "passed|<check>|<observed result>" \
  --remaining "<remaining work or None>" \
  --post-github
```

Synchronize review activity with structured findings and actual reviewer attribution:

```bash
speckit-jira-git review-to-jira --pr-url <PR_URL> \
  --status <approved|changes_requested|commented|review_requested> \
  --reviewer "<human reviewer>" --round <N> --area <area> \
  --finding "P2|<summary>|<path>|<line>|<impact>|<required action>" \
  --validation "passed|<check>|<observed result>"
```

Never include secrets or claim checks, approvals, comments, or CI results that were not observed.
<!-- speckit-jira-git:end -->
