"""Build a /rest/api/3/issue/bulk payload from a Spec Kit tasks.md.

Reads the parent story key, walks each phase in tasks.md, and emits one
sub-task per phase with:

- Project key from JIRA_PROJECT (auto-detected via JiraClient)
- Sub-task issue type id from the discovery cache
- Parent set to the user-supplied key
- ADF description with Purpose / Goal / Independent Test / Checkpoint /
  task checklist
- Labels: ["speckit-phase", "phase-N"], plus optional --extra-label values
- Optional `timetracking.originalEstimate` from per-phase estimates passed
  via --estimates "phase-num=time-string,phase-num=time-string,..." or from
  the Effort Breakdown table inside tasks.md (--from-table flag).

Writes both:
- `<output>.json` with the bulk-create body
- `<output>.md`   with a human-readable preview

The script does NOT call Jira. Push with `push_subtasks.py` after the user
has reviewed the preview.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from jira_client import JiraClient
from parse_tasks_md import derive_per_phase_estimate, parse_phases
from discover_project_metadata import discover, _cache_path
from workflow_manifest import phase_position, phase_title


def _truncate(text: str, n: int = 240) -> str:
    flat = " ".join(text.split())
    return flat if len(flat) <= n else flat[: n - 1].rstrip() + "…"


def _adf_for_phase(phase: dict, source_path: str, summary: str) -> dict:
    blocks = [
        JiraClient.adf_para(f"Source: {source_path}"),
    ]
    for key, label in (
        ("purpose", "Purpose"),
        ("goal", "Goal"),
        ("independent_test", "Independent Test"),
        ("checkpoint", "Checkpoint"),
    ):
        v = phase["meta"].get(key, "")
        if v:
            blocks.append(JiraClient.adf_heading(label, level=4))
            blocks.append(JiraClient.adf_para(v))

    blocks.append(JiraClient.adf_heading(f"Tasks ({len(phase['tasks'])})", level=4))
    if phase["tasks"]:
        blocks.append(
            JiraClient.adf_bullet_list(
                [
                    f"{t['id']}{(' ' + t['tags']) if t['tags'] else ''}: {_truncate(t['desc'])}"
                    for t in phase["tasks"]
                ]
            )
        )
    blocks.append(
        JiraClient.adf_para(
            "Full task descriptions, dependencies, and parallel-execution map "
            "live in the source tasks.md. This sub-task tracks the phase-level "
            "checkpoint; T-IDs are reference markers, not separate Jira tickets."
        )
    )
    return JiraClient.adf_doc(blocks)


def _parse_estimate_arg(arg: str | None) -> dict[int, str]:
    if not arg:
        return {}
    out: dict[int, str] = {}
    for chunk in arg.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" not in chunk:
            raise SystemExit(f"--estimates entry '{chunk}' missing '='")
        k, v = chunk.split("=", 1)
        out[int(k)] = v.strip()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate /issue/bulk payload from tasks.md")
    ap.add_argument("--tasks", required=True, help="Path to tasks.md")
    ap.add_argument("--parent", required=True, help="Parent story Jira key (e.g. PROJ-100)")
    ap.add_argument("--output", required=True, help="Path for the JSON payload (e.g. exports/foo-payload.json)")
    ap.add_argument(
        "--summary-prefix",
        default=None,
        help="Optional text inserted before each implementation-phase title",
    )
    ap.add_argument(
        "--extra-label",
        action="append",
        default=[],
        help="Additional label to attach to every sub-task; repeatable",
    )
    ap.add_argument(
        "--estimates",
        default=None,
        help='Per-phase originalEstimate map, e.g. "1=15m,2=30m,3=5h"',
    )
    ap.add_argument(
        "--from-table",
        action="store_true",
        help="Derive estimates from the 'Estimated Effort Breakdown' table in tasks.md",
    )
    args = ap.parse_args()

    tasks_path = Path(args.tasks)
    if not tasks_path.exists():
        raise SystemExit(f"tasks.md not found at {tasks_path}")

    text = tasks_path.read_text(encoding="utf-8")
    try:
        phases = parse_phases(text)
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    if not phases:
        raise SystemExit("No phases found. Expected `## Phase N: Title` headings.")

    # Resolve estimates
    explicit = _parse_estimate_arg(args.estimates)
    table_estimates = derive_per_phase_estimate(text) if args.from_table else {}

    # Discover sub-task issue type id (cached)
    client = JiraClient()
    cache = _cache_path(client.config.project)
    if cache.exists():
        meta = json.loads(cache.read_text())
    else:
        meta = discover(client)
        cache.write_text(json.dumps(meta, indent=2))
    subtask_type_id = meta.get("subtask_type_id")
    if not subtask_type_id:
        raise SystemExit(
            "Could not determine sub-task issue type id. Run "
            "discover_project_metadata.py --refresh and check Jira project config."
        )

    # Build issueUpdates
    issue_updates: list[dict] = []
    md_lines: list[str] = [
        f"# Sub-task payload preview\n",
        f"Parent: `{args.parent}`",
        f"Project: `{client.config.project}`",
        f"Sub-task type id: `{subtask_type_id}`",
        f"Total: {len(phases)}",
        "",
    ]
    for p in phases:
        phase_num = p["num"]
        title = p["title"]
        label = f"{args.summary_prefix}{title}" if args.summary_prefix else title
        summary = phase_title(phase_num, label)
        if len(summary) > 240:
            summary = summary[:237] + "..."

        labels = [
            "speckit-phase",
            f"phase-{phase_num}",
            *phase_position(phase_num).labels,
            *args.extra_label,
        ]

        fields: dict = {
            "project": {"key": client.config.project},
            "issuetype": {"id": subtask_type_id},
            "summary": summary,
            "description": _adf_for_phase(p, str(tasks_path), summary),
            "parent": {"key": args.parent},
            "labels": labels,
        }
        est = explicit.get(phase_num) or table_estimates.get(phase_num)
        if est:
            fields["timetracking"] = {"originalEstimate": est}
        issue_updates.append({"fields": fields})

        md_lines.append(f"## {summary}")
        if est:
            md_lines.append(f"- Original estimate: {est}")
        md_lines.append(f"- Labels: {', '.join(labels)}")
        md_lines.append(f"- Tasks ({len(p['tasks'])}):")
        for t in p["tasks"]:
            md_lines.append(
                f"  - `{t['id']}`{(' ' + t['tags']) if t['tags'] else ''} "
                f"{_truncate(t['desc'], 200)}"
            )
        md_lines.append("")

    out_json = Path(args.output)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps({"issueUpdates": issue_updates}, indent=2))

    out_md = out_json.with_suffix(".md")
    out_md.write_text("\n".join(md_lines))

    print(f"Wrote {out_json}")
    print(f"Wrote {out_md}")
    print(f"Sub-tasks: {len(issue_updates)}")


if __name__ == "__main__":
    main()
