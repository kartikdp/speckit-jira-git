"""Create a Code Review sub-task under a parent story.

Mirrors a common team pattern: a sub-task titled "Code Review" under the
parent story, assigned to the named reviewer, with a fixed estimate. The PR
URL goes into the description so the reviewer has a one-click handoff.

Usage:
    python create_code_review_subtask.py --parent PROJ-100 --reviewer "Reviewer Name" \\
        --estimate 3h --pr-url https://github.com/<org>/<repo>/pull/<num>
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jira_client import JiraClient
from discover_project_metadata import discover, _cache_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Create a Code Review sub-task")
    ap.add_argument("--parent", required=True, help="Parent story key, e.g. PROJ-100")
    ap.add_argument("--reviewer", required=True, help="Reviewer display name")
    ap.add_argument("--estimate", default="3h", help='Original estimate, e.g. "3h"')
    ap.add_argument("--pr-url", default=None, help="Optional PR URL for the description")
    ap.add_argument(
        "--summary",
        default="Code Review",
        help='Sub-task summary (default: "Code Review")',
    )
    ap.add_argument(
        "--priority",
        default="Medium",
        help='Priority name (default "Medium")',
    )
    args = ap.parse_args()

    client = JiraClient()

    # Discover sub-task type id
    cache = _cache_path(client.config.project)
    if cache.exists():
        meta = json.loads(cache.read_text())
    else:
        meta = discover(client)
        cache.write_text(json.dumps(meta, indent=2))
    subtask_type_id = meta.get("subtask_type_id")
    if not subtask_type_id:
        sys.exit(
            "Could not determine sub-task issue type id. Run "
            "discover_project_metadata.py --refresh."
        )

    # Resolve reviewer accountId
    account_id = client.find_user_account_id(args.reviewer)
    if not account_id:
        sys.exit(f"Could not resolve reviewer '{args.reviewer}' to an accountId.")

    # Build description
    desc_lines = []
    if args.pr_url:
        desc_lines.append(f"PR: {args.pr_url}")
    desc_lines.append(f"Code review for parent story {args.parent}.")
    description = JiraClient.adf_simple(" ".join(desc_lines))

    fields = {
        "project": {"key": client.config.project},
        "issuetype": {"id": subtask_type_id},
        "summary": args.summary,
        "parent": {"key": args.parent},
        "assignee": {"accountId": account_id},
        "priority": {"name": args.priority},
        "timetracking": {"originalEstimate": args.estimate},
        "description": description,
    }

    result = client.post("/rest/api/3/issue", {"fields": fields}) or {}
    new_key = result.get("key")
    print(f"Created {new_key}  ->  {client.config.url}/browse/{new_key}")


if __name__ == "__main__":
    main()
