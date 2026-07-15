"""Transition a Jira issue to a named status (e.g. "Done", "In Progress").

Usage:
    python transition_issue.py --issue PROJ-100 --to Done
    python transition_issue.py --issue PROJ-100 --to "In Progress"
    python transition_issue.py --issue PROJ-100 --list

The script discovers the transition id by name on each call (transition ids
can vary across issue types and are cheap to look up).
"""
from __future__ import annotations

import argparse
import sys

from jira_client import JiraClient


def _list_transitions(client: JiraClient, issue: str) -> None:
    data = client.get(f"/rest/api/3/issue/{issue}/transitions") or {}
    print(f"Available transitions for {issue}:")
    for t in data.get("transitions", []):
        print(f"  id={t['id']:>4}  name={t['name']!r:25}  to={t['to']['name']!r}")


def _transition_id_for(client: JiraClient, issue: str, name: str) -> str | None:
    data = client.get(f"/rest/api/3/issue/{issue}/transitions") or {}
    target = name.strip().lower()
    for t in data.get("transitions", []):
        if t.get("name", "").lower() == target:
            return t["id"]
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Transition a Jira issue by status name")
    ap.add_argument("--issue", required=True)
    ap.add_argument("--to", help='Target status name, e.g. "Done"')
    ap.add_argument(
        "--list",
        action="store_true",
        help="List available transitions for the issue and exit",
    )
    args = ap.parse_args()

    client = JiraClient()

    if args.list:
        _list_transitions(client, args.issue)
        return

    if not args.to:
        sys.exit("--to is required unless --list is passed")

    tid = _transition_id_for(client, args.issue, args.to)
    if not tid:
        _list_transitions(client, args.issue)
        sys.exit(f"\nNo transition named {args.to!r} on {args.issue}.")

    client.post(
        f"/rest/api/3/issue/{args.issue}/transitions",
        {"transition": {"id": tid}},
    )
    print(f"Transitioned {args.issue} -> {args.to} (transition id {tid})")


if __name__ == "__main__":
    main()
