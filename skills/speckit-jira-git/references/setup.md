# Setup and installation

## Install the skill

Install from the repository with the standard skills installer:

```bash
npx skills add <owner>/<repository> --skill speckit-jira-git
```

Select installation targets with the installer's current agent-selection flags
when non-interactive installation is required. The installer discovers
`skills/speckit-jira-git/SKILL.md` and copies or links the complete skill
folder, including scripts, references, assets, and agent metadata. It owns the
destination layout; neither the package nor consuming instructions should
hardcode an agent-specific directory.

An installed skill is not necessarily a globally installed executable. Use the bundled command from the loaded skill root when `speckit-jira-git` is absent from `PATH`:

```bash
node bin/speckit-jira-git.js --help
```

The npm package also exposes the same CLI when installed globally or executed from the package.

## Install repository policy

Add the portable policy to `AGENTS.md`:

```bash
speckit-jira-git install-instructions
```

Ensure `CLAUDE.md` imports `AGENTS.md` without duplicating the policy:

```bash
speckit-jira-git install-instructions --all
```

Use `--target-file <path>` for another instruction file. The operation is idempotent through `speckit-jira-git:start/end` markers.

## Credentials

Create an Atlassian API token and provide:

```text
JIRA_URL
JIRA_EMAIL
JIRA_TOKEN
JIRA_PROJECT
```

Optional GitHub auth:

```text
GITHUB_TOKEN
```

When `GITHUB_TOKEN` is absent, GitHub scripts use `gh auth token`.

Credential loading order:

1. Current process environment.
2. Project `.env`.
3. `~/.jira/credentials.env`.

Prefer a gitignored credential file for persistent agent workflows. Never commit or print actual tokens.

## Validate

```bash
speckit-jira-git setup-check
```

The checker masks secrets, verifies Jira identity/project access, checks GitHub authentication, and reports candidate credential files. Install Python dependencies only if imports fail:

```bash
python3 -m pip install -r requirements.txt
```
