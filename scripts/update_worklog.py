"""Resize an existing worklog or move it to a different date.

All editable fields are optional; pass only the ones you want to change.

Usage:
    python update_worklog.py --issue PROJ-100 --worklog-id 17029 --time-spent 3h
    python update_worklog.py --issue PROJ-100 --worklog-id 17029 --started 2026-05-04
    python update_worklog.py --issue PROJ-100 --worklog-id 17029 \\
        --time-spent 7h --started 2026-05-04 --comment-file exports/new-note.md
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jira_client import JiraClient
from log_worklog import _started_iso
from markdown_to_adf import markdown_to_adf


def main() -> None:
    ap = argparse.ArgumentParser(description="Edit an existing worklog")
    ap.add_argument("--issue", required=True)
    ap.add_argument("--worklog-id", required=True)
    ap.add_argument("--time-spent", default=None)
    ap.add_argument("--started", default=None, help="YYYY-MM-DD")
    ap.add_argument("--hour", type=int, default=10)
    ap.add_argument("--comment-file", default=None)
    args = ap.parse_args()

    body: dict = {}
    if args.time_spent:
        body["timeSpent"] = args.time_spent
    if args.started:
        body["started"] = _started_iso(args.started, args.hour)
    if args.comment_file:
        md = Path(args.comment_file).read_text(encoding="utf-8")
        body["comment"] = markdown_to_adf(md)

    if not body:
        sys.exit("Nothing to update; pass --time-spent, --started, or --comment-file")

    client = JiraClient()
    client.put(
        f"/rest/api/3/issue/{args.issue}/worklog/{args.worklog_id}", body
    )
    parts = []
    if "timeSpent" in body:
        parts.append(f"timeSpent={body['timeSpent']}")
    if "started" in body:
        parts.append(f"started={body['started'][:10]}")
    if "comment" in body:
        parts.append("comment updated")
    print(f"Updated worklog {args.worklog_id} on {args.issue}: {'; '.join(parts)}")


if __name__ == "__main__":
    main()
