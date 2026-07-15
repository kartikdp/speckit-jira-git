"""Synchronize a versioned, structured GitHub PR activity record to Jira."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import replace

from activity_common import add_comment_once, extract_issue_keys
from activity_contracts import (
    CommitEvidence,
    PullRequestActivityV1,
    one_line,
    parse_validation,
    redact_text,
)
from activity_renderers import render_pr_adf, render_pr_markdown
from github_client import GitHubClient, PullRequestRef, current_repo, parse_issue_comment_url, parse_pr_url
from jira_client import JiraClient


EVENTS = ("opened", "ready", "updated", "closed", "merged")


def _ref_from_args(args: argparse.Namespace) -> PullRequestRef:
    if args.pr_url:
        return parse_pr_url(args.pr_url)
    repo = args.repo or current_repo()
    if not repo:
        raise SystemExit("ERROR: pass --repo owner/repo or run inside a git repo with origin")
    if not args.pr:
        raise SystemExit("ERROR: pass --pr or --pr-url")
    owner, name = repo.split("/", 1)
    return PullRequestRef(owner=owner, repo=name, number=int(args.pr))


def _issue_keys(args: argparse.Namespace, pr: dict, commits: list[dict]) -> list[str]:
    if args.issue:
        return [args.issue.upper()]
    project = os.environ.get("JIRA_PROJECT", "").upper()
    groups = [
        [pr.get("title"), (pr.get("head") or {}).get("ref"), (pr.get("base") or {}).get("ref")],
        [(commit.get("commit") or {}).get("message") for commit in commits],
        [pr.get("body")],
    ]
    for texts in groups:
        keys = extract_issue_keys(texts, args.pattern)
        if project:
            project_keys = [key for key in keys if key.startswith(f"{project}-")]
            if project_keys:
                return project_keys
        if keys:
            return keys
    raise SystemExit("ERROR: no Jira issue key found. Pass --issue or include the key in PR context.")


def _latest_review_states(reviews: list[dict]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for review in reviews:
        user = (review.get("user") or {}).get("login") or "unknown"
        latest[user] = (review.get("state") or "COMMENTED").upper()
    return latest


def _review_summary(pr: dict, reviews: list[dict]) -> tuple[str, str]:
    latest = _latest_review_states(reviews)
    if any(state == "CHANGES_REQUESTED" for state in latest.values()):
        names = [user for user, state in latest.items() if state == "CHANGES_REQUESTED"]
        return "changes requested", ", ".join(names)
    if latest and all(state == "APPROVED" for state in latest.values()):
        return "approved", ", ".join(latest)
    approvals = [user for user, state in latest.items() if state == "APPROVED"]
    if approvals:
        return "partially approved", ", ".join(approvals)
    comments = [user for user, state in latest.items() if state == "COMMENTED"]
    if comments:
        return "commented", ", ".join(comments)
    requested = [
        user.get("login") or ""
        for user in pr.get("requested_reviewers", []) or []
        if user.get("login")
    ]
    return ("waiting review", ", ".join(requested)) if requested else ("review required", "none")


def _check_summary(check_runs: list[dict]) -> tuple[str, str]:
    if not check_runs:
        return "unknown", "0 checks"
    counts: dict[str, int] = {}
    pending = failing = 0
    for run in check_runs:
        status = (run.get("status") or "").lower()
        conclusion = (run.get("conclusion") or "pending").lower()
        if status != "completed":
            pending += 1
            conclusion = "pending"
        if conclusion in {"failure", "cancelled", "timed_out", "action_required"}:
            failing += 1
        counts[conclusion] = counts.get(conclusion, 0) + 1
    label = "failing" if failing else "pending" if pending else "passed"
    return label, ", ".join(f"{count} {name}" for name, count in sorted(counts.items()))


def _source_note(
    gh: GitHubClient,
    ref: PullRequestRef,
    pr: dict,
    commits: list[dict],
    comment_url: str,
    include_latest_comment: bool,
) -> tuple[str, str, str]:
    if comment_url:
        comment_ref, comment_id = parse_issue_comment_url(comment_url)
        if comment_ref != ref:
            raise SystemExit("ERROR: --comment-url must belong to the selected PR")
        comment = gh.issue_comment(ref, comment_id)
        author = (comment.get("user") or {}).get("login") or "unknown"
        when = comment.get("updated_at") or comment.get("created_at") or "unknown time"
        return f"PR conversation comment by {author} at {when}", redact_text(comment.get("body") or "").strip(), comment_url
    body = redact_text(pr.get("body") or "").strip()
    if body:
        author = (pr.get("user") or {}).get("login") or "unknown"
        return f"PR description by {author}", body, ""
    if include_latest_comment:
        comments = [comment for comment in gh.issue_comments(ref) if (comment.get("body") or "").strip()]
        if comments:
            comment = comments[-1]
            author = (comment.get("user") or {}).get("login") or "unknown"
            when = comment.get("updated_at") or comment.get("created_at") or "unknown time"
            return f"PR conversation comment by {author} at {when}", redact_text(comment.get("body") or "").strip(), comment.get("html_url") or ""
    if commits:
        message = redact_text((commits[-1].get("commit") or {}).get("message") or "").strip()
        if message:
            return f"latest commit {(commits[-1].get('sha') or '')[:8]}", message, ""
    return "", "", ""


def _selected_commits(commits: list[dict], requested: list[str]) -> list[dict]:
    """Resolve explicitly pushed SHA prefixes while preserving caller order."""

    if not requested:
        return commits
    selected: list[dict] = []
    seen: set[str] = set()
    for raw_sha in requested:
        prefix = raw_sha.strip().lower()
        if not prefix:
            raise ValueError("--commit values cannot be empty")
        matches = [
            commit
            for commit in commits
            if str(commit.get("sha") or "").lower().startswith(prefix)
        ]
        if len(matches) != 1:
            raise ValueError(
                f"--commit {raw_sha!r} must identify exactly one commit in the selected PR"
            )
        full_sha = str(matches[0].get("sha") or "").lower()
        if full_sha not in seen:
            selected.append(matches[0])
            seen.add(full_sha)
    return selected


def _contract(args: argparse.Namespace, ref: PullRequestRef, pr: dict, commits: list[dict], reviews: list[dict], checks: list[dict], note: tuple[str, str, str]) -> PullRequestActivityV1:
    check_state, check_detail = _check_summary(checks)
    review_state, review_detail = _review_summary(pr, reviews)
    headline = args.headline or args.summary
    if args.summary:
        sys.stderr.write("WARNING: --summary is deprecated; use the single-line --headline option.\n")
    validations = tuple(parse_validation(item) for item in args.validation)
    note_source, note_body, comment_url = note
    commit_items = []
    for commit in commits:
        message = ((commit.get("commit") or {}).get("message") or "").splitlines()[0]
        commit_items.append(CommitEvidence((commit.get("sha") or "")[:12] or "unknown", one_line(message, "commit subject")))
    return PullRequestActivityV1(
        event=args.event,
        repository=ref.full_name,
        number=ref.number,
        title=one_line(pr.get("title") or f"PR #{ref.number}", "PR title"),
        url=pr.get("html_url") or args.pr_url or "",
        author=(pr.get("user") or {}).get("login") or "unknown",
        source_branch=(pr.get("head") or {}).get("ref") or "unknown",
        target_branch=(pr.get("base") or {}).get("ref") or "unknown",
        head_sha=(pr.get("head") or {}).get("sha") or "unknown",
        state="merged" if pr.get("merged") else pr.get("state") or "unknown",
        draft=bool(pr.get("draft")),
        mergeability=pr.get("mergeable_state") or "unknown",
        checks=check_state,
        checks_detail=check_detail,
        review_state=review_state,
        review_detail=review_detail,
        changed_files=pr.get("changed_files", "unknown"),
        additions=pr.get("additions", "unknown"),
        deletions=pr.get("deletions", "unknown"),
        commits=tuple(commit_items),
        changes=tuple(one_line(item, "change") for item in args.change if item.strip()),
        validations=validations,
        remaining=tuple(one_line(item, "remaining work") for item in args.remaining if item.strip()),
        headline=one_line(headline, "headline") if headline else "",
        note_source=note_source,
        note=note_body,
        github_comment_url=comment_url,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize structured GitHub PR activity to Jira")
    parser.add_argument("--pr-url")
    parser.add_argument("--repo", help="owner/repo; defaults to current git origin")
    parser.add_argument("--pr", type=int)
    parser.add_argument("--issue", help="Jira issue key override")
    parser.add_argument("--event", default="opened", choices=EVENTS)
    parser.add_argument("--pattern", default=r"\b[A-Z][A-Z0-9]+-\d+\b")
    parser.add_argument("--headline", default="", help="Optional single-line activity headline")
    parser.add_argument("--summary", default="", help=argparse.SUPPRESS)
    parser.add_argument("--commit", action="append", default=[], help="Pushed commit SHA or unique prefix; repeatable")
    parser.add_argument("--change", action="append", default=[], help="Change made; repeatable")
    parser.add_argument("--validation", action="append", default=[], help="status|name|detail; repeatable")
    parser.add_argument("--remaining", action="append", default=[], help="Remaining work or None; repeatable")
    parser.add_argument("--comment-url", default="", help="Existing PR conversation comment to cite")
    parser.add_argument("--no-latest-comment", action="store_true")
    parser.add_argument("--post-github", action="store_true", help="Post the canonical Markdown update before Jira sync")
    parser.add_argument("--update-existing", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.post_github and args.comment_url:
        raise SystemExit("ERROR: use --post-github or --comment-url, not both")
    if args.post_github:
        missing = [
            name
            for name, values in (
                ("--commit", args.commit),
                ("--change", args.change),
                ("--validation", args.validation),
                ("--remaining", args.remaining),
            )
            if not values
        ]
        if missing:
            raise SystemExit(
                "ERROR: --post-github requires explicit " + ", ".join(missing)
            )
    try:
        gh = GitHubClient()
        ref = _ref_from_args(args)
        pr = gh.pull_request(ref)
        commits = gh.pull_request_commits(ref)
        reviews = gh.pull_request_reviews(ref)
        checks = gh.check_runs(ref, (pr.get("head") or {}).get("sha", ""))
        issues = _issue_keys(args, pr, commits)
        activity_commits = _selected_commits(commits, args.commit)
        note = (
            ("", "", "")
            if args.post_github
            else _source_note(gh, ref, pr, commits, args.comment_url, not args.no_latest_comment)
        )
        activity = _contract(args, ref, pr, activity_commits, reviews, checks, note)
    except (ValueError, OSError, RuntimeError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc

    markdown = render_pr_markdown(activity)
    if args.post_github and not args.dry_run:
        posted = gh.create_issue_comment(ref, markdown) or {}
        activity = replace(activity, github_comment_url=posted.get("html_url") or "")
        markdown = render_pr_markdown(activity)

    marker = f"speckit-jira-git:v1:pr:{args.event}:{ref.full_name}#{ref.number}:{activity.head_sha}"
    adf = render_pr_adf(activity, marker)
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
            f"PR update — {args.event}",
            [],
            update_existing=args.update_existing,
            visible_marker=False,
            fallback_texts=[activity.url, activity.head_sha],
            adf_body=adf,
        ).__dict__
        for issue in issues
    ]
    print(json.dumps({"results": results}, indent=2) if args.json else "\n".join(str(result) for result in results))


if __name__ == "__main__":
    main()
