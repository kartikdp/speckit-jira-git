# speckit-jira-git

Portable Agent Skill and CLI for Spec Kit, Jira, and GitHub workflows.

This repository is distributed as a public skill source package. You may use,
fork, and adapt it under the Apache-2.0 license while preserving the copyright,
license, and notice attribution to the original author. If published to npm,
the package should use the owner-scoped name `@kartikdp/speckit-jira-git`.

Use it for:

- **Setup**: check Jira/GitHub access and show the credentials file to update.
- **Plan to Jira**: add stories, tasks, sub-tasks, and standard review tasks from Spec Kit.
- **Git ↔ Jira sync**: post GitHub PR/review status back to the linked Jira story.
- **Time logging**: check, add, update, and report Jira logged hours.
- **Jira maintenance**: add comments, move issues, update estimates, and inspect project metadata.

## Install As An Agent Skill

Install with the open Agent Skills CLI:

```bash
npx skills add kartikdp/speckit-jira-git
```

Install globally for supported agents:

```bash
npx skills add kartikdp/speckit-jira-git -g
```

Install for specific agents:

```bash
npx skills add kartikdp/speckit-jira-git -a codex -a claude-code
```

## Run The CLI

For routine usage, prefer an installed or vendored CLI:

```bash
speckit-jira-git setup-check
```

If the repo vendors this package, use its repo-relative path:

```bash
node .agents/speckit-jira-git/bin/speckit-jira-git.js setup-check
```

Run directly from GitHub only for bootstrap, refresh, or one-off testing:

```bash
npx github:kartikdp/speckit-jira-git setup-check
```

If installed from npm later:

```bash
npx @kartikdp/speckit-jira-git setup-check
```

Workflow examples:

```bash
speckit-jira-git setup-check
speckit-jira-git standard-tasks --parent PROJ-123 --kinds specs-generation,specs-review,pr-review --dry-run
speckit-jira-git pr-to-jira --pr-url https://github.com/org/repo/pull/123 --event opened --dry-run
speckit-jira-git review-to-jira --pr-url https://github.com/org/repo/pull/123 --status approved --reviewer "Reviewer" --dry-run
speckit-jira-git time-report --from 2026-07-01 --to 2026-07-15 --csv exports/time.csv --markdown exports/time.md
```

PR-to-Jira comments include a monospaced ASCII status card showing source branch, PR number, target branch, draft state, merge state, and last update time.

## Credentials

Create a Jira API token at `https://id.atlassian.com/manage-profile/security/api-tokens`.

For agent workflows, store credentials in a file. Do not rely on `export ...` from another terminal; those variables are not visible to already-running agents or separate shell sessions.

Preferred locations:

1. Existing project `.env`, when the repo already uses one and it is gitignored.
2. `~/.jira/credentials.env`, for machine-wide Jira credentials.

Run `speckit-jira-git setup-check` and use `recommended_credentials_file` / `dotenv_candidates` from the output to tell the user exactly which file to edit.

File content:

```text
JIRA_URL=https://your-tenant.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_TOKEN=...
JIRA_PROJECT=PROJ
GITHUB_TOKEN=
```

`GITHUB_TOKEN` is optional. If absent, GitHub commands use `gh auth token`.

Inline environment variables, such as `JIRA_TOKEN=... speckit-jira-git setup-check`, are useful only for one-off debugging in the same command.

Never commit real credentials.

## Verify

```bash
speckit-jira-git setup-check
```

## Add Repo Instructions

Skill installation does not silently edit your project files. To opt in to automatic agent behavior for PR/review activity, run:

```bash
speckit-jira-git install-instructions
```

By default this updates `AGENTS.md`. Other targets:

```bash
speckit-jira-git install-instructions --target claude
speckit-jira-git install-instructions --target cursor
speckit-jira-git install-instructions --target windsurf
speckit-jira-git install-instructions --all
```

The command writes a marked block:

```text
<!-- speckit-jira-git:start -->
...
<!-- speckit-jira-git:end -->
```

Rerunning the command updates that block instead of duplicating it.

## Repository Use

For tools that do not support Agent Skills directly, clone or vendor this repo and point the agent to:

- `AGENTS.md` for generic coding agents, Cursor, Windsurf, Cascade, Devin.
- `CLAUDE.md` for Claude Code project instructions.
- `SKILL.md` for Codex/Claude-style skill loaders.

## Use Case Map

```text
setup
  setup-check, install-instructions

plan-to-jira
  find-parent, standard-tasks, generate-subtasks, push-subtasks

sync-git-jira
  find-jira-key, pr-to-jira, review-to-jira

time-logging
  log-worklog, update-worklog, time-report

jira-maintenance
  add-comment, transition, update-estimate, discover-project
```

Run `speckit-jira-git <command> --help` for command-specific options.
