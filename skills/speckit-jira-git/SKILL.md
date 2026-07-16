---
name: speckit-jira-git
description: Portable Spec Kit, Jira, and GitHub workflow automation. Use for Jira setup and maintenance, deterministic Spec Kit story/sub-task creation, complete Specs Review attachments, GitHub PR or review synchronization, worklogs, estimates, transitions, project discovery, and time reports.
---

# Spec Kit Jira Git

Use the scripts bundled beside this file. They provide consistent credential loading, Jira ADF, duplicate protection, canonical task ordering, structured GitHub activity, and secret redaction.

## Invocation

If `speckit-jira-git` is on `PATH`, use it. Otherwise invoke the bundled CLI relative to this loaded skill root:

```bash
node bin/speckit-jira-git.js <command> [args...]
```

The skill installer chooses the agent-specific installation path. Never assume `.agents`, `.claude`, or another fixed directory.

If neither invocation can be resolved, stop before any Jira or GitHub write and
tell the user that the required `speckit-jira-git` skill or CLI could not be
loaded, which locations were checked, and that the project structure or skill
installation must be repaired. Do not substitute direct Jira REST calls,
generic Jira tools, `gh` mutations, or manually constructed payloads.

## Safety

- Run `setup-check` before live Jira or GitHub writes.
- Use `--dry-run` when a target issue, PR, review area, or payload is uncertain.
- Never print or copy secrets into Jira/GitHub content.
- Leave created Jira work in its default status. Transition only when an explicit target status is requested.
- Attribute reviews to the actual human reviewer. Keep reviewer attribution separate from Jira task assignment.
- Leave PR Review tasks unassigned unless a human reviewer is explicitly supplied.
- Do not claim unobserved validation, CI, mergeability, comments, or approvals.

## Configuration

Required Jira environment variables:

```text
JIRA_URL
JIRA_EMAIL
JIRA_TOKEN
JIRA_PROJECT
```

`GITHUB_TOKEN` is optional; GitHub commands otherwise use `gh auth token`. Credential loading is process environment, project `.env`, then `~/.jira/credentials.env`.

Use project-local `.speckit-jira-git.toml` for non-secret defaults such as human identity, assignment, and parent-story title format. See `references/configuration.md`.

## Canonical workflow

Create Jira work in this exact sequence:

1. Specs Generation
2. Specs Review
3. Clarification Round(s)
4. Implementation Phase(s)
5. Code Review Round(s)
6. PR Review(s)

Use CLI-generated stage-coded titles; do not hand-format task titles. Generate phases from `tasks.md`, and attach the complete Spec Kit packet to Specs Review. See `references/workflow-ordering.md`, `references/speckit-workflows.md`, and `references/review-task-patterns.md`.

## Structured GitHub activity

PR updates and reviews use versioned contracts and deterministic Markdown/Jira ADF. Prefer repeatable `--change`, `--validation`, `--remaining`, and `--finding` fields over free-form summaries.

After every successful push containing commits, verify the remote SHA/open PR and post one canonical GitHub conversation update before Jira synchronization:

```bash
speckit-jira-git pr-to-jira --pr-url <PR_URL> --event updated \
  --commit <PUSHED_SHA> \
  --change "<change>" \
  --validation "passed|<check>|<observed result>" \
  --remaining "<remaining work or None>" \
  --post-github
```

For reviews:

```bash
speckit-jira-git review-to-jira --pr-url <PR_URL> \
  --status <approved|changes_requested|commented|review_requested> \
  --reviewer "<actual human>" --round <N> --area <area> \
  --finding "P2|<summary>|<path>|<line>|<impact>|<required action>" \
  --validation "passed|<check>|<observed result>"
```

See `references/activity-contracts.md` and `references/git-jira-workflows.md`.

## Reference router

- Install and credentials: `references/setup.md`
- Non-secret preferences: `references/configuration.md`
- Canonical order and titles: `references/workflow-ordering.md`
- Spec Kit phases to Jira: `references/speckit-workflows.md`
- Standard process/review tasks: `references/review-task-patterns.md`
- PR/review activity: `references/git-jira-workflows.md`
- Structured payload fields: `references/activity-contracts.md`
- Jira REST operations: `references/jira-api-quickref.md`
- Date-range time reports: `references/time-reporting.md`
- ADF formatting: `references/adf-format.md`

## Common commands

```bash
speckit-jira-git setup-check
speckit-jira-git story-title --story-id OBS-RUN-L0-1 --outcome "define the contract boundary"
speckit-jira-git standard-tasks --parent PROJ-123 --kinds specs-generation,specs-review \
  --spec-file spec.md --spec-file plan.md --spec-file tasks.md
speckit-jira-git generate-subtasks --tasks tasks.md --parent PROJ-123 --output exports/tasks.json
speckit-jira-git push-subtasks --payload exports/tasks.json
speckit-jira-git log-worklog --issue PROJ-123 --time 2h --started 2026-07-15 --comment "Implementation"
```

Use `speckit-jira-git --help` and `<command> --help` for the complete CLI surface.
