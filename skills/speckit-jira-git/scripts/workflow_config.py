"""Load non-secret, project-local speckit-jira-git preferences."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_NAME = ".speckit-jira-git.toml"
DEFAULT_STORY_TITLE_TEMPLATE = "{workstream} — {story_id} — {outcome}"


@dataclass(frozen=True)
class WorkflowConfig:
    reviewer: str = ""
    default_assignee: str = ""
    specs_reviewer: str = ""
    clarification_owner: str = ""
    pr_reviewer: str = ""
    story_title_template: str = DEFAULT_STORY_TITLE_TEMPLATE


def _find_config(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / CONFIG_NAME
        if candidate.is_file():
            return candidate
    return None


def _string(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{CONFIG_NAME}: {key} must be a string")
    return value.strip()


def load_workflow_config(path: str | Path | None = None) -> WorkflowConfig:
    """Load project preferences without credentials or personalized defaults."""

    config_path = Path(path).expanduser().resolve() if path else _find_config()
    if config_path is None:
        return WorkflowConfig()
    if not config_path.is_file():
        raise ValueError(f"configuration file does not exist: {config_path}")
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    identity = data.get("identity") or {}
    assignment = data.get("assignment") or {}
    titles = data.get("titles") or {}
    if not all(isinstance(section, dict) for section in (identity, assignment, titles)):
        raise ValueError(f"{CONFIG_NAME}: identity, assignment, and titles must be tables")
    template = _string(titles, "story") or DEFAULT_STORY_TITLE_TEMPLATE
    return WorkflowConfig(
        reviewer=_string(identity, "reviewer"),
        default_assignee=_string(assignment, "default_assignee"),
        specs_reviewer=_string(assignment, "specs_reviewer"),
        clarification_owner=_string(assignment, "clarification_owner"),
        pr_reviewer=_string(assignment, "pr_reviewer"),
        story_title_template=template,
    )
