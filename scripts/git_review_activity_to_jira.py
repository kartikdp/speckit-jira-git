"""Post GitHub review activity to the linked Jira issue."""
from __future__ import annotations

import argparse
import json

from activity_common import add_comment_once, extract_issue_keys
from github_client import GitHubClient, parse_pr_url
from jira_client import JiraClient


STATUS_LABELS = {
    "approved": "GitHub PR review approved",
    "changes_requested": "GitHub PR review changes requested",
    "commented": "GitHub PR review commented",
    "review_requested": "GitHub PR review requested",
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


def _latest_review_message(reviews: list[dict], status: str, reviewer: str) -> tuple[str, str]:
    wanted_state = {
        "approved": "APPROVED",
        "changes_requested": "CHANGES_REQUESTED",
        "commented": "COMMENTED",
    }.get(status)
    reviewer_lower = reviewer.lower().strip()
    candidates = []
    for review in reviews:
        body = (review.get("body") or "").strip()
        if not body:
            continue
        state = (review.get("state") or "").upper()
        user = (review.get("user") or {}).get("login") or "unknown"
        if wanted_state and state != wanted_state:
            continue
        if reviewer_lower and user.lower() != reviewer_lower:
            continue
        candidates.append(review)
    if not candidates:
        return "", ""
    review = candidates[-1]
    user = (review.get("user") or {}).get("login") or "unknown"
    submitted = review.get("submitted_at") or "unknown time"
    url = review.get("html_url") or ""
    source = f"GitHub review by {user} at {submitted}"
    if url:
        source += f" ({url})"
    return source, (review.get("body") or "").strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a Jira comment for GitHub PR review activity")
    parser.add_argument("--pr-url", required=True, help="GitHub PR URL")
    parser.add_argument("--issue", help="Jira issue key override")
    parser.add_argument(
        "--status",
        required=True,
        choices=sorted(STATUS_LABELS),
        help="Review outcome",
    )
    parser.add_argument("--reviewer", default="", help="Reviewer name or GitHub login")
    parser.add_argument("--round", default="", help="Review round label, e.g. 2")
    parser.add_argument("--area", choices=["frontend", "backend", "fullstack", "general"], default="general")
    parser.add_argument("--summary", default="", help="Manual message override for the Jira comment")
    parser.add_argument("--pattern", default=r"\b[A-Z][A-Z0-9]+-\d+\b", help="Jira key regex")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    gh = GitHubClient()
    ref = parse_pr_url(args.pr_url)
    pr = gh.pull_request(ref)
    commits = gh.pull_request_commits(ref)
    reviews = gh.pull_request_reviews(ref)
    issues = _issue_keys(args, pr, commits)

    title = STATUS_LABELS[args.status]
    marker_parts = [
        "speckit-jira-git:github-review",
        args.status,
        ref.full_name,
        f"#{ref.number}",
        args.area,
        args.round or "round-na",
        args.reviewer or "reviewer-na",
    ]
    marker = ":".join(marker_parts)
    lines = [
        f"PR: {pr.get('title')}",
        f"URL: {pr.get('html_url')}",
        f"Repository: {ref.full_name}",
        f"Area: {args.area}",
        f"Reviewer: {args.reviewer or 'not specified'}",
        f"Round: {args.round or 'not specified'}",
        f"Outcome: {args.status.replace('_', ' ')}",
    ]
    if args.summary:
        message_source = "manual summary override"
        message_body = args.summary.strip()
    else:
        message_source, message_body = _latest_review_message(reviews, args.status, args.reviewer)
    code_blocks = []
    if message_body:
        lines.append(f"GitHub message source: {message_source}")
        code_blocks.append(message_body)

    if args.dry_run:
        output = {
            "issues": issues,
            "title": title,
            "github_message_source": message_source,
            "github_message": message_body,
            "lines": lines,
            "marker": marker,
        }
        print(json.dumps(output, indent=2) if args.json else output)
        return

    client = JiraClient()
    results = [
        add_comment_once(client, issue, marker, title, lines, code_blocks=code_blocks, dry_run=False).__dict__
        for issue in issues
    ]
    print(json.dumps({"results": results}, indent=2) if args.json else "\n".join(str(r) for r in results))


if __name__ == "__main__":
    main()
