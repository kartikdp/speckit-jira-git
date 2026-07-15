# Time Reporting

Use `scripts/jira_time_report.py` to export worklogs for a date range.

Current user only:

```bash
speckit-jira-git time-report --from 2026-07-01 --to 2026-07-15 --csv exports/time.csv --markdown exports/time.md
```

All visible users:

```bash
speckit-jira-git time-report --from 2026-07-01 --to 2026-07-15 --all-users --csv exports/team-time.csv
```

Outputs include:

- date
- issue
- parent
- issue summary
- author
- seconds
- hours
- worklog comment text

The script filters by `worklogDate` using JQL, then fetches worklogs per returned issue and filters exact dates client-side.
