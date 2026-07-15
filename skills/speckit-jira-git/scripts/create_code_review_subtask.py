"""Create one canonically named Code Review sub-task.

This compatibility helper delegates naming and identity defaults to the same
configuration used by ``standard-tasks``. New workflows should prefer:

    speckit-jira-git standard-tasks --parent PROJ-100 \
        --kinds code-review --round 1 --assignee "Reviewer Name"
"""
from __future__ import annotations

import argparse
import json
import sys

from discover_project_metadata import _cache_path, discover
from jira_client import JiraClient
from workflow_config import load_workflow_config
from workflow_manifest import standard_task_position, standard_task_title


def main() -> None:
    parser = argparse.ArgumentParser(description="Create one Code Review sub-task")
    parser.add_argument("--parent", required=True, help="Parent story key, e.g. PROJ-100")
    parser.add_argument("--assignee", default="", help="Jira display name of the engineer assigned to resolve review findings")
    parser.add_argument("--reviewer", default="", help=argparse.SUPPRESS)
    parser.add_argument("--round", type=int, default=1, help="Code review round number")
    parser.add_argument("--estimate", default="3h", help='Original estimate, e.g. "3h"')
    parser.add_argument("--pr-url", default="", help="Optional implementation PR URL")
    parser.add_argument("--summary", default="", help="Optional explicit summary override")
    parser.add_argument("--priority", default="Medium", help='Priority name (default: "Medium")')
    parser.add_argument("--config", default="", help="Optional .speckit-jira-git.toml path")
    args = parser.parse_args()

    try:
        config = load_workflow_config(args.config or None)
        position = standard_task_position("code-review", args.round)
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    if args.reviewer:
        print("WARNING: --reviewer is deprecated; use --assignee.", file=sys.stderr)
    assignee_name = (args.assignee or args.reviewer or config.default_assignee).strip()
    if not assignee_name:
        raise SystemExit("ERROR: --assignee or assignment.default_assignee is required")

    client = JiraClient()
    cache = _cache_path(client.config.project)
    if cache.exists():
        metadata = json.loads(cache.read_text(encoding="utf-8"))
    else:
        metadata = discover(client)
        cache.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    subtask_type_id = metadata.get("subtask_type_id")
    if not subtask_type_id:
        raise SystemExit("ERROR: could not determine Jira sub-task issue type; run discover-project --refresh")

    account_id = client.find_user_account_id(assignee_name)
    if not account_id:
        raise SystemExit(f"ERROR: could not resolve assignee '{assignee_name}' to a Jira accountId")

    summary = args.summary or standard_task_title(
        "code-review", f"Code Review Round {args.round}", args.round
    )
    description = JiraClient.adf_doc(
        [
            JiraClient.adf_heading("Objective", level=4),
            JiraClient.adf_para(
                "Resolve actionable implementation-review findings for the current parent-story scope."
            ),
            JiraClient.adf_heading("Required activities", level=5),
            JiraClient.adf_bullet_list(
                [
                    "Verify findings against the current head and target branch.",
                    "Implement scoped corrections and regression coverage.",
                    "Record validation evidence and remaining limitations.",
                ]
            ),
            JiraClient.adf_heading("Acceptance criteria", level=5),
            JiraClient.adf_bullet_list(
                [
                    "Each in-scope finding is resolved or answered with reproducible evidence.",
                    "Focused validation is recorded truthfully.",
                    "The issue status changes only when explicitly requested.",
                ]
            ),
            *(
                [JiraClient.adf_heading("Pull request", level=5), JiraClient.adf_para(args.pr_url)]
                if args.pr_url
                else []
            ),
        ]
    )
    fields = {
        "project": {"key": client.config.project},
        "issuetype": {"id": subtask_type_id},
        "summary": summary,
        "parent": {"key": args.parent},
        "assignee": {"accountId": account_id},
        "priority": {"name": args.priority},
        "timetracking": {"originalEstimate": args.estimate},
        "description": description,
        "labels": list(position.labels),
    }
    result = client.post("/rest/api/3/issue", {"fields": fields}) or {}
    issue_key = result.get("key")
    print(f"Created {issue_key} -> {client.config.url}/browse/{issue_key}")


if __name__ == "__main__":
    main()
