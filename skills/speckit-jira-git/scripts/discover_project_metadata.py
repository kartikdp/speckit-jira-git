"""Discover tenant-specific Jira metadata and cache it locally.

Detects, for the current `JIRA_PROJECT`:

- Sub-task issue type ID (`subtask: true`)
- Default board ID for the project (first software board returned by Jira Agile)
- Active sprint id and name (if any)
- Done transition ID (queried against any sub-task; may differ for other types)

Cached at `~/.cache/speckit-jira-git/<JIRA_PROJECT>.json`. The cache is
intentionally shallow: only public IDs and names, no credentials.

Usage:
    python discover_project_metadata.py
    python discover_project_metadata.py --refresh
    python discover_project_metadata.py --print
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jira_client import JiraClient


def _cache_path(project_key: str) -> Path:
    base = Path("~/.cache/speckit-jira-git").expanduser()
    base.mkdir(parents=True, exist_ok=True)
    return base / f"{project_key}.json"


def discover(client: JiraClient | None = None) -> dict:
    client = client or JiraClient()
    project_key = client.config.project

    # Resolve issue types from the configured project. Jira Cloud can expose
    # multiple global "Sub-task" types, but only the type in the project's
    # issue-type scheme is valid when creating a child issue.
    project = client.get(f"/rest/api/3/project/{project_key}") or {}
    issue_types = project.get("issueTypes", [])
    subtask_type = next(
        (
            t
            for t in issue_types
            if t.get("subtask")
            and t.get("name", "").lower() in ("sub-task", "subtask")
        ),
        None,
    )
    subtask_type_id = subtask_type.get("id") if subtask_type else None

    # Board id (first software board for the project)
    boards = (
        client.get(
            "/rest/agile/1.0/board",
            params={"projectKeyOrId": project_key, "type": "scrum"},
        )
        or {}
    )
    board_values = boards.get("values", [])
    board = board_values[0] if board_values else None
    board_id = board.get("id") if board else None

    # Active sprint
    active_sprint = None
    if board_id is not None:
        try:
            sprints = (
                client.get(
                    f"/rest/agile/1.0/board/{board_id}/sprint",
                    params={"state": "active"},
                )
                or {}
            )
            sv = sprints.get("values", [])
            if sv:
                active_sprint = {
                    "id": sv[0].get("id"),
                    "name": sv[0].get("name"),
                }
        except Exception as exc:  # pragma: no cover - kanban boards return 400/404
            active_sprint = {"error": str(exc)[:100]}

    # Done transition id (query against any single issue we have access to)
    done_transition_id = None
    try:
        issues = client.search_jql(
            f"project = {project_key} AND statusCategory = Done",
            fields=["summary"],
            max_results=1,
        )
        if issues:
            sample_key = issues[0]["key"]
            transitions = (
                client.get(
                    f"/rest/api/3/issue/{sample_key}/transitions"
                )
                or {}
            )
            done_transition_id = next(
                (
                    t.get("id")
                    for t in transitions.get("transitions", [])
                    if t.get("name", "").lower() == "done"
                ),
                None,
            )
    except Exception:
        pass

    return {
        "project_key": project_key,
        "subtask_type_id": subtask_type_id,
        "board_id": board_id,
        "active_sprint": active_sprint,
        "done_transition_id": done_transition_id,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Discover Jira tenant metadata")
    ap.add_argument(
        "--refresh", action="store_true", help="Refresh cache even if it exists"
    )
    ap.add_argument(
        "--print", action="store_true", help="Print the cached metadata without refreshing"
    )
    args = ap.parse_args()

    client = JiraClient()
    cache = _cache_path(client.config.project)

    if args.print and cache.exists():
        sys.stdout.write(cache.read_text())
        return

    if cache.exists() and not args.refresh:
        data = json.loads(cache.read_text())
        sys.stdout.write(json.dumps(data, indent=2))
        sys.stdout.write("\n# (cached; pass --refresh to re-discover)\n")
        return

    data = discover(client)
    cache.write_text(json.dumps(data, indent=2))
    print(json.dumps(data, indent=2))
    print(f"# cached at {cache}")


if __name__ == "__main__":
    main()
