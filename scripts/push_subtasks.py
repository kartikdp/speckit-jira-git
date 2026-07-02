"""Push a previously-generated bulk-create payload to Jira.

Reads the JSON written by `generate_subtasks_payload.py`. Supports:

- Pushing a single phase as a smoke test (`--phase 1`)
- Pushing all remaining phases (`--phases all`)
- Pushing a specific subset (`--phases 2,3,4`)

Always runs a duplicate-summary check first (Jira returns the existing keys
if the summaries already exist) so re-runs are idempotent.

Usage:
    python push_subtasks.py --payload exports/foo-payload.json --phase 1
    python push_subtasks.py --payload exports/foo-payload.json --phases all
    python push_subtasks.py --payload exports/foo-payload.json --phases 2,3,4
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from jira_client import JiraClient


PHASE_TAG_RE = re.compile(r"\[Phase\s+(\d+)\]", re.IGNORECASE)


def _phase_number(summary: str) -> int | None:
    m = PHASE_TAG_RE.search(summary)
    return int(m.group(1)) if m else None


def _check_duplicates(client: JiraClient, summaries: list[str]) -> dict[str, dict]:
    """Return {summary: {key, status}} for any summary that already exists."""
    if not summaries:
        return {}
    found: dict[str, dict] = {}
    chunk_size = 50
    for i in range(0, len(summaries), chunk_size):
        chunk = summaries[i : i + chunk_size]
        escaped = [s.replace('"', '\\"') for s in chunk]
        quoted = ", ".join(f'"{s}"' for s in escaped)
        jql = f"project = {client.config.project} AND summary in ({quoted})"
        for issue in client.search_jql(jql, fields=["summary", "status"], max_results=chunk_size):
            f = issue["fields"]
            found[f["summary"]] = {"key": issue["key"], "status": (f.get("status") or {}).get("name")}
    return found


def main() -> None:
    ap = argparse.ArgumentParser(description="Push bulk-create payload to Jira")
    ap.add_argument("--payload", required=True, help="JSON written by generate_subtasks_payload.py")
    ap.add_argument(
        "--phase",
        type=int,
        default=None,
        help="Push a single phase number (smoke test). Mutually exclusive with --phases.",
    )
    ap.add_argument(
        "--phases",
        default=None,
        help='"all" or comma-separated list, e.g. "2,3,4"',
    )
    ap.add_argument(
        "--allow-duplicates",
        action="store_true",
        help="Push even if a summary already exists in Jira (default: skip duplicates)",
    )
    args = ap.parse_args()

    if args.phase is not None and args.phases is not None:
        sys.exit("Pass either --phase or --phases, not both")

    payload_path = Path(args.payload)
    if not payload_path.exists():
        sys.exit(f"Payload not found at {payload_path}")
    payload = json.loads(payload_path.read_text())
    all_updates = payload["issueUpdates"]

    # Filter
    if args.phase is not None:
        wanted = [args.phase]
    elif args.phases == "all" or args.phases is None:
        wanted = None
    else:
        wanted = [int(p.strip()) for p in args.phases.split(",") if p.strip()]

    if wanted is None:
        selected = all_updates
    else:
        selected = []
        for u in all_updates:
            n = _phase_number(u["fields"]["summary"])
            if n is not None and n in wanted:
                selected.append(u)
        if not selected:
            sys.exit(f"No phases match selection {wanted}")

    summaries = [u["fields"]["summary"] for u in selected]

    print(f"Selected {len(selected)} sub-tasks to push:")
    for s in summaries:
        print(f"  - {s}")
    print()

    client = JiraClient()
    print("Checking for duplicate summaries...")
    dups = _check_duplicates(client, summaries)
    if dups:
        print(f"Already exist in {client.config.project}:")
        for s, info in dups.items():
            print(f"  {info['key']:14}  status={info['status']:10}  {s}")
        if not args.allow_duplicates:
            selected = [u for u in selected if u["fields"]["summary"] not in dups]
            if not selected:
                print("Nothing left to push (all selected sub-tasks already exist).")
                return
            print(f"Skipping {len(dups)} duplicates; will push {len(selected)} new.")
    else:
        print("No duplicates.")

    print()
    print("--- POST /rest/api/3/issue/bulk ---")
    result = client.post(
        "/rest/api/3/issue/bulk", {"issueUpdates": selected}
    ) or {}
    created = result.get("issues") or result.get("createdIssues") or []
    errors = result.get("errors", [])
    print(f"Created: {len(created)}    Errors: {len(errors)}")
    for c in created:
        print(f"  {c.get('key')}  ->  {client.config.url}/browse/{c.get('key')}")
    for e in errors:
        print(f"  ERROR: {e}")


if __name__ == "__main__":
    main()
