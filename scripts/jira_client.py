"""Shared Jira REST API v3 client for the speckit-to-jira skill.

Reads credentials and project key from environment variables. Falls back to
a project-local `.env` and `~/.jira/credentials.env` if `python-dotenv` is
available. The client never logs the token; it only reports whether each
required variable is set.

This module also exposes ADF (Atlassian Document Format) helpers used by
every script in the skill that posts a comment, description, or worklog body.
"""
from __future__ import annotations

import os
import sys
import base64
import json
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Credentials load order (highest priority first):
#   1. Variables already set in the running shell environment
#   2. `.env` at the current working directory or any parent directory
#      (resolved via python-dotenv's `find_dotenv()`)
#   3. `~/.jira/credentials.env` (fallback for users who prefer a single
#      machine-wide credentials file)
#
# The skill expects most users to keep credentials in a project-root `.env`.
# Run scripts from inside the project repo and `find_dotenv()` discovers it
# automatically; no other configuration needed.
def _load_env_file(path: Path) -> None:
    """Minimal dotenv fallback for KEY=VALUE lines."""

    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


try:
    from dotenv import find_dotenv, load_dotenv

    project_dotenv = find_dotenv(usecwd=True)
    if project_dotenv:
        load_dotenv(project_dotenv, override=False)
    load_dotenv(
        Path("~/.jira/credentials.env").expanduser(), override=False
    )
except ImportError:
    current = Path.cwd()
    for parent in [current, *current.parents]:
        candidate = parent / ".env"
        if candidate.exists():
            _load_env_file(candidate)
            break
    _load_env_file(Path("~/.jira/credentials.env").expanduser())


REQUIRED_ENV = ("JIRA_URL", "JIRA_EMAIL", "JIRA_TOKEN", "JIRA_PROJECT")


class JiraConfig:
    """Tenant configuration. Reads from env, validates presence, never echoes the token."""

    def __init__(self) -> None:
        self.url = os.getenv("JIRA_URL", "").rstrip("/")
        self.email = os.getenv("JIRA_EMAIL", "")
        self.token = os.getenv("JIRA_TOKEN", "")
        self.project = os.getenv("JIRA_PROJECT", "")

        missing = [k for k in REQUIRED_ENV if not os.getenv(k)]
        if missing:
            sys.stderr.write(
                "ERROR: missing required env vars: "
                + ", ".join(missing)
                + "\nSet them in the running shell, in ./.env, or in "
                "~/.jira/credentials.env. See the SKILL.md \"Pre-flight: "
                "environment\" section for details.\n"
            )
            sys.exit(2)


class JiraClient:
    """Minimal Jira Cloud REST client. One method per HTTP verb plus ADF helpers."""

    def __init__(self, config: JiraConfig | None = None) -> None:
        self.config = config or JiraConfig()
        raw_auth = f"{self.config.email}:{self.config.token}".encode("utf-8")
        self.auth_header = "Basic " + base64.b64encode(raw_auth).decode("ascii")
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": self.auth_header,
        }

    # ------------------------------------------------------------------ HTTP

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.config.url}{path}"

    def _request(self, method: str, path: str, payload: dict | None = None, params: dict | None = None) -> Any:
        url = self._url(path)
        if params:
            url += "?" + urlencode(params)
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = Request(url, data=body, headers=self.headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read()
                if response.status == 204 or not content:
                    return None
                return json.loads(content.decode("utf-8"))
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{exc.code} from {method} {path}: {error_body[:500]}") from exc

    def get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def post(self, path: str, payload: dict | None = None) -> Any:
        return self._request("POST", path, payload=payload)

    def put(self, path: str, payload: dict | None = None) -> Any:
        return self._request("PUT", path, payload=payload)

    def delete(self, path: str) -> None:
        self._request("DELETE", path)

    # ----------------------------------------------------------- Convenience

    def whoami(self) -> dict:
        return self.get("/rest/api/3/myself")

    def search_jql(self, jql: str, fields: list[str], max_results: int = 50) -> list[dict]:
        body = {"jql": jql, "fields": fields, "maxResults": max_results}
        data = self.post("/rest/api/3/search/jql", body) or {}
        return data.get("issues", [])

    def find_user_account_id(self, query: str) -> str | None:
        """Resolve a display name or email fragment to an accountId.
        Returns the first exact display-name match if any, else the first hit.
        """
        users = self.get("/rest/api/3/user/search", params={"query": query, "maxResults": 10}) or []
        if not users:
            return None
        exact = next(
            (u for u in users if u.get("displayName", "").lower() == query.lower()),
            None,
        )
        return (exact or users[0]).get("accountId")

    # ----------------------------------------------------------------- ADF

    @staticmethod
    def adf_doc(blocks: list[dict]) -> dict:
        """Wrap a list of ADF block nodes into a top-level doc."""
        return {"type": "doc", "version": 1, "content": blocks}

    @staticmethod
    def adf_para(text: str) -> dict:
        return {"type": "paragraph", "content": [{"type": "text", "text": text}]}

    @staticmethod
    def adf_heading(text: str, level: int = 3) -> dict:
        return {
            "type": "heading",
            "attrs": {"level": level},
            "content": [{"type": "text", "text": text}],
        }

    @staticmethod
    def adf_bullet_list(items: list[str]) -> dict:
        return {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [
                        {"type": "paragraph", "content": [{"type": "text", "text": x}]}
                    ],
                }
                for x in items
            ],
        }

    @staticmethod
    def adf_code_block(text: str) -> dict:
        """Create a Jira ADF code block for fixed-width status cards."""

        return {
            "type": "codeBlock",
            "attrs": {"language": "text"},
            "content": [{"type": "text", "text": text}],
        }

    @staticmethod
    def adf_simple(text: str) -> dict:
        """Single-paragraph ADF doc from a plain string."""
        return JiraClient.adf_doc([JiraClient.adf_para(text)])
