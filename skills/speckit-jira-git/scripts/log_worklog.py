"""Log a worklog on a Jira issue, or list existing worklogs.

Examples:
    python log_worklog.py --issue PROJ-100 --time-spent 2h
    python log_worklog.py --issue PROJ-100 --time-spent 1h 30m --started 2026-05-08
    python log_worklog.py --issue PROJ-100 --time-spent 3h --started 2026-05-08 \\
        --comment-file exports/note.md
    python log_worklog.py --issue PROJ-100 --list
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

from jira_client import JiraClient
from markdown_to_adf import markdown_to_adf


def _started_iso(date_str: str, hour: int) -> str:
    """Format YYYY-MM-DD plus hour into Jira's expected ISO with offset."""
    if not date_str:
        date_str = _dt.date.today().isoformat()
    return f"{date_str}T{hour:02d}:00:00.000+0000"


def _list_worklogs(client: JiraClient, issue: str) -> None:
    data = client.get(f"/rest/api/3/issue/{issue}/worklog") or {}
    worklogs = data.get("worklogs", [])
    print(f"{issue}: {len(worklogs)} worklog(s)")
    for w in worklogs:
        author = (w.get("author") or {}).get("displayName", "?")
        print(
            f"  id={w['id']:>8}  spent={w['timeSpent']:>8}  "
            f"started={w.get('started','?')[:10]}  by={author}"
        )


def main() -> None:
    ap = argparse.ArgumentParser(description="Add a worklog (or list)")
    ap.add_argument("--issue", required=True)
    ap.add_argument("--time-spent", default=None, help='Time string, e.g. "2h 30m"')
    ap.add_argument("--started", default=None, help="YYYY-MM-DD; defaults to today")
    ap.add_argument(
        "--hour",
        type=int,
        default=10,
        help="Wall-clock hour for the started timestamp; defaults to 10:00",
    )
    ap.add_argument(
        "--comment-file",
        default=None,
        help="Path to markdown file with worklog body",
    )
    ap.add_argument(
        "--list",
        action="store_true",
        help="List existing worklogs on the issue and exit",
    )
    args = ap.parse_args()

    client = JiraClient()

    if args.list:
        _list_worklogs(client, args.issue)
        return

    if not args.time_spent:
        sys.exit("--time-spent is required unless --list is passed")

    body: dict = {"timeSpent": args.time_spent}
    if args.started:
        body["started"] = _started_iso(args.started, args.hour)
    else:
        body["started"] = _started_iso(_dt.date.today().isoformat(), args.hour)
    if args.comment_file:
        md = Path(args.comment_file).read_text(encoding="utf-8")
        body["comment"] = markdown_to_adf(md)

    result = client.post(f"/rest/api/3/issue/{args.issue}/worklog", body) or {}
    print(f"Logged worklog id={result.get('id')} on {args.issue}: {args.time_spent} on {body['started'][:10]}")


if __name__ == "__main__":
    main()
