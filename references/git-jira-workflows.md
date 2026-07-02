# GitHub to Jira Workflows

Use these scripts when GitHub activity needs to be recorded as Jira comments without relying on Jira Automation or GitHub for Atlassian sync.

## Jira key detection

Scripts detect keys from:

- PR title.
- PR body.
- source branch.
- target branch.
- PR commit messages.

Default regex:

```text
\b[A-Z][A-Z0-9]+-\d+\b
```

Pass `--issue PROJ-123` when detection is ambiguous.

## PR activity

Dry-run:

```bash
speckit-jira-git pr-to-jira --pr-url https://github.com/org/repo/pull/123 --event opened --dry-run --json
```

PR comments include a fixed-width Jira code block with a compact status card:

```text
+---------------- GitHub PR Status ----------------+
| PR       : org/repo#123
| Event    : updated
| State    : open
| Draft    : no
| Merge    : clean
| Source   : feature/PROJ-123-example
| Target   : main
| Updated  : 2026-07-02T10:00:00Z
+--------------------------------------------------+

feature/PROJ-123-example  --->  PR #123  --->  main
```

Post live:

```bash
speckit-jira-git pr-to-jira --pr-url https://github.com/org/repo/pull/123 --event ready
```

Supported events:

```text
opened
ready
updated
closed
merged
```

## Review activity

```bash
speckit-jira-git review-to-jira \
  --pr-url https://github.com/org/repo/pull/123 \
  --status changes_requested \
  --reviewer "Reviewer Name" \
  --round 2 \
  --area backend \
  --summary "Requested API contract and test updates."
```

Supported statuses:

```text
approved
changes_requested
commented
review_requested
```

## Idempotency

GitHub-to-Jira scripts add a stable marker to each Jira comment, such as:

```text
speckit-jira-git:github-pr:opened:org/repo#123
```

If the marker already exists on the Jira issue, reruns skip creating a duplicate comment.
