"""Create standard Jira sub-tasks for planning, specs, review, and PR work."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from jira_client import JiraClient


TASK_TEMPLATES = {
    "specs-generation": ("Specs Generation", "Generate or update Spec Kit specification artifacts."),
    "specs-review": ("Specs Review", "Review specification, plan, task split, and acceptance criteria."),
    "clarification-round": ("Clarification Round {round}", "Resolve open questions and update Jira/spec artifacts."),
    "code-review": ("Code Review Round {round}", "Review implementation changes and record outcome."),
    "pr-review": ("PR Review", "Review pull request and verify checks, scope, and Jira linkage."),
    "fe-pr-review": ("FE PR Review", "Review frontend pull request, UX impact, and UI test evidence."),
    "be-pr-review": ("BE PR Review", "Review backend pull request, contracts, migrations, and test evidence."),
}


@dataclass(frozen=True)
class CreatedTask:
    key: str | None
    summary: str
    created: bool
    reason: str = ""


def _subtask_type_id(client: JiraClient) -> str:
    issue_types = client.get("/rest/api/3/issuetype") or []
    for issue_type in issue_types:
        if issue_type.get("subtask") and issue_type.get("name") in {"Sub-task", "Subtask"}:
            return issue_type["id"]
    raise SystemExit("ERROR: no Sub-task issue type found in Jira tenant")


def _existing_by_summary(client: JiraClient, parent: str, summaries: list[str]) -> dict[str, str]:
    if not summaries:
        return {}
    escaped = [s.replace('"', '\\"') for s in summaries]
    quoted = ", ".join(f'"{s}"' for s in escaped)
    jql = f'parent = {parent} AND summary in ({quoted})'
    issues = client.search_jql(jql, fields=["summary"], max_results=max(50, len(summaries)))
    return {issue["fields"]["summary"]: issue["key"] for issue in issues}


def _description(client: JiraClient, label: str, purpose: str, pr_url: str | None) -> dict:
    lines = [
        client.adf_heading(label, level=4),
        client.adf_para(purpose),
    ]
    if pr_url:
        lines.append(client.adf_para(f"PR: {pr_url}"))
    return client.adf_doc(lines)


def _summary(kind: str, round_label: str, prefix: str) -> str:
    title = TASK_TEMPLATES[kind][0].format(round=round_label or "1")
    return f"{prefix}{title}" if prefix else title


def main() -> None:
    parser = argparse.ArgumentParser(description="Create standard planning/review Jira sub-tasks")
    parser.add_argument("--parent", required=True, help="Parent Jira issue key")
    parser.add_argument(
        "--kinds",
        required=True,
        help="Comma-separated kinds: specs-generation,specs-review,clarification-round,code-review,pr-review,fe-pr-review,be-pr-review",
    )
    parser.add_argument("--round", default="1", help="Round number for round-based task names")
    parser.add_argument("--reviewer", default="", help="Assignee display name")
    parser.add_argument("--estimate", default="", help='Original estimate, e.g. "3h"')
    parser.add_argument("--priority", default="", help="Optional Jira priority name")
    parser.add_argument("--pr-url", default="", help="Optional pull request URL")
    parser.add_argument("--prefix", default="", help="Optional summary prefix")
    parser.add_argument("--allow-duplicates", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    kinds = [kind.strip() for kind in args.kinds.split(",") if kind.strip()]
    unknown = [kind for kind in kinds if kind not in TASK_TEMPLATES]
    if unknown:
        raise SystemExit(f"ERROR: unknown task kinds: {', '.join(unknown)}")

    client = JiraClient()
    subtask_type_id = _subtask_type_id(client)
    assignee = client.find_user_account_id(args.reviewer) if args.reviewer else None
    summaries = [_summary(kind, args.round, args.prefix) for kind in kinds]
    existing = {} if args.allow_duplicates else _existing_by_summary(client, args.parent, summaries)

    results: list[CreatedTask] = []
    for kind, summary in zip(kinds, summaries, strict=True):
        if summary in existing:
            results.append(CreatedTask(key=existing[summary], summary=summary, created=False, reason="duplicate"))
            continue
        label, purpose = TASK_TEMPLATES[kind]
        fields = {
            "project": {"key": client.config.project},
            "issuetype": {"id": subtask_type_id},
            "summary": summary,
            "parent": {"key": args.parent},
            "description": _description(client, label.format(round=args.round), purpose, args.pr_url or None),
        }
        if assignee:
            fields["assignee"] = {"accountId": assignee}
        if args.estimate:
            fields["timetracking"] = {"originalEstimate": args.estimate}
        if args.priority:
            fields["priority"] = {"name": args.priority}
        if args.dry_run:
            results.append(CreatedTask(key=None, summary=summary, created=False, reason="dry-run"))
            continue
        result = client.post("/rest/api/3/issue", {"fields": fields}) or {}
        results.append(CreatedTask(key=result.get("key"), summary=summary, created=True))

    payload = {"results": [result.__dict__ for result in results]}
    print(json.dumps(payload, indent=2) if args.json else "\n".join(str(r) for r in results))


if __name__ == "__main__":
    main()
