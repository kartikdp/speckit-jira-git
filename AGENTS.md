# Repository contributor instructions

This repository publishes an agent-neutral Agent Skill and an optional npm CLI.
Keep portable runtime content under `skills/speckit-jira-git/`; root files are
for repository development and distribution only.

## Development rules

- Do not add user names, Jira account IDs, tenant URLs, tokens, or organization-
  specific assignment policy to portable source, examples, or defaults.
- Keep Jira identity attribution separate from Jira task assignment.
- Keep generated Jira issues in their default status unless a caller explicitly
  requests a transition.
- Preserve deterministic workflow ordering, structured comment schemas,
  idempotency markers, and secret redaction when changing integrations.
- Put detailed workflows in the skill's `references/` directory and reusable
  output contracts/templates in `assets/`; keep `SKILL.md` concise.

## Validation

Run before proposing a release:

```bash
npm run check
npm test
npm run validate-skill
```

Also perform a clean temporary `npx skills add` installation and an `npm pack`
smoke test when changing layout, package metadata, or executable paths.
