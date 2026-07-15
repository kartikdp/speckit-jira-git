# Workflow patterns

Patterns that came out of using this skill in real time. Read this when
deciding how to use the scripts in combination, or when something you push
doesn't render the way you expected.

## 1. Generate, preview, then push

Pushes to Jira are not free: tickets must be deleted by hand if the shape
turns out wrong, and bulk-create is partial-success (some succeed, others
fail). Always do this in two steps:

1. Run `generate_subtasks_payload.py` with the parent key and tasks.md path.
   The script writes a `<output>.json` (the bulk-create body) and a
   `<output>.md` (a human preview). It never calls Jira.
2. Open the `.md` file. Read every summary, every label, every estimate. If
   anything looks wrong, edit `tasks.md` (or the generator args) and
   regenerate.
3. Once the preview is right, push with `push_subtasks.py --payload <json>`.

## 2. Smoke push, then bulk push

For a multi-phase rollout, push phase 1 first as a smoke test:

```bash
python scripts/push_subtasks.py --payload exports/foo-payload.json --phase 1
```

Wait for the response, then go look at the new issue in Jira. Specifically
verify:

- The summary is correct
- The parent linkage shows the right story key
- The description renders cleanly (especially bullets and inline code)
- Labels are attached
- Original estimate appears
- For sub-tasks, the inherited sprint (if any) is visible

Only then push the rest:

```bash
python scripts/push_subtasks.py --payload exports/foo-payload.json --phases 2,3,4,5,6
```

This catches ADF rendering quirks and parent-key typos against one ticket
instead of N.

## 3. Duplicate-summary pre-check

`push_subtasks.py` runs `summary in (...)` JQL before posting and refuses to
re-create existing tickets unless `--allow-duplicates` is passed. This makes
the script safe to re-run if the previous run errored partway. The Jira
duplicate-detection is exact-match on summary (case-sensitive), so if you
ever need to re-issue a sub-task with a fresh ticket, change the summary
slightly first.

## 4. Comment, log time, transition - in that order

When closing a sub-task that was finished, run the three actions in this
order so the timeline reads sensibly in Jira:

```bash
python scripts/add_comment.py --issue PROJ-101 --comment-file exports/phase-1-summary.md
python scripts/log_worklog.py  --issue PROJ-101 --time-spent 15m --started 2026-05-08 \
    --comment-file exports/phase-1-worklog-note.md
python scripts/transition_issue.py --issue PROJ-101 --to "Done"
```

Reverse order works too, but if anything fails you'd rather have the
audit comment in place than the status flip.

## 5. Worklog comments are first-class

The worklog `comment` field is plain text in many UIs but renders as ADF in
the issue history. Use a substantive note: what was actually delivered, not
just `"Logged 5h"`. The comment also surfaces in time-tracking reports.

## 6. Sub-task sprint inheritance

Sub-tasks cannot have their own `customfield_10020` (Sprint). They inherit
the parent story's active sprint at creation time. Two consequences:

- If the parent isn't yet in a sprint, sub-tasks land in the backlog. Move
  the parent first.
- Changing the parent's sprint later does not move existing sub-tasks. They
  stay in whatever sprint the parent was in when they were created. Move
  sub-tasks individually with `POST /rest/agile/1.0/sprint/{sprintId}/issue`
  (the skill doesn't ship a script for this; rare enough to do by hand).

## 7. Logging non-ticket time

Meetings, standups, story grooming, and similar non-ticket time still need
to be tracked but shouldn't pollute feature sub-tasks. Convention: keep a
single sub-task in each sprint named something like "Log time for
brainstorming, planning and standup" and bucket all that time into it via
`log_worklog.py` with a per-day worklog. This keeps feature tickets clean
and gives a single place to see how much time the team spends in
non-ticket work.

## 8. When Jira returns the wrong-looking data after a push

Jira's search index is briefly behind the create endpoint. If you do a JQL
query immediately after a bulk-push you may see fewer issues than you just
created. Wait 5 seconds and re-query, or fetch by key directly via
`GET /rest/api/3/issue/{key}`.

## 9. Idempotent re-runs

All three of these scripts are designed to be re-runnable:

- `push_subtasks.py` - duplicate-checks before posting
- `add_comment.py` - posting again creates a new comment, so use `--update-id`
  if you want to edit instead of add
- `log_worklog.py` - posting again creates a new worklog, so use
  `update_worklog.py` if you want to edit instead

`transition_issue.py` is also idempotent in the sense that transitioning to
the current status is a no-op (Jira returns 204 either way).

## 10. Decimal hour estimates from spec sheets

Engineering estimates in spreadsheets are often decimals (`18.4h`). Jira
doesn't accept decimals in `originalEstimate`. The `update_estimate.py`
script auto-converts: `18.4h` -> `18h 24m`. Use that script rather than
hand-converting; it handles edge cases (rounding 60-minute remainders up
to the next hour).
