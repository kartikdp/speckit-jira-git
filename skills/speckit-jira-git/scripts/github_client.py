"""Small GitHub REST helper for speckit-jira-git scripts.

Authentication order:
1. GITHUB_TOKEN from the environment.
2. `gh auth token` from the GitHub CLI.

The helper covers the focused read operations needed to inspect PR/review
activity and the conversation-comment write used by structured push updates.
"""
from __future__ import annotations

import os
import re
import json
import subprocess
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.parse import urlencode
from urllib.request import Request, urlopen


PR_URL_RE = re.compile(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)")
ISSUE_COMMENT_URL_RE = re.compile(
    r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)#issuecomment-(?P<comment_id>\d+)"
)


@dataclass(frozen=True)
class PullRequestRef:
    """A normalized GitHub pull request reference."""

    owner: str
    repo: str
    number: int

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.repo}"


def _token_from_gh() -> str:
    try:
        result = subprocess.run(
            ["gh", "auth", "token"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return ""
    return result.stdout.strip()


def load_github_token() -> str:
    """Load a GitHub token without printing it."""

    return os.getenv("GITHUB_TOKEN", "").strip() or _token_from_gh()


def parse_pr_url(url: str) -> PullRequestRef:
    """Parse https://github.com/org/repo/pull/123 or git@ style PR URLs."""

    match = PR_URL_RE.search(url)
    if not match:
        raise ValueError(f"Not a GitHub pull request URL: {url}")
    return PullRequestRef(
        owner=match.group("owner"),
        repo=match.group("repo"),
        number=int(match.group("number")),
    )


def parse_issue_comment_url(url: str) -> tuple[PullRequestRef, int]:
    """Parse a GitHub PR issue-comment URL."""

    match = ISSUE_COMMENT_URL_RE.search(url)
    if not match:
        raise ValueError(f"Not a GitHub pull request issue-comment URL: {url}")
    return (
        PullRequestRef(
            owner=match.group("owner"),
            repo=match.group("repo"),
            number=int(match.group("number")),
        ),
        int(match.group("comment_id")),
    )


def repo_from_remote(remote_url: str) -> str | None:
    """Extract owner/repo from a Git remote URL."""

    if remote_url.startswith("git@"):
        path = remote_url.split(":", 1)[-1]
    else:
        parsed = urlparse(remote_url)
        path = parsed.path.lstrip("/")
    path = path.removesuffix(".git")
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return None


def current_repo() -> str | None:
    """Return owner/repo for the current git checkout, if discoverable."""

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return None
    return repo_from_remote(result.stdout.strip())


class GitHubClient:
    """Minimal GitHub REST client."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token if token is not None else load_github_token()
        if not self.token:
            sys.stderr.write(
                "ERROR: missing GitHub auth. Set GITHUB_TOKEN or run `gh auth login`.\n"
            )
            sys.exit(2)
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        if not path.startswith("/"):
            path = "/" + path
        url = f"https://api.github.com{path}"
        if params:
            url += "?" + urlencode(params)
        request = Request(url, headers=self.headers, method="GET")
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read()
                return json.loads(content.decode("utf-8")) if content else None
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{exc.code} from GET {path}: {body[:500]}") from exc

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        if not path.startswith("/"):
            path = "/" + path
        url = f"https://api.github.com{path}"
        headers = {**self.headers, "Content-Type": "application/json"}
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=30) as response:
                content = response.read()
                return json.loads(content.decode("utf-8")) if content else None
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{exc.code} from POST {path}: {body[:500]}") from exc

    def get_all(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        item_key: str | None = None,
        max_pages: int = 100,
    ) -> list[dict[str, Any]]:
        """Read every REST page for a list or a list nested under item_key."""

        collected: list[dict[str, Any]] = []
        base_params = dict(params or {})
        per_page = int(base_params.pop("per_page", 100))
        for page in range(1, max_pages + 1):
            payload = self.get(
                path,
                params={**base_params, "per_page": per_page, "page": page},
            )
            items = payload.get(item_key, []) if item_key and isinstance(payload, dict) else payload
            if not isinstance(items, list):
                raise RuntimeError(f"unexpected paginated response from GET {path}")
            collected.extend(items)
            if len(items) < per_page:
                return collected
        raise RuntimeError(f"pagination exceeded {max_pages} pages for GET {path}")

    def pull_request(self, ref: PullRequestRef) -> dict[str, Any]:
        return self.get(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}")

    def pull_request_commits(self, ref: PullRequestRef) -> list[dict[str, Any]]:
        return self.get_all(
            f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/commits",
        )

    def pull_request_reviews(self, ref: PullRequestRef) -> list[dict[str, Any]]:
        return self.get_all(
            f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/reviews",
        )

    def pull_request_comments(self, ref: PullRequestRef) -> list[dict[str, Any]]:
        return self.get_all(
            f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/comments",
        )

    def issue_comments(self, ref: PullRequestRef) -> list[dict[str, Any]]:
        return self.get_all(
            f"/repos/{ref.owner}/{ref.repo}/issues/{ref.number}/comments",
        )

    def issue_comment(self, ref: PullRequestRef, comment_id: int) -> dict[str, Any]:
        return self.get(
            f"/repos/{ref.owner}/{ref.repo}/issues/comments/{comment_id}",
        )

    def create_issue_comment(self, ref: PullRequestRef, body: str) -> dict[str, Any]:
        return self.post(
            f"/repos/{ref.owner}/{ref.repo}/issues/{ref.number}/comments",
            {"body": body},
        )

    def check_runs(self, ref: PullRequestRef, sha: str) -> list[dict[str, Any]]:
        return self.get_all(
            f"/repos/{ref.owner}/{ref.repo}/commits/{sha}/check-runs",
            item_key="check_runs",
        )
