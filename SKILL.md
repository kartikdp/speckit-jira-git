---
name: speckit-jira-git
description: Portable Spec Kit, Jira, and GitHub workflow automation. Use when Codex needs to set up Jira/GitHub access, add stories/tasks/sub-tasks from Spec Kit plans into Jira, sync GitHub PR or review status back to linked Jira work items, check/add/update Jira logged hours, export time reports, or perform Jira maintenance such as comments, transitions, estimates, and project metadata using file-based JIRA_URL/JIRA_EMAIL/JIRA_TOKEN/JIRA_PROJECT credentials and optional GITHUB_TOKEN or gh auth.
---

# Spec Kit Jira Git

Use this skill as a portable workflow layer for Spec Kit, Jira, and GitHub. Prefer bundled scripts over hand-written REST calls because they handle Jira ADF, credential loading, duplicate checks, and GitHub/Jira key extraction consistently.

## Preflight

Required Jira variables:

```text
JIRA_URL
JIRA_EMAIL
JIRA_TOKEN
JIRA_PROJECT
```

Optional GitHub auth:

```text
GITHUB_TOKEN
```

If `GITHUB_TOKEN` is unset, GitHub scripts fall back to `gh auth token`.

For agent workflows, prefer credentials in a file because `export ...` in another terminal is not visible to the agent process. Run setup validation and use `recommended_credentials_file` / `dotenv_candidates` from the output to decide where the user should add or rotate tokens.

Credential loading order is current process environment, project `.env`, then `~/.jira/credentials.env`. Never print real tokens.

Run setup validation before live Jira/GitHub work:

```bash
speckit-jira-git setup-check
```

Install dependencies only if imports fail:

```bash
python3 -m pip install -r /path/to/speckit-jira-git/requirements.txt
```

Install this skill into supported agents:

```bash
npx skills add kartikdp/speckit-jira-git
```

Add repo-local instructions explicitly when you want agents to run the GitHub-to-Jira workflow during PR and review tasks:

```bash
speckit-jira-git install-instructions --target agents
```

## Workflow Router

Read only the relevant reference:

- Setup and install: `references/setup.md`.
- Spec Kit phase to Jira tasks: `references/speckit-workflows.md`.
- Jira issue operations: `references/jira-api-quickref.md`.
- GitHub PR/review comments to Jira: `references/git-jira-workflows.md`.
- Standard planning/review tasks: `references/review-task-patterns.md`.
- Date-range time reports: `references/time-reporting.md`.
- ADF details: `references/adf-format.md`.

## Use Case Router

Setup and install:

```bash
speckit-jira-git setup-check
speckit-jira-git install-instructions --target agents
```

Add stories/tasks to Jira from Spec Kit:

```bash
speckit-jira-git find-parent --query "agent registry" --types Epic Story Task
speckit-jira-git standard-tasks --parent PROJ-123 --kinds specs-generation,specs-review,clarification-round,code-review,pr-review --round 1
speckit-jira-git generate-subtasks --tasks specs/012-feature/tasks.md --parent PROJ-123 --output exports/012-feature-payload.json
speckit-jira-git push-subtasks --payload exports/012-feature-payload.json --phase 1
```

Sync GitHub PR/review status to Jira:

```bash
speckit-jira-git pr-to-jira --pr-url https://github.com/org/repo/pull/123 --event opened
speckit-jira-git review-to-jira --pr-url https://github.com/org/repo/pull/123 --status changes_requested --reviewer "Reviewer Name" --round 2 --area backend --summary "Requested contract and test updates."
```

Check and update logged hours:

```bash
speckit-jira-git log-worklog --issue PROJ-123 --time 2h --started 2026-07-02 --comment "Implementation"
speckit-jira-git update-worklog --issue PROJ-123 --worklog-id 12345 --time 3h
speckit-jira-git time-report --from 2026-07-01 --to 2026-07-15 --csv exports/time.csv --markdown exports/time.md
```

Jira maintenance:

```bash
speckit-jira-git add-comment --issue PROJ-123 --comment "Status update"
speckit-jira-git transition --issue PROJ-123 --to "In Progress"
speckit-jira-git update-estimate --issue PROJ-123 --estimate 3h
```

## Script Reference

```text
setup_check.py                  Validate Jira/GitHub setup without printing secrets.
install_instructions.py         Add marked instructions to AGENTS/CLAUDE/Cursor/Windsurf.
jira_client.py                  Shared Jira REST client and ADF helpers.
github_client.py                Shared GitHub REST helper.
activity_common.py              Shared Jira-key and idempotent-comment helpers.
find_parent_story.py            Search parent issues by summary.
parse_tasks_md.py               Parse Spec Kit tasks.md phases.
generate_subtasks_payload.py    Build Jira bulk-create payload and preview.
push_subtasks.py                Create Jira sub-tasks with duplicate checks.
add_comment.py                  Add/update Jira comments.
log_worklog.py                  Add/list Jira worklogs.
update_worklog.py               Edit Jira worklogs.
transition_issue.py             Move Jira issue by transition name.
update_estimate.py              Update original estimate.
create_code_review_subtask.py   Legacy single code-review sub-task helper.
jira_create_standard_tasks.py   Create standard specs/review/PR sub-tasks.
git_find_jira_key.py            Extract Jira keys from git/PR context.
git_pr_activity_to_jira.py      Comment PR opened/ready/updated/closed/merged on Jira.
git_review_activity_to_jira.py  Comment review outcome on Jira.
jira_time_report.py             Export Jira worklogs for a date range.
```
