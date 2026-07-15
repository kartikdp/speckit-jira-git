"""Shared Jira REST API v3 client for the speckit-jira-git skill.

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
import mimetypes
import uuid
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
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
                "~/.jira/credentials.env. See references/setup.md for details.\n"
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

    def get_bytes(self, path_or_url: str) -> bytes:
        """Read Jira-hosted binary content without forwarding auth off-origin."""

        configured = urlparse(self.config.url)
        requested = urlparse(path_or_url)
        if requested.scheme or requested.netloc:
            def origin(value: Any) -> tuple[str, str | None, int | None]:
                scheme = value.scheme.lower()
                default_port = 443 if scheme == "https" else 80 if scheme == "http" else None
                return scheme, value.hostname, value.port or default_port

            configured_origin = origin(configured)
            requested_origin = origin(requested)
            if requested_origin != configured_origin:
                raise ValueError("refusing to send Jira credentials to another origin")
            url = path_or_url
        else:
            url = self._url(path_or_url)

        request = Request(url, headers={"Accept": "application/octet-stream"}, method="GET")
        # Jira may redirect attachment downloads to a signed media URL. Keep
        # credentials on the initial Jira request and never forward them.
        request.add_unredirected_header("Authorization", self.auth_header)
        try:
            with urlopen(request, timeout=60) as response:
                return response.read()
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"{exc.code} while reading Jira attachment: {error_body[:500]}"
            ) from exc

    def attach_file(self, issue_key: str, file_path: str | Path) -> dict:
        """Attach one local file to a Jira issue using the Cloud multipart API."""

        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise FileNotFoundError(f"attachment does not exist or is not a file: {path}")

        boundary = f"speckit-jira-git-{uuid.uuid4().hex}"
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        prefix = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
        body = prefix + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode("utf-8")
        headers = {
            "Accept": "application/json",
            "Authorization": self.auth_header,
            "X-Atlassian-Token": "no-check",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        endpoint = f"/rest/api/3/issue/{issue_key}/attachments"
        request = Request(self._url(endpoint), data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=60) as response:
                content = response.read()
                if not content:
                    return {}
                payload = json.loads(content.decode("utf-8"))
                return payload[0] if isinstance(payload, list) and payload else payload
        except HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"{exc.code} from POST {endpoint}: {error_body[:500]}"
            ) from exc

    # ----------------------------------------------------------- Convenience

    def whoami(self) -> dict:
        return self.get("/rest/api/3/myself")

    def search_jql(self, jql: str, fields: list[str], max_results: int = 50) -> list[dict]:
        body = {"jql": jql, "fields": fields, "maxResults": max_results}
        data = self.post("/rest/api/3/search/jql", body) or {}
        return data.get("issues", [])

    def search_jql_all(
        self,
        jql: str,
        fields: list[str],
        page_size: int = 100,
        max_total: int = 1000,
    ) -> list[dict]:
        """Read enhanced-search pages up to an explicit safety cap."""

        if page_size < 1 or max_total < 1:
            raise ValueError("page_size and max_total must be positive")
        issues: list[dict] = []
        next_page_token: str | None = None
        while len(issues) < max_total:
            body: dict[str, Any] = {
                "jql": jql,
                "fields": fields,
                "maxResults": min(page_size, max_total - len(issues)),
            }
            if next_page_token:
                body["nextPageToken"] = next_page_token
            data = self.post("/rest/api/3/search/jql", body) or {}
            page = data.get("issues", [])
            issues.extend(page)
            next_page_token = data.get("nextPageToken")
            if not next_page_token or not page:
                break
        return issues

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
