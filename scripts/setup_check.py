"""Validate local Jira and GitHub setup for speckit-jira-git."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from jira_client import JiraClient


def _masked(name: str) -> dict:
    value = os.getenv(name, "")
    return {"name": name, "set": bool(value), "preview": "***" if value and "TOKEN" in name else value}


def _gh_status() -> dict:
    token_set = bool(os.getenv("GITHUB_TOKEN"))
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except Exception as exc:
        return {"github_token_set": token_set, "gh_available": False, "error": str(exc)}
    return {
        "github_token_set": token_set,
        "gh_available": True,
        "gh_status_code": result.returncode,
        "gh_status": result.stdout.strip() or result.stderr.strip(),
    }


def _dotenv_candidates() -> list[str]:
    paths = []
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            paths.append(str(candidate))
            break
    home = Path("~/.jira/credentials.env").expanduser()
    if home.exists():
        paths.append(str(home))
    return paths


def _recommended_credentials_file() -> str:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            return str(candidate)
    return str(Path("~/.jira/credentials.env").expanduser())


def main() -> None:
    parser = argparse.ArgumentParser(description="Check Jira/GitHub credentials and local dependencies")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result = {
        "dotenv_candidates": _dotenv_candidates(),
        "recommended_credentials_file": _recommended_credentials_file(),
        "credential_note": (
            "For agent workflows, update the recommended credentials file. "
            "Exports in another terminal are not visible to this process."
        ),
        "env": [_masked(name) for name in ["JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJECT", "GITHUB_TOKEN"]],
        "jira": {},
        "github": _gh_status(),
    }
    try:
        client = JiraClient()
        myself = client.whoami()
        result["jira"] = {
            "ok": True,
            "url": client.config.url,
            "project": client.config.project,
            "displayName": myself.get("displayName"),
            "accountId": myself.get("accountId"),
        }
    except SystemExit:
        result["jira"] = {"ok": False, "error": "missing required Jira environment variables"}
    except Exception as exc:
        result["jira"] = {"ok": False, "error": str(exc)}

    if args.json:
        print(json.dumps(result, indent=2))
        return
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
