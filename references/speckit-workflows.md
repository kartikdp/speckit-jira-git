# Spec Kit Workflows

Use this workflow when converting Spec Kit `tasks.md` into Jira sub-tasks.

1. Find or confirm the parent Jira issue.
2. Generate payload and preview:

```bash
python3 scripts/generate_subtasks_payload.py \
  --tasks specs/012-feature/tasks.md \
  --parent PROJ-123 \
  --output exports/012-feature-payload.json
```

3. Review the generated Markdown preview next to the JSON payload.
4. Smoke push one phase:

```bash
python3 scripts/push_subtasks.py --payload exports/012-feature-payload.json --phase 1
```

5. Verify the created Jira sub-task in the UI.
6. Push remaining phases:

```bash
python3 scripts/push_subtasks.py --payload exports/012-feature-payload.json --phases all
```

Sub-tasks inherit sprint from the parent at creation time.
