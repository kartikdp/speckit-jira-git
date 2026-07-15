"""Versioned structured contracts for GitHub activity synchronized to Jira."""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1
VALIDATION_STATUSES = {"passed", "failed", "blocked", "skipped"}
FINDING_SEVERITIES = {"P0", "P1", "P2", "P3"}
MAX_FIELD_LENGTH = 10_000

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(JIRA_TOKEN|GITHUB_TOKEN|AUTHORIZATION)\s*[:=]\s*[^\s]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]+\b"),
    re.compile(r"(https?://[^:/\s]+:)[^@/\s]+(@)"),
)


def redact_text(value: str) -> str:
    """Redact common credentials and bound untrusted comment content."""

    text = value or ""
    text = _SECRET_PATTERNS[0].sub(lambda match: f"{match.group(1)}=[REDACTED]", text)
    text = _SECRET_PATTERNS[1].sub("Bearer [REDACTED]", text)
    text = _SECRET_PATTERNS[2].sub("[REDACTED_GITHUB_TOKEN]", text)
    text = _SECRET_PATTERNS[3].sub(r"\1[REDACTED]\2", text)
    if len(text) > MAX_FIELD_LENGTH:
        return text[: MAX_FIELD_LENGTH - 14].rstrip() + "… [truncated]"
    return text


def one_line(value: str, label: str) -> str:
    text = " ".join(redact_text(value).split())
    if "\n" in value or "\r" in value:
        raise ValueError(f"{label} must be a single line")
    return text


@dataclass(frozen=True)
class CommitEvidence:
    sha: str
    subject: str


@dataclass(frozen=True)
class ValidationEvidence:
    status: str
    name: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.status not in VALIDATION_STATUSES:
            raise ValueError(f"validation status must be one of {sorted(VALIDATION_STATUSES)}")
        if not self.name.strip():
            raise ValueError("validation name is required")


@dataclass(frozen=True)
class ReviewFinding:
    severity: str
    summary: str
    path: str = ""
    line: int | None = None
    impact: str = ""
    required_action: str = ""

    def __post_init__(self) -> None:
        if self.severity not in FINDING_SEVERITIES:
            raise ValueError(f"finding severity must be one of {sorted(FINDING_SEVERITIES)}")
        if not self.summary.strip():
            raise ValueError("finding summary is required")
        if self.line is not None and self.line < 1:
            raise ValueError("finding line must be positive")


@dataclass(frozen=True)
class PullRequestActivityV1:
    event: str
    repository: str
    number: int
    title: str
    url: str
    author: str
    source_branch: str
    target_branch: str
    head_sha: str
    state: str
    draft: bool
    mergeability: str
    checks: str
    checks_detail: str
    review_state: str
    review_detail: str
    changed_files: int | str
    additions: int | str
    deletions: int | str
    commits: tuple[CommitEvidence, ...] = ()
    changes: tuple[str, ...] = ()
    validations: tuple[ValidationEvidence, ...] = ()
    remaining: tuple[str, ...] = ()
    headline: str = ""
    note_source: str = ""
    note: str = ""
    github_comment_url: str = ""
    schema_version: int = field(default=SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReviewActivityV1:
    status: str
    repository: str
    number: int
    title: str
    url: str
    area: str
    reviewer: str
    round: int | None
    head_sha: str
    findings: tuple[ReviewFinding, ...] = ()
    validations: tuple[ValidationEvidence, ...] = ()
    headline: str = ""
    note_source: str = ""
    note: str = ""
    review_url: str = ""
    schema_version: int = field(default=SCHEMA_VERSION, init=False)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_validation(raw: str) -> ValidationEvidence:
    parts = [part.strip() for part in raw.split("|", 2)]
    if len(parts) < 2:
        raise ValueError("validation must use status|name|detail")
    status, name = parts[:2]
    detail = parts[2] if len(parts) == 3 else ""
    return ValidationEvidence(
        status.lower(),
        one_line(name, "validation name"),
        one_line(detail, "validation detail") if detail else "",
    )


def parse_finding(raw: str) -> ReviewFinding:
    parts = [part.strip() for part in raw.split("|", 5)]
    if len(parts) < 2:
        raise ValueError("finding must use severity|summary|path|line|impact|required_action")
    parts += [""] * (6 - len(parts))
    severity, summary, path, line_raw, impact, required_action = parts
    line = int(line_raw) if line_raw else None
    return ReviewFinding(
        severity=severity.upper(),
        summary=one_line(summary, "finding summary"),
        path=one_line(path, "finding path"),
        line=line,
        impact=one_line(impact, "finding impact") if impact else "",
        required_action=one_line(required_action, "finding required action") if required_action else "",
    )


def load_findings(path: str | Path) -> tuple[ReviewFinding, ...]:
    file_path = Path(path).expanduser().resolve()
    data = json.loads(file_path.read_text(encoding="utf-8"))
    rows = data.get("findings", []) if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError("finding file must contain a list or a findings list")
    findings: list[ReviewFinding] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each finding must be an object")
        findings.append(
            ReviewFinding(
                severity=str(row.get("severity", "")).upper(),
                summary=one_line(str(row.get("summary", "")), "finding summary"),
                path=one_line(str(row.get("path", "")), "finding path"),
                line=int(row["line"]) if row.get("line") is not None else None,
                impact=(
                    one_line(str(row.get("impact", "")), "finding impact")
                    if row.get("impact")
                    else ""
                ),
                required_action=(
                    one_line(
                        str(row.get("required_action", "")),
                        "finding required action",
                    )
                    if row.get("required_action")
                    else ""
                ),
            )
        )
    return tuple(findings)
