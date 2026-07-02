# speckit-jira-git Agent Instructions

Use this package for Jira, Spec Kit, GitHub PR/review tracking, and time reporting tasks.

Always prefer scripts in `scripts/` over hand-written Jira or GitHub API calls. The scripts load credentials from environment variables, project `.env`, or `~/.jira/credentials.env` and avoid printing tokens.

Run setup validation before live work:

```bash
speckit-jira-git setup-check
```

Use these workflows:

- Setup: `setup-check`, `install-instructions`.
- Add stories/tasks to Jira: `find-parent`, `standard-tasks`, `generate-subtasks`, `push-subtasks`.
- Sync GitHub to Jira: `find-jira-key`, `pr-to-jira`, `review-to-jira`.
- Check and update logged hours: `log-worklog`, `update-worklog`, `time-report`.
- Jira maintenance: `add-comment`, `transition`, `update-estimate`, `discover-project`.

For GitHub-to-Jira activity, detect the Jira key from PR title, branch, body, or commit messages. If no key is found, ask for the Jira issue key instead of guessing.

Use dry-run flags before posting to live Jira when the request is ambiguous.

If this repository is checked out locally, running `python3 scripts/<name>.py`
is also supported. Prefer an installed or vendored `speckit-jira-git` command
for routine work; use `npx github:kartikdp/speckit-jira-git ...` only to
bootstrap or refresh the tool.
