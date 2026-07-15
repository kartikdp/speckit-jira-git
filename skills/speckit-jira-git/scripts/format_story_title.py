"""Render a project-configured canonical Jira parent-story title."""
from __future__ import annotations

import argparse

from workflow_config import load_workflow_config
from workflow_manifest import format_story_title


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a canonical Jira story title")
    parser.add_argument("--story-id", required=True)
    parser.add_argument("--outcome", required=True)
    parser.add_argument("--workstream", default="")
    parser.add_argument("--template", default="")
    parser.add_argument("--config", default="")
    args = parser.parse_args()
    try:
        config = load_workflow_config(args.config or None)
        template = args.template or config.story_title_template
        print(format_story_title(template, args.workstream, args.story_id, args.outcome))
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
