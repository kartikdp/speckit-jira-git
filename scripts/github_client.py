"""Small GitHub REST helper for speckit-jira-git scripts.

Authentication order:
1. GITHUB_TOKEN from the environment.
2. `gh auth token` from the GitHub CLI.

The helper intentionally covers only read operations needed to turn PR and
review activity into Jira comments.
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

    def pull_request(self, ref: PullRequestRef) -> dict[str, Any]:
        return self.get(f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}")

    def pull_request_commits(self, ref: PullRequestRef) -> list[dict[str, Any]]:
        return self.get(
            f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/commits",
            params={"per_page": 100},
        )

    def pull_request_reviews(self, ref: PullRequestRef) -> list[dict[str, Any]]:
        return self.get(
            f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/reviews",
            params={"per_page": 100},
        )

    def pull_request_comments(self, ref: PullRequestRef) -> list[dict[str, Any]]:
        return self.get(
            f"/repos/{ref.owner}/{ref.repo}/pulls/{ref.number}/comments",
            params={"per_page": 100},
        )

    def issue_comments(self, ref: PullRequestRef) -> list[dict[str, Any]]:
        return self.get(
            f"/repos/{ref.owner}/{ref.repo}/issues/{ref.number}/comments",
            params={"per_page": 100},
        )

    def issue_comment(self, ref: PullRequestRef, comment_id: int) -> dict[str, Any]:
        return self.get(
            f"/repos/{ref.owner}/{ref.repo}/issues/comments/{comment_id}",
        )

    def check_runs(self, ref: PullRequestRef, sha: str) -> list[dict[str, Any]]:
        data = self.get(
            f"/repos/{ref.owner}/{ref.repo}/commits/{sha}/check-runs",
            params={"per_page": 100},
        )
        return data.get("check_runs", []) if isinstance(data, dict) else []
