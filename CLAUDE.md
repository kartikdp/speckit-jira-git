# Claude Code Instructions for speckit-jira-git

Use this folder as the source of truth for Jira, Spec Kit, and GitHub activity workflows.

Do not hand-roll Jira REST calls when a command exists. Prefer workflow-level commands:

```bash
speckit-jira-git setup-check
speckit-jira-git standard-tasks --help
speckit-jira-git pr-to-jira --help
speckit-jira-git review-to-jira --help
speckit-jira-git time-report --help
```

Use cases:

- Setup: check credentials and install repo-local agent instructions.
- Add stories/tasks to Jira: create standard review tasks and Spec Kit sub-tasks.
- Sync GitHub to Jira: post PR, review, requested-changes, close, and merge status.
- Check and update logged hours: add/edit worklogs and export date-range reports.
- Jira maintenance: add comments, transition issues, update estimates, inspect project metadata.

When opening or updating a PR, run `pr-to-jira` and post the PR activity to the linked Jira issue.

When recording a code review, run `review-to-jira` with the review status, reviewer, round, and area.

When creating delivery tasks under a Jira story, use `standard-tasks` for Specs Generation, Specs Review, Clarification Round, Code Review Round N, PR Review, FE PR Review, and BE PR Review.

Never print or commit `JIRA_TOKEN` or `GITHUB_TOKEN`.
