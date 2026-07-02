# Standard Review And Planning Tasks

Use `scripts/jira_create_standard_tasks.py` to create recurring delivery sub-tasks under a Jira parent.

Supported kinds:

```text
specs-generation
specs-review
clarification-round
code-review
pr-review
fe-pr-review
be-pr-review
```

Example:

```bash
speckit-jira-git standard-tasks \
  --parent PROJ-123 \
  --kinds specs-generation,specs-review,clarification-round,code-review,pr-review \
  --round 1 \
  --reviewer "Reviewer Name" \
  --estimate 3h \
  --pr-url https://github.com/org/repo/pull/123
```

For FE/BE split reviews:

```bash
speckit-jira-git standard-tasks \
  --parent PROJ-123 \
  --kinds fe-pr-review,be-pr-review \
  --reviewer "Reviewer Name" \
  --estimate 2h
```

The script checks duplicate summaries under the same parent unless `--allow-duplicates` is passed.
