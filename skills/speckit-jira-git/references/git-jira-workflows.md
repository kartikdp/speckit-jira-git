# GitHub to Jira workflows

Use these commands to record observed GitHub activity as versioned, structured Jira comments without depending on Jira Automation.

## Jira key detection

Keys are detected from PR title, source/target branch, commit messages, then PR body. Pass `--issue PROJ-123` when detection is ambiguous.

## Pull-request activity

Dry-run the fully rendered GitHub Markdown and Jira ADF:

```bash
speckit-jira-git pr-to-jira \
  --pr-url https://github.com/org/repo/pull/123 \
  --event updated \
  --commit abc123 \
  --change "Implemented durable cursor validation" \
  --validation "passed|unit tests|42 passed" \
  --remaining "Add DB-backed integration evidence" \
  --dry-run --json
```

Supported events are `opened`, `ready`, `updated`, `closed`, and `merged`.

The renderer always includes:

- PR identity, repository, branches, current head SHA, author, and state.
- Every PR commit SHA and subject.
- Explicit changes supplied with repeatable `--change`.
- Validation evidence supplied as `status|name|detail`.
- Observed checks, mergeability, and review state.
- Remaining work supplied with repeatable `--remaining`.
- An evidence URL and optional redacted source note.

Use `--comment-url` to cite an existing PR conversation comment. Use `--post-github` to post the canonical rendered update first and synchronize that new comment to Jira. These options are mutually exclusive.

## Required post-push workflow

After every successful push containing commits:

1. Verify the remote branch SHA and identify every commit in that push.
2. Find the open PR for that branch.
3. Supply every pushed SHA with repeatable `--commit` plus factual `--change`, `--validation`, and `--remaining` fields.
4. Run `pr-to-jira --event updated --post-github`.
5. Record the returned GitHub comment URL and Jira synchronization result.

One update can cover multiple commits. Each `--commit` SHA/prefix must resolve to exactly one commit in the selected PR, and `--post-github` rejects incomplete structured input. Never claim unobserved checks or include credentials/logs containing secrets. If no open PR exists, report that instead of inventing a target.

## Review activity

```bash
speckit-jira-git review-to-jira \
  --pr-url https://github.com/org/repo/pull/123 \
  --status changes_requested \
  --reviewer "Human Reviewer" \
  --round 2 \
  --area backend \
  --finding "P1|Reject malformed cursors|backend/api.py|87|Bad input restarts pagination|Return HTTP 400" \
  --validation "passed|focused contract tests|18 passed"
```

Supported statuses are `approved`, `changes_requested`, `commented`, and `review_requested`. The reviewer is the actual human attribution; it is not a Jira task-assignment instruction. When a matching GitHub review exists, its URL and redacted body are included as evidence.

For many findings, pass one or more JSON packets with `--finding-file`. See `activity-contracts.md`.

## Idempotency

Markers include schema version, PR identity, current head SHA, event/status, and review dimensions. Reruns skip equivalent comments unless `--update-existing` is supplied.
