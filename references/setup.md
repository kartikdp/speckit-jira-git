# Setup

## Required Jira credentials

Create an Atlassian API token at `https://id.atlassian.com/manage-profile/security/api-tokens`.

For agent workflows, store credentials in a file. Do not rely on `export ...` from another terminal; those variables are not visible to already-running agents or separate shell sessions.

Preferred locations:

1. Existing project `.env`, when the repo already uses one and it is gitignored.
2. `~/.jira/credentials.env`, for machine-wide Jira credentials.

Run setup validation and use `recommended_credentials_file` / `dotenv_candidates` from the output to tell the user exactly which file to edit.

Required:

```text
JIRA_URL
JIRA_EMAIL
JIRA_TOKEN
JIRA_PROJECT
```

Optional:

```text
GITHUB_TOKEN
```

If `GITHUB_TOKEN` is absent, GitHub scripts call `gh auth token`.

Inline environment variables, such as `JIRA_TOKEN=... speckit-jira-git setup-check`, are useful only for one-off debugging in the same command.

## Validate

```bash
python3 scripts/setup_check.py
```

The setup checker masks tokens, calls Jira `myself`, and checks GitHub CLI/token availability.

## Install for agents

Preferred install:

```bash
npx skills add kartikdp/speckit-jira-git
```

Global install:

```bash
npx skills add kartikdp/speckit-jira-git -g
```

Run without installing:

```bash
speckit-jira-git setup-check
```

Add project instructions after installing:

```bash
speckit-jira-git install-instructions
```

This updates `AGENTS.md` by default. Use `--target claude`, `--target cursor`, `--target windsurf`, or `--all` for other agent instruction files. The command is idempotent because it writes between `speckit-jira-git:start` and `speckit-jira-git:end` markers.

Use the same package for all agents:

- Codex/Claude skill: install or upload this folder with `SKILL.md`.
- Repo agents: copy this folder under `.agents/speckit-jira-git` and reference `AGENTS.md`.
- Claude Code: reference `CLAUDE.md`.
- Cursor/Windsurf: add a project rule that points agents to this folder and scripts.
