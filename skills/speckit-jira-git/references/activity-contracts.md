# Structured activity contracts

PR and review comments use schema version 1. JSON Schemas are bundled at:

- `assets/schemas/pr-activity-v1.schema.json`
- `assets/schemas/review-activity-v1.schema.json`

## Validation evidence

Pass repeatable values using:

```text
status|name|detail
```

Allowed statuses are `passed`, `failed`, `blocked`, and `skipped`. `name` is required; `detail` records the observed result or limitation.

## Review finding

Pass repeatable values using:

```text
severity|summary|path|line|impact|required_action
```

Allowed severities are `P0`, `P1`, `P2`, and `P3`. Summary is required. Path, positive line number, impact, and required action should be supplied for actionable code findings.

A finding file can be a JSON array or an object with a `findings` array:

```json
{
  "findings": [
    {
      "severity": "P2",
      "summary": "Reject malformed cursors",
      "path": "backend/api.py",
      "line": 87,
      "impact": "Bad input restarts pagination",
      "required_action": "Return HTTP 400"
    }
  ]
}
```

## Rendering guarantees

Renderers produce fixed section order in both GitHub Markdown and Jira ADF. Common credentials, bearer tokens, GitHub token prefixes, and URL passwords are redacted. Single-line identity/title fields reject embedded newlines, and imported text is length-bounded.

Legacy `--summary` remains accepted as a hidden compatibility alias for `--headline`, but new automation should use structured fields.
