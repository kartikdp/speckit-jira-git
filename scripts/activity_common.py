"""Shared helpers for GitHub activity to Jira comments."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from typing import Any, Iterable

from jira_client import JiraClient


DEFAULT_ISSUE_KEY_RE = r"\b[A-Z][A-Z0-9]+-\d+\b"


@dataclass(frozen=True)
class JiraCommentResult:
    """Outcome for an idempotent Jira comment operation."""

    issue: str
    marker: str
    created: bool
    updated: bool = False
    comment_id: str | None = None


def extract_issue_keys(texts: Iterable[str | None], pattern: str = DEFAULT_ISSUE_KEY_RE) -> list[str]:
    """Extract unique Jira issue keys from text in first-seen order."""

    seen: set[str] = set()
    keys: list[str] = []
    regex = re.compile(pattern)
    for text in texts:
        if not text:
            continue
        for match in regex.findall(text):
            key = match.upper()
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def current_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return ""
    return result.stdout.strip()


def recent_commit_subjects(limit: int = 20) -> list[str]:
    try:
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--pretty=%s"],
            check=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except Exception:
        return []
    return [line for line in result.stdout.splitlines() if line.strip()]


def plain_from_adf(node: Any) -> str:
    """Extract plain text from Jira ADF."""

    if isinstance(node, dict):
        text = node.get("text", "")
        for child in node.get("content", []) or []:
            text += plain_from_adf(child)
        return text
    if isinstance(node, list):
        return "".join(plain_from_adf(item) for item in node)
    return ""


def comment_exists(
    client: JiraClient,
    issue: str,
    marker: str,
    fallback_texts: list[str] | None = None,
) -> str | None:
    """Return existing comment id if marker or fallback text already exists."""

    start_at = 0
    fallback_texts = [text for text in fallback_texts or [] if text]
    while True:
        data = client.get(
            f"/rest/api/3/issue/{issue}/comment",
            params={"startAt": start_at, "maxResults": 100, "orderBy": "created"},
        ) or {}
        for comment in data.get("comments", []):
            plain = plain_from_adf(comment.get("body"))
            if marker in plain or (fallback_texts and all(text in plain for text in fallback_texts)):
                return str(comment.get("id"))
        start_at += len(data.get("comments", []))
        if start_at >= int(data.get("total", 0)):
            return None


def adf_activity_comment(
    title: str,
    lines: list[str],
    marker: str | None = None,
    code_blocks: list[str] | None = None,
) -> dict:
    """Build a compact ADF activity comment."""

    blocks = [
        JiraClient.adf_heading(title, level=4),
        *[JiraClient.adf_code_block(block) for block in code_blocks or [] if block],
        *[JiraClient.adf_para(line) for line in lines if line],
    ]
    if marker:
        blocks.append(JiraClient.adf_para(marker))
    return JiraClient.adf_doc(blocks)


def add_comment_once(
    client: JiraClient,
    issue: str,
    marker: str,
    title: str,
    lines: list[str],
    code_blocks: list[str] | None = None,
    update_existing: bool = False,
    visible_marker: bool = True,
    fallback_texts: list[str] | None = None,
    dry_run: bool = False,
) -> JiraCommentResult:
    """Create a Jira comment once, keyed by a stable marker."""

    existing = comment_exists(client, issue, marker, fallback_texts=fallback_texts)
    body_marker = marker if visible_marker else None
    if existing:
        if update_existing and not dry_run:
            client.put(
                f"/rest/api/3/issue/{issue}/comment/{existing}",
                {"body": adf_activity_comment(title, lines, body_marker, code_blocks=code_blocks)},
            )
            return JiraCommentResult(
                issue=issue,
                marker=marker,
                created=False,
                updated=True,
                comment_id=existing,
            )
        return JiraCommentResult(issue=issue, marker=marker, created=False, comment_id=existing)
    if dry_run:
        return JiraCommentResult(issue=issue, marker=marker, created=False, comment_id=None)
    result = client.post(
        f"/rest/api/3/issue/{issue}/comment",
        {"body": adf_activity_comment(title, lines, body_marker, code_blocks=code_blocks)},
    ) or {}
    return JiraCommentResult(
        issue=issue,
        marker=marker,
        created=True,
        comment_id=str(result.get("id")) if result.get("id") else None,
    )
