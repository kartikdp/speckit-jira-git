"""Synchronize a versioned, structured GitHub review activity record to Jira."""
from __future__ import annotations

import argparse
import json
import sys

from activity_common import add_comment_once, extract_issue_keys
from activity_contracts import (
    ReviewActivityV1,
    load_findings,
    one_line,
    parse_finding,
    parse_validation,
    redact_text,
)
from activity_renderers import render_review_adf, render_review_markdown
from github_client import GitHubClient, parse_pr_url
from jira_client import JiraClient
from workflow_config import load_workflow_config
from workflow_manifest import positive_number


STATUS_LABELS = {
    "approved": "GitHub PR review approved",
    "changes_requested": "GitHub PR review changes requested",
    "commented": "GitHub PR review commented",
    "review_requested": "GitHub PR review requested",
}
GITHUB_STATES = {
    "approved": "APPROVED",
    "changes_requested": "CHANGES_REQUESTED",
    "commented": "COMMENTED",
}


def _issue_keys(args: argparse.Namespace, pr: dict, commits: list[dict]) -> list[str]:
    if args.issue:
        return [args.issue.upper()]
    texts = [
        pr.get("title"),
        pr.get("body"),
        (pr.get("head") or {}).get("ref"),
        (pr.get("base") or {}).get("ref"),
    ]
    texts.extend((commit.get("commit") or {}).get("message") for commit in commits)
    keys = extract_issue_keys(texts, args.pattern)
    if not keys:
        raise SystemExit("ERROR: no Jira issue key found. Pass --issue or include the key in PR context.")
    return keys


def _select_review(reviews: list[dict], status: str, reviewer: str) -> dict | None:
    wanted_state = GITHUB_STATES.get(status)
    candidates = [
        review
        for review in reviews
        if not wanted_state or (review.get("state") or "").upper() == wanted_state
    ]
    if reviewer:
        exact = [
            review
            for review in candidates
            if ((review.get("user") or {}).get("login") or "").lower() == reviewer.lower()
        ]
        if exact:
            return exact[-1]
    return candidates[-1] if candidates else None


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize structured GitHub PR review activity to Jira")
    parser.add_argument("--pr-url", required=True)
    parser.add_argument("--issue", help="Jira issue key override")
    parser.add_argument("--status", required=True, choices=sorted(STATUS_LABELS))
    parser.add_argument("--reviewer", default="", help="Actual reviewer display name or GitHub login")
    parser.add_argument("--round", type=int, default=None)
    parser.add_argument("--area", choices=["frontend", "backend", "fullstack", "general"], default="general")
    parser.add_argument("--headline", default="", help="Optional single-line review headline")
    parser.add_argument("--summary", default="", help=argparse.SUPPRESS)
    parser.add_argument("--finding", action="append", default=[], help="severity|summary|path|line|impact|required_action")
    parser.add_argument("--finding-file", action="append", default=[], help="JSON finding packet; repeatable")
    parser.add_argument("--validation", action="append", default=[], help="status|name|detail; repeatable")
    parser.add_argument("--config", default="", help="Optional .speckit-jira-git.toml path")
    parser.add_argument("--pattern", default=r"\b[A-Z][A-Z0-9]+-\d+\b")
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        config = load_workflow_config(args.config or None)
        requested_reviewer = (args.reviewer or config.reviewer).strip()
        gh = GitHubClient()
        ref = parse_pr_url(args.pr_url)
        pr = gh.pull_request(ref)
        commits = gh.pull_request_commits(ref)
        reviews = gh.pull_request_reviews(ref)
        issues = _issue_keys(args, pr, commits)
        selected_review = _select_review(reviews, args.status, requested_reviewer)
        derived_reviewer = ((selected_review or {}).get("user") or {}).get("login") or ""
        reviewer = requested_reviewer or derived_reviewer
        if not reviewer:
            raise ValueError("reviewer is required when it cannot be derived from a matching GitHub review")
        if args.status == "review_requested" and not requested_reviewer:
            raise ValueError("--reviewer or configured identity.reviewer is required for review_requested")
        round_number = positive_number(args.round, "review round") if args.round is not None else None
        headline = args.headline or args.summary
        if args.summary:
            sys.stderr.write("WARNING: --summary is deprecated; use the single-line --headline option.\n")
        findings = [parse_finding(item) for item in args.finding]
        for finding_file in args.finding_file:
            findings.extend(load_findings(finding_file))
        validations = tuple(parse_validation(item) for item in args.validation)
        note = redact_text((selected_review or {}).get("body") or "").strip()
        review_url = (selected_review or {}).get("html_url") or ""
        note_source = ""
        if selected_review:
            author = ((selected_review.get("user") or {}).get("login") or "unknown")
            submitted = selected_review.get("submitted_at") or "unknown time"
            note_source = f"GitHub review by {author} at {submitted}"
        activity = ReviewActivityV1(
            status=args.status,
            repository=ref.full_name,
            number=ref.number,
            title=one_line(pr.get("title") or f"PR #{ref.number}", "PR title"),
            url=pr.get("html_url") or args.pr_url,
            area=args.area,
            reviewer=one_line(reviewer, "reviewer"),
            round=round_number,
            head_sha=(pr.get("head") or {}).get("sha") or "unknown",
            findings=tuple(findings),
            validations=validations,
            headline=one_line(headline, "headline") if headline else "",
            note_source=note_source,
            note=note,
            review_url=review_url,
        )
    except (ValueError, OSError, RuntimeError, json.JSONDecodeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    round_marker = str(activity.round) if activity.round is not None else "round-na"
    marker = (
        f"speckit-jira-git:v1:review:{args.status}:{ref.full_name}#{ref.number}:"
        f"{activity.head_sha}:{args.area}:{round_marker}:{activity.reviewer}"
    )
    markdown = render_review_markdown(activity)
    adf = render_review_adf(activity, marker)
    if args.dry_run:
        output = {"issues": issues, "marker": marker, "activity": activity.to_dict(), "markdown": markdown, "adf": adf}
        print(json.dumps(output, indent=2) if args.json else markdown)
        return

    client = JiraClient()
    results = [
        add_comment_once(
            client,
            issue,
            marker,
            STATUS_LABELS[args.status],
            [],
            update_existing=args.update_existing,
            visible_marker=False,
            fallback_texts=[activity.url, activity.head_sha, activity.reviewer],
            adf_body=adf,
        ).__dict__
        for issue in issues
    ]
    print(json.dumps({"results": results}, indent=2) if args.json else "\n".join(str(result) for result in results))


if __name__ == "__main__":
    main()
