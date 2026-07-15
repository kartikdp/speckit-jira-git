"""Parse a Spec Kit `tasks.md` into a phase list (JSON on stdout).

Designed for the format produced by `/speckit-tasks`: each phase begins with
`## Phase N: <title>`, has optional `**Purpose**:` / `**Goal**:` /
`**Independent Test**:` / `**Checkpoint**:` lines, followed by a checklist of
`- [ ] T0NN [P?] [USn?] description` items.

Usage:
    python parse_tasks_md.py path/to/tasks.md > phases.json
    python parse_tasks_md.py path/to/tasks.md --pretty
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from workflow_manifest import normalize_phases


PHASE_HEADER_RE = re.compile(r"^## Phase (\d+):\s*(.+?)$", re.MULTILINE)
META_RE = {
    "purpose": re.compile(r"^\*\*Purpose\*\*:\s*(.+)$", re.MULTILINE),
    "goal": re.compile(r"^\*\*Goal\*\*:\s*(.+)$", re.MULTILINE),
    "independent_test": re.compile(r"^\*\*Independent Test\*\*:\s*(.+)$", re.MULTILINE),
    "checkpoint": re.compile(r"^\*\*Checkpoint\*\*:\s*(.+)$", re.MULTILINE),
}
TASK_LINE_RE = re.compile(
    r"^- \[[ xX]\] (T\d+[A-Za-z]*)((?:\s*\[[^\]]+\])*)\s+(.+)$",
    re.MULTILINE,
)


def parse_phases(text: str) -> list[dict]:
    """Return ordered list of phase dicts: num, title, meta, tasks."""
    headers = list(PHASE_HEADER_RE.finditer(text))
    phases: list[dict] = []
    for i, m in enumerate(headers):
        num = int(m.group(1))
        title = m.group(2).strip()
        body_start = m.end()
        body_end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
        body = text[body_start:body_end]

        meta: dict[str, str] = {}
        for key, regex in META_RE.items():
            mm = regex.search(body)
            meta[key] = mm.group(1).strip() if mm else ""

        # Stop at the next horizontal rule so we don't pick up tasks from the
        # next section if one phase forgot to add one.
        body_for_tasks = re.split(r"^---\s*$", body, maxsplit=1, flags=re.MULTILINE)[0]

        tasks: list[dict] = []
        for tm in TASK_LINE_RE.finditer(body_for_tasks):
            tasks.append(
                {
                    "id": tm.group(1),
                    "tags": tm.group(2).strip(),
                    "desc": tm.group(3).strip(),
                }
            )

        phases.append(
            {
                "num": num,
                "title": title,
                "meta": meta,
                "tasks": tasks,
            }
        )
    try:
        return normalize_phases(phases)
    except ValueError as exc:
        raise ValueError(f"invalid tasks.md phase sequence: {exc}") from exc


def derive_per_phase_estimate(text: str) -> dict[int, str]:
    """If the tasks.md has an "Estimated Effort Breakdown" markdown table at
    the bottom, extract per-phase original estimates as Jira time strings.

    The table format produced by the speckit templates is:

        | Phase | Tasks | Estimate |
        |-------|-------|----------|
        | Setup | T001-T002 | 15 min |
        | Foundational | T003-T007 | 30 min |
        | US1 backend | T008-T018 | 5h |
        | ...

    Phase numbers aren't always in the table, so this function returns a map
    keyed by 1-based row order. Empty dict if no table is found.
    """
    out: dict[int, str] = {}
    lines = text.splitlines()
    in_table = False
    rows = 0
    for raw in lines:
        line = raw.strip()
        if "Estimated Effort Breakdown" in line:
            in_table = True
            continue
        if in_table and line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if not cells or cells[0].lower() in ("phase", "") or set("-:") >= set(cells[0]):
                continue
            # data row
            if len(cells) >= 3:
                est = cells[-1].replace(" min", "m").replace(" h", "h").replace(" hr", "h")
                rows += 1
                out[rows] = est
        elif in_table and not line.startswith("|") and line:
            break  # table ended
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse a Spec Kit tasks.md")
    ap.add_argument("tasks_md", help="Path to tasks.md")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    ap.add_argument(
        "--with-estimates",
        action="store_true",
        help="Also try to derive per-phase estimates from the Effort Breakdown table",
    )
    args = ap.parse_args()

    path = Path(args.tasks_md)
    if not path.exists():
        sys.stderr.write(f"ERROR: tasks.md not found at {path}\n")
        sys.exit(2)

    text = path.read_text(encoding="utf-8")
    try:
        phases = parse_phases(text)
    except ValueError as exc:
        sys.stderr.write(f"ERROR: {exc}\n")
        sys.exit(2)

    if args.with_estimates:
        estimates = derive_per_phase_estimate(text)
        for i, phase in enumerate(phases, start=1):
            if i in estimates:
                phase["original_estimate"] = estimates[i]

    out = {"phases": phases, "source": str(path)}
    print(json.dumps(out, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
