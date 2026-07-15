# speckit-jira-git

Portable Agent Skill and optional CLI for Spec Kit, Jira, and GitHub workflows.

The repository has two distribution surfaces:

- `npx skills add` installs the complete multi-file Agent Skill.
- npm/GitHub installation exposes the optional `speckit-jira-git` shell command.

## Install the Agent Skill

```bash
npx skills add kartikdp/speckit-jira-git --skill speckit-jira-git
```

Use the installer's agent-selection flags when a non-interactive target is
needed, and `-g` for a user-level installation. The installer owns agent-specific
locations and symlinks; the skill does not assume `.agents`, `.claude`, or any
other installation path.

Installing a skill does not guarantee that its CLI is added to `PATH`. Agents
may run the bundled executable relative to the loaded skill directory:

```bash
node bin/speckit-jira-git.js setup-check
```

For a shell-level CLI, install or invoke the npm package separately:

```bash
npx github:kartikdp/speckit-jira-git setup-check
```

## Capabilities

- Validate Jira and GitHub access without printing secrets.
- Create consistently described Spec Kit process and implementation sub-tasks.
- Enforce canonical workflow order and stable Jira titles.
- Attach complete review packets to Specs Review tasks.
- Render versioned, structured GitHub PR and review activity into Jira ADF.
- Add, update, and report Jira worklogs.
- Perform explicit Jira maintenance without inferring status transitions.

Run `speckit-jira-git --help` for the command map.

## Credentials

The CLI reads credentials in this order:

1. Current process environment.
2. Project `.env`.
3. `~/.jira/credentials.env`.

Required Jira variables:

```text
JIRA_URL=https://your-tenant.atlassian.net
JIRA_EMAIL=you@example.com
JIRA_TOKEN=...
JIRA_PROJECT=PROJ
```

`GITHUB_TOKEN` is optional; GitHub commands otherwise use `gh auth token`.
Never commit credentials.

Non-secret user or organization defaults may be stored in a project-local
`.speckit-jira-git.toml`; see the installed skill reference for supported
fields and precedence.

## Repository layout

```text
skills/speckit-jira-git/
  SKILL.md
  agents/openai.yaml
  bin/
  scripts/
  references/
  assets/
  requirements.txt
```

Root `AGENTS.md` contains contributor instructions. Root `CLAUDE.md` imports it
and is not part of the installed skill payload.

## Verify

```bash
npm run check
npm test
npm run validate-skill
```

Layout changes must also pass clean temporary `npx skills add` and `npm pack`
smoke tests.
