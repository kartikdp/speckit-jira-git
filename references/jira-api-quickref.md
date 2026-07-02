# Jira REST API quick reference (skill scope only)

This file documents only the endpoints the skill uses. Generic placeholders
are used throughout: `PROJ` for the project key, `PROJ-100` for the parent
story, `PROJ-101..PROJ-N` for sub-task keys, `Reviewer Name` for any human
display name. Replace at runtime with values from your environment.

## Authentication

All requests use HTTP Basic Auth with email + API token:

```
Authorization: Basic base64(<JIRA_EMAIL>:<JIRA_TOKEN>)
Accept: application/json
Content-Type: application/json
```

API tokens are created at `id.atlassian.com/manage-profile/security/api-tokens`.

## Issue type discovery

```
GET /rest/api/3/issuetype
```

Each entry has `id`, `name`, and `subtask: true|false`. Filter for the one
where both `subtask` is true and `name` is `"Sub-task"` (or the close variant
your tenant uses, e.g. `"Subtask"`). Cache the id.

## Project, board, sprint discovery

Project metadata:

```
GET /rest/api/3/project/{projectKey}
```

Board for a project:

```
GET /rest/agile/1.0/board?projectKeyOrId={projectKey}&type=scrum
```

Returns `values: [{id, name, type}]`. Pick the first (or filter by name).

Sprints on a board:

```
GET /rest/agile/1.0/board/{boardId}/sprint?state=active
```

Returns `values: [{id, name, state}]`. There is usually 0 or 1 active sprint.

## Search

```
POST /rest/api/3/search/jql
{
  "jql": "project = PROJ AND summary ~ \"<fragment>\"",
  "fields": ["summary", "status", "issuetype", "parent"],
  "maxResults": 50
}
```

Returned shape:

```json
{
  "issues": [
    {
      "key": "PROJ-100",
      "fields": {
        "summary": "...",
        "status": {"name": "To Do"},
        "issuetype": {"name": "Story"},
        "parent": {"key": "PROJ-50"}
      }
    }
  ]
}
```

## User search

```
GET /rest/api/3/user/search?query={name-or-email-fragment}
```

Returns a list. Match exact display name first; fall back to first hit. The
`accountId` is what you pass when assigning issues.

## Create one issue

```
POST /rest/api/3/issue
{
  "fields": {
    "project":     { "key": "PROJ" },
    "issuetype":   { "id": "<sub-task-id>" },
    "summary":     "Code Review",
    "parent":      { "key": "PROJ-100" },
    "assignee":    { "accountId": "..." },
    "priority":    { "name": "Medium" },
    "timetracking":{ "originalEstimate": "3h" },
    "description": <ADF doc>
  }
}
```

Response (`201 Created`): `{id, key, self}`.

## Bulk create issues

```
POST /rest/api/3/issue/bulk
{
  "issueUpdates": [
    {"fields": { ... }},
    {"fields": { ... }}
  ]
}
```

Up to 50 issues per call. Response shape:

```json
{
  "issues":          [{"id": "...", "key": "PROJ-101"}, {"id": "...", "key": "PROJ-102"}],
  "createdIssues":   [...],   // older Jira instances; either field may be present
  "errors":          []
}
```

Always check both `errors` and the created list - bulk returns partial
success. Failed items don't stop the batch.

## Sub-tasks

A sub-task is just `issuetype.id == <subtask-id>` plus a `parent.key` set to
a level-0 issue (Story, Task, Feature). Sub-tasks cannot have their own
`customfield_10020` (Sprint); they inherit the parent's.

## Comments

Add:

```
POST /rest/api/3/issue/{key}/comment
{ "body": <ADF doc> }
```

Response includes `id`, which you keep if you ever need to edit:

```
PUT /rest/api/3/issue/{key}/comment/{commentId}
{ "body": <new ADF doc> }
```

## Worklogs

Add:

```
POST /rest/api/3/issue/{key}/worklog
{
  "timeSpent": "2h 30m",
  "started":   "2026-05-08T10:00:00.000+0000",
  "comment":   <ADF doc>
}
```

Edit:

```
PUT /rest/api/3/issue/{key}/worklog/{worklogId}
{ "timeSpent": "...", "started": "...", "comment": ... }
```

List:

```
GET /rest/api/3/issue/{key}/worklog
```

Important: the `started` field's offset must be `+0000` (no colon). Jira
rejects `+00:00`.

## Time tracking format

Jira time strings: `1w 2d 3h 4m`, where the units are weeks, days, hours,
minutes (workdays default to 8 hours, weeks to 5 working days). Plain `5h`
or `30m` is fine. Decimals (`18.5h`) are NOT accepted: convert to compound,
e.g. `18.5h` -> `18h 30m`. The `update_estimate.py` script does the
conversion automatically.

To set or update an estimate on an existing issue:

```
PUT /rest/api/3/issue/{key}
{ "fields": { "timetracking": { "originalEstimate": "18h 24m" } } }
```

## Transitions

List available transitions for an issue:

```
GET /rest/api/3/issue/{key}/transitions
```

Apply one:

```
POST /rest/api/3/issue/{key}/transitions
{ "transition": { "id": "<transition-id>" } }
```

Transition ids vary per workflow and may differ between issue types within
the same project. Always look up by name on the specific issue you're moving.

## Common errors

| Status | Meaning | Common cause |
|---|---|---|
| 400 | Bad Request | Invalid field shape (e.g. plain string in `description` instead of ADF; sprint id passed as object instead of integer) |
| 401 | Unauthorized | Wrong email or token. Check the JIRA_EMAIL/JIRA_TOKEN env vars |
| 403 | Forbidden | Token works but lacks permission on the project |
| 404 | Not Found | Wrong project key or issue key |
| 422 | Unprocessable | Hit when posting to /api/auth/login with empty body; in our skill flow this means a payload validation issue |
| 429 | Too Many Requests | Rate limited. Honour `Retry-After` header. The bulk-create helper retries automatically up to a few times |
