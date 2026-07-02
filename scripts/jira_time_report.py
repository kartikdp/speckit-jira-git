"""Generate a Jira worklog report for a date range."""
from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from activity_common import plain_from_adf
from jira_client import JiraClient


@dataclass(frozen=True)
class WorklogRow:
    date: str
    issue: str
    parent: str
    summary: str
    author: str
    seconds: int
    hours: float
    comment: str


def _parse_started(value: str) -> str:
    return datetime.strptime(value[:10], "%Y-%m-%d").date().isoformat()


def _in_range(date: str, start: str, end: str) -> bool:
    return start <= date <= end


def _rows(client: JiraClient, start: str, end: str, current_user_only: bool) -> list[WorklogRow]:
    myself = client.whoami()
    account_id = myself.get("accountId")
    jql = f'project = {client.config.project} AND worklogDate >= "{start}" AND worklogDate <= "{end}"'
    if current_user_only:
        jql += " AND worklogAuthor = currentUser()"
    issues = client.search_jql(jql, fields=["summary", "parent"], max_results=200)
    rows: list[WorklogRow] = []
    for issue in issues:
        key = issue["key"]
        fields = issue.get("fields") or {}
        summary = fields.get("summary") or ""
        parent = ((fields.get("parent") or {}).get("key")) or ""
        data = client.get(f"/rest/api/3/issue/{key}/worklog") or {}
        for worklog in data.get("worklogs", []):
            if current_user_only and (worklog.get("author") or {}).get("accountId") != account_id:
                continue
            date = _parse_started(worklog.get("started", ""))
            if not _in_range(date, start, end):
                continue
            seconds = int(worklog.get("timeSpentSeconds") or 0)
            rows.append(
                WorklogRow(
                    date=date,
                    issue=key,
                    parent=parent,
                    summary=summary,
                    author=(worklog.get("author") or {}).get("displayName", ""),
                    seconds=seconds,
                    hours=round(seconds / 3600, 2),
                    comment=plain_from_adf(worklog.get("comment")),
                )
            )
    return sorted(rows, key=lambda row: (row.date, row.issue))


def _write_csv(rows: list[WorklogRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["date", "issue", "parent", "summary", "author", "seconds", "hours", "comment"],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def _markdown(rows: list[WorklogRow], start: str, end: str) -> str:
    by_day: dict[str, float] = defaultdict(float)
    by_issue: dict[str, float] = defaultdict(float)
    for row in rows:
        by_day[row.date] += row.hours
        by_issue[row.issue] += row.hours
    lines = [
        f"# Jira time report: {start} to {end}",
        "",
        f"Total hours: {round(sum(row.hours for row in rows), 2)}",
        "",
        "## By day",
        "",
    ]
    lines.extend(f"- {day}: {round(hours, 2)}h" for day, hours in sorted(by_day.items()))
    lines.extend(["", "## By issue", ""])
    lines.extend(f"- {issue}: {round(hours, 2)}h" for issue, hours in sorted(by_issue.items()))
    lines.extend(["", "## Entries", ""])
    for row in rows:
        parent = f" parent={row.parent}" if row.parent else ""
        lines.append(f"- {row.date} {row.issue}{parent}: {row.hours}h - {row.summary}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate Jira worklog CSV/Markdown report")
    parser.add_argument("--from", dest="start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--all-users", action="store_true", help="Include all visible users instead of current user")
    parser.add_argument("--csv", dest="csv_path", help="CSV output path")
    parser.add_argument("--markdown", dest="md_path", help="Markdown output path")
    parser.add_argument("--json", action="store_true", help="Print JSON rows")
    args = parser.parse_args()

    client = JiraClient()
    rows = _rows(client, args.start, args.end, current_user_only=not args.all_users)
    if args.csv_path:
        _write_csv(rows, Path(args.csv_path))
    md = _markdown(rows, args.start, args.end)
    if args.md_path:
        path = Path(args.md_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(md, encoding="utf-8")
    if args.json:
        print(json.dumps({"rows": [row.__dict__ for row in rows]}, indent=2))
    else:
        print(md)


if __name__ == "__main__":
    main()
