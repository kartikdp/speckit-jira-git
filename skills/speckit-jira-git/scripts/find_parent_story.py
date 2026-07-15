"""Search Jira for a parent story by summary fragment.

Usage:
    python find_parent_story.py --query "user auth"
    python find_parent_story.py --query "user auth" --types Story Task

Prints matching issues as JSON. The user picks one and feeds the key into
generate_subtasks_payload.py.
"""
from __future__ import annotations

import argparse
import json

from jira_client import JiraClient


def main() -> None:
    ap = argparse.ArgumentParser(description="Find candidate parent stories in Jira")
    ap.add_argument("--query", required=True, help="Substring to match against summary")
    ap.add_argument(
        "--types",
        nargs="+",
        default=["Story", "Task"],
        help="Issue types to consider (default: Story Task)",
    )
    ap.add_argument("--max", type=int, default=10, help="Max results")
    args = ap.parse_args()

    client = JiraClient()
    project = client.config.project
    type_clause = " OR ".join([f'issuetype = "{t}"' for t in args.types])
    safe_query = args.query.replace('"', '\\"')
    jql = f'project = {project} AND ({type_clause}) AND summary ~ "{safe_query}"'

    issues = client.search_jql(
        jql,
        fields=["summary", "status", "issuetype", "parent"],
        max_results=args.max,
    )

    out = []
    for i in issues:
        f = i["fields"]
        out.append(
            {
                "key": i["key"],
                "summary": f.get("summary"),
                "type": (f.get("issuetype") or {}).get("name"),
                "status": (f.get("status") or {}).get("name"),
                "parent": (f.get("parent") or {}).get("key"),
            }
        )
    print(json.dumps({"query": args.query, "results": out}, indent=2))


if __name__ == "__main__":
    main()
