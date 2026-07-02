# Project discovery and the local cache

The skill avoids hardcoding any tenant-specific id (issue type, board,
sprint, transition). Instead, on first use it queries Jira to discover the
ones it needs and caches them in `~/.cache/speckit-to-jira/<JIRA_PROJECT>.json`.

## What gets discovered

The discovery script (`scripts/discover_project_metadata.py`) probes:

| Field | Endpoint | Why |
|---|---|---|
| `subtask_type_id` | `GET /rest/api/3/issuetype` | Required to create sub-tasks. Jira returns multiple subtask-flavoured types; we filter for the one named `Sub-task` or `Subtask`. |
| `board_id` | `GET /rest/agile/1.0/board?projectKeyOrId=<key>&type=scrum` | Used to find the active sprint. We pick the first matching board. |
| `active_sprint` | `GET /rest/agile/1.0/board/<id>/sprint?state=active` | Surfaced for context; we don't set sprints on sub-tasks (they inherit parents). |
| `done_transition_id` | `GET /rest/api/3/issue/<sample>/transitions` | We don't actually persist this any more (the transition_issue.py script looks it up live), but the discovery records it so the cache reflects "is the workflow set up correctly?" |

## Cache shape

```json
{
  "project_key": "PROJ",
  "subtask_type_id": "10006",
  "board_id": 2359,
  "active_sprint": {"id": 4797, "name": "Sprint 1"},
  "done_transition_id": "31"
}
```

No credentials, no email, no display names. Safe to share if someone needs
the same metadata.

## Refresh

The cache is sticky. Refresh manually after a Jira admin changes the
project's workflow, board, or issue type configuration:

```bash
python scripts/discover_project_metadata.py --refresh
```

The cache filename is keyed by `JIRA_PROJECT`, so multiple projects can
coexist on the same machine without clobbering each other.

## When discovery fails

| Symptom | Likely cause | Fix |
|---|---|---|
| `subtask_type_id: null` | Project doesn't have a Sub-task issue type configured. | Ask the Jira admin to enable Sub-task in the project's issue type scheme. |
| `board_id: null` | Project has no Scrum board (might be Kanban or no board). | If it's a Kanban project, pass an empty `--phases` push and use a manual board for sprints. The skill still works for ticket creation; just the sprint inheritance comment doesn't apply. |
| `active_sprint: null` or `{"error": ...}` | No sprint is currently active, or the board returned 400/404 (not a Scrum board). | Move the parent story to a sprint manually before pushing sub-tasks. |
| `done_transition_id: null` | Workflow doesn't have a "Done" transition by name. | Inspect with `transition_issue.py --issue <key> --list` and use whatever name your workflow uses (e.g. `"Resolve"`). |

## What discovery does NOT do

- It does not write anything to Jira.
- It does not store credentials.
- It does not infer sprint id automatically when creating sub-tasks; sub-task
  sprint always inherits the parent.
- It does not look up `accountId`s for assignment; user resolution is done
  on demand by `JiraClient.find_user_account_id(name)`.
