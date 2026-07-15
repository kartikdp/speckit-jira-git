"""Canonical ordering, titles, and labels for a Spec Kit Jira workflow."""
from __future__ import annotations

from dataclasses import dataclass


STAGE = {
    "specs-generation": 1,
    "specs-review": 2,
    "clarification-round": 3,
    "implementation-phase": 4,
    "code-review": 5,
    "be-pr-review": 6,
    "fe-pr-review": 6,
    "pr-review": 6,
}
PR_REVIEW_ORDER = {"be-pr-review": 1, "fe-pr-review": 2, "pr-review": 1}


@dataclass(frozen=True, order=True)
class WorkflowPosition:
    stage: int
    item: int

    @property
    def code(self) -> str:
        return f"{self.stage:02d}" if self.item == 0 else f"{self.stage:02d}.{self.item:02d}"

    @property
    def labels(self) -> tuple[str, str]:
        return (f"speckit-stage-{self.stage:02d}", f"speckit-sequence-{self.stage:02d}-{self.item:02d}")


def positive_number(value: str | int, label: str) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if number < 1:
        raise ValueError(f"{label} must be a positive integer")
    return number


def standard_task_position(kind: str, round_number: str | int = 1) -> WorkflowPosition:
    if kind not in STAGE or kind == "implementation-phase":
        raise ValueError(f"unsupported standard task kind: {kind}")
    stage = STAGE[kind]
    if kind in {"clarification-round", "code-review"}:
        item = positive_number(round_number, f"{kind} round")
    elif kind in PR_REVIEW_ORDER:
        item = PR_REVIEW_ORDER[kind]
    else:
        item = 0
    return WorkflowPosition(stage, item)


def standard_task_title(
    kind: str,
    label: str,
    round_number: str | int = 1,
    pr_number: int | None = None,
) -> str:
    position = standard_task_position(kind, round_number)
    suffix = f" — PR #{pr_number}" if kind in PR_REVIEW_ORDER and pr_number else ""
    return f"[{position.code}] {label}{suffix}"


def sort_standard_kinds(kinds: list[str], round_number: str | int = 1) -> list[str]:
    """Return unique kinds in canonical workflow order."""

    seen: set[str] = set()
    unique: list[str] = []
    for kind in kinds:
        if kind not in seen:
            seen.add(kind)
            unique.append(kind)
    if "pr-review" in seen and ({"be-pr-review", "fe-pr-review"} & seen):
        raise ValueError("use generic PR Review or repository-specific PR Reviews, not both")
    return sorted(unique, key=lambda kind: standard_task_position(kind, round_number))


def normalize_phases(phases: list[dict]) -> list[dict]:
    """Validate positive, unique, contiguous phase numbers and sort them."""

    if not phases:
        return []
    numbers = [positive_number(phase.get("num"), "phase number") for phase in phases]
    if len(set(numbers)) != len(numbers):
        raise ValueError("phase numbers must be unique")
    ordered = sorted(phases, key=lambda phase: int(phase["num"]))
    expected = list(range(1, len(ordered) + 1))
    actual = [int(phase["num"]) for phase in ordered]
    if actual != expected:
        raise ValueError(f"phase numbers must be contiguous from 1; found {actual}")
    return ordered


def phase_position(phase_number: int) -> WorkflowPosition:
    return WorkflowPosition(STAGE["implementation-phase"], positive_number(phase_number, "phase number"))


def phase_title(phase_number: int, title: str) -> str:
    position = phase_position(phase_number)
    return f"[{position.code}] Implementation Phase {phase_number} — {title.strip()}"


def format_story_title(template: str, workstream: str, story_id: str, outcome: str) -> str:
    values = {
        "workstream": workstream.strip(),
        "story_id": story_id.strip(),
        "outcome": outcome.strip(),
    }
    if not values["story_id"] or not values["outcome"]:
        raise ValueError("story_id and outcome are required")
    try:
        rendered = template.format(**values)
    except KeyError as exc:
        raise ValueError(f"unknown story-title placeholder: {exc.args[0]}") from exc
    parts = [part.strip() for part in rendered.split("—") if part.strip()]
    return " — ".join(parts)
