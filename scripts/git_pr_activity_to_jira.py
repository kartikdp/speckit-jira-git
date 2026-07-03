"""Post GitHub pull request activity to the linked Jira issue."""
from __future__ import annotations

import argparse
import json
import os

from activity_common import add_comment_once, extract_issue_keys
from github_client import GitHubClient, PullRequestRef, current_repo, parse_issue_comment_url, parse_pr_url
from jira_client import JiraClient


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
    title_branch_keys = extract_issue_keys(
        [
            pr.get("title"),
            (pr.get("head") or {}).get("ref"),
            (pr.get("base") or {}).get("ref"),
        ],
        args.pattern,
    )
    if title_branch_keys:
        if project:
            project_keys = [key for key in title_branch_keys if key.startswith(f"{project}-")]
            if project_keys:
                return project_keys
        return title_branch_keys

    commit_texts = []
    for commit in commits:
        commit_texts.append((commit.get("commit") or {}).get("message"))
    keys = extract_issue_keys(commit_texts, args.pattern)
    if keys:
        if project:
            project_keys = [key for key in keys if key.startswith(f"{project}-")]
            if project_keys:
                return project_keys
        return keys

    keys = extract_issue_keys([pr.get("body")], args.pattern)
    if project:
        project_keys = [key for key in keys if key.startswith(f"{project}-")]
        if project_keys:
            return project_keys
    if not keys:
        raise SystemExit("ERROR: no Jira issue key found. Pass --issue or include the key in branch/title/body/commit.")
    return keys


def _event_title(event: str) -> str:
    labels = {
        "opened": "GitHub pull request opened",
        "ready": "GitHub pull request ready for review",
        "updated": "GitHub pull request updated",
        "closed": "GitHub pull request closed",
        "merged": "GitHub pull request merged",
    }
    return labels.get(event, f"GitHub pull request {event}")


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _short_sha(pr: dict) -> str:
    sha = ((pr.get("head") or {}).get("sha") or "")[:8]
    return sha or "unknown"


def _requested_reviewers(pr: dict) -> list[str]:
    users = [(user.get("login") or "") for user in pr.get("requested_reviewers", []) or []]
    teams = [(team.get("slug") or team.get("name") or "") for team in pr.get("requested_teams", []) or []]
    return [item for item in [*users, *teams] if item]


def _latest_review_states(reviews: list[dict]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for review in reviews:
        user = (review.get("user") or {}).get("login") or "unknown"
        state = (review.get("state") or "COMMENTED").upper()
        latest[user] = state
    return latest


def _review_summary(pr: dict, reviews: list[dict]) -> tuple[str, str]:
    latest = _latest_review_states(reviews)
    requested = _requested_reviewers(pr)
    if any(state == "CHANGES_REQUESTED" for state in latest.values()):
        reviewers = ", ".join(user for user, state in latest.items() if state == "CHANGES_REQUESTED")
        return "changes requested", reviewers or "reviewer"
    if latest and all(state == "APPROVED" for state in latest.values()):
        return "approved", ", ".join(latest)
    approvals = [user for user, state in latest.items() if state == "APPROVED"]
    comments = [user for user, state in latest.items() if state == "COMMENTED"]
    if approvals:
        return "partially approved", ", ".join(approvals)
    if comments:
        return "commented", ", ".join(comments)
    if requested:
        return "waiting review", ", ".join(requested)
    return "review required", "none"


def _check_summary(check_runs: list[dict]) -> tuple[str, str]:
    if not check_runs:
        return "unknown", "0 checks"
    counts: dict[str, int] = {}
    pending = 0
    failing = 0
    for run in check_runs:
        status = (run.get("status") or "").lower()
        conclusion = (run.get("conclusion") or "pending").lower()
        if status != "completed":
            pending += 1
            conclusion = "pending"
        if conclusion in {"failure", "cancelled", "timed_out", "action_required"}:
            failing += 1
        counts[conclusion] = counts.get(conclusion, 0) + 1
    if failing:
        label = "failing"
    elif pending:
        label = "pending"
    else:
        label = "passed"
    detail = ", ".join(f"{count} {name}" for name, count in sorted(counts.items()))
    return label, detail


def _merge_label(pr: dict) -> str:
    if pr.get("merged"):
        return "merged"
    state = pr.get("mergeable_state") or "unknown"
    if state in {"clean", "has_hooks", "unstable"}:
        return "ready"
    if state in {"dirty", "blocked"}:
        return "blocked"
    return state


def _gate_line(label: str, status: str) -> str:
    symbol = "x" if status in {"done", "passed", "ready", "approved", "merged"} else "!" if status in {"blocked", "failing", "changes requested"} else " "
    return f"[{symbol}] {label}: {status}"


def _latest_commit_message(commits: list[dict]) -> str:
    if not commits:
        return ""
    return ((commits[-1].get("commit") or {}).get("message") or "").strip()


def _github_message_from_comment(comment: dict) -> tuple[str, str]:
    author = (comment.get("user") or {}).get("login") or "unknown"
    updated = comment.get("updated_at") or comment.get("created_at") or "unknown time"
    url = comment.get("html_url") or ""
    source = f"PR conversation comment by {author} at {updated}"
    if url:
        source += f" ({url})"
    return source, (comment.get("body") or "").strip()


def _github_message(
    *,
    gh: GitHubClient,
    ref: PullRequestRef,
    pr: dict,
    commits: list[dict],
    summary: str,
    comment_url: str,
    include_latest_comment: bool,
) -> tuple[str, str]:
    """Select the GitHub-authored message to attach to the Jira comment."""

    if summary.strip():
        return "manual summary override", summary.strip()
    if comment_url:
        comment_ref, comment_id = parse_issue_comment_url(comment_url)
        if comment_ref != ref:
            raise SystemExit("ERROR: --comment-url must belong to the same PR as --pr-url")
        return _github_message_from_comment(gh.issue_comment(ref, comment_id))
    body = (pr.get("body") or "").strip()
    if body:
        author = (pr.get("user") or {}).get("login") or "unknown"
        updated = pr.get("updated_at") or pr.get("created_at") or "unknown time"
        return f"PR description by {author} at {updated}", body
    if include_latest_comment:
        comments = [comment for comment in gh.issue_comments(ref) if (comment.get("body") or "").strip()]
        if comments:
            return _github_message_from_comment(comments[-1])
    commit_message = _latest_commit_message(commits)
    if commit_message:
        sha = (((commits[-1].get("sha") or "")[:8]) or "unknown")
        return f"latest commit message {sha}", commit_message
    return "", ""


def _status_card(ref: PullRequestRef, pr: dict, event: str, commits: list[dict], reviews: list[dict], check_runs: list[dict]) -> str:
    """Render a compact fixed-width PR status card for Jira comments."""

    state = "merged" if pr.get("merged") else pr.get("state", "unknown")
    draft = bool(pr.get("draft"))
    mergeable = pr.get("mergeable_state") or "unknown"
    source = (pr.get("head") or {}).get("ref") or "unknown"
    target = (pr.get("base") or {}).get("ref") or "unknown"
    updated = pr.get("updated_at") or "unknown"
    number = pr.get("number") or ref.number
    review_state, review_detail = _review_summary(pr, reviews)
    check_state, check_detail = _check_summary(check_runs)
    merge_label = _merge_label(pr)
    files = pr.get("changed_files", "unknown")
    additions = pr.get("additions", "unknown")
    deletions = pr.get("deletions", "unknown")
    commit_count = pr.get("commits") or len(commits)
    return "\n".join(
        [
            "+---------------- GitHub PR Snapshot --------------+",
            f"| PR       : {ref.full_name}#{number}",
            f"| Event    : {event}",
            f"| State    : {state}",
            f"| Draft    : {_yes_no(draft)}",
            f"| Merge    : {mergeable}",
            f"| Review   : {review_state} ({review_detail})",
            f"| Checks   : {check_state} ({check_detail})",
            f"| Change   : {commit_count} commits, {files} files, +{additions}/-{deletions}",
            f"| Head SHA : {_short_sha(pr)}",
            f"| Source   : {source}",
            f"| Target   : {target}",
            f"| Updated  : {updated}",
            "+--------------------------------------------------+",
            "",
            "Branch / PR path:",
            f"  {source}  --->  PR #{number}  --->  {target}",
            "",
            "Progress gates:",
            f"  {_gate_line('Branch pushed', 'done')}",
            f"  {_gate_line('PR opened', 'done' if state in {'open', 'closed', 'merged'} else state)}",
            f"  {_gate_line('CI checks', check_state)}",
            f"  {_gate_line('Code review', review_state)}",
            f"  {_gate_line('Merge readiness', merge_label)}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a Jira comment for GitHub PR activity")
    parser.add_argument("--pr-url", help="GitHub PR URL")
    parser.add_argument("--repo", help="owner/repo; defaults to current git origin")
    parser.add_argument("--pr", type=int, help="PR number when --pr-url is not used")
    parser.add_argument("--issue", help="Jira issue key override")
    parser.add_argument(
        "--event",
        default="opened",
        choices=["opened", "ready", "updated", "closed", "merged"],
        help="Activity type to report",
    )
    parser.add_argument("--pattern", default=r"\b[A-Z][A-Z0-9]+-\d+\b", help="Jira key regex")
    parser.add_argument("--summary", default="", help="Manual message override for the Jira comment")
    parser.add_argument("--comment-url", default="", help="GitHub PR conversation comment URL to attach")
    parser.add_argument(
        "--no-latest-comment",
        action="store_true",
        help="Do not fall back to the latest PR conversation comment when PR body is empty",
    )
    parser.add_argument("--update-existing", action="store_true", help="Update existing marked Jira comment instead of skipping")
    parser.add_argument("--dry-run", action="store_true", help="Print payload without posting")
    parser.add_argument("--json", action="store_true", help="Print JSON result")
    args = parser.parse_args()

    gh = GitHubClient()
    ref = _ref_from_args(args)
    pr = gh.pull_request(ref)
    commits = gh.pull_request_commits(ref)
    reviews = gh.pull_request_reviews(ref)
    check_runs = gh.check_runs(ref, (pr.get("head") or {}).get("sha", ""))
    issues = _issue_keys(args, pr, commits)

    status_card = _status_card(ref, pr, args.event, commits, reviews, check_runs)
    message_source, message_body = _github_message(
        gh=gh,
        ref=ref,
        pr=pr,
        commits=commits,
        summary=args.summary,
        comment_url=args.comment_url,
        include_latest_comment=not args.no_latest_comment,
    )
    lines = [
        f"PR: {pr.get('title')}",
        f"URL: {pr.get('html_url')}",
    ]
    code_blocks = [status_card]
    if message_body:
        lines.append(f"GitHub message source: {message_source}")
        code_blocks.append(message_body)
    marker = f"speckit-jira-git:github-pr:{args.event}:{ref.full_name}#{ref.number}"
    title = _event_title(args.event)

    if args.dry_run:
        output = {
            "issues": issues,
            "title": title,
            "status_card": status_card,
            "github_message_source": message_source,
            "github_message": message_body,
            "lines": lines,
            "marker": marker,
        }
        print(json.dumps(output, indent=2) if args.json else output)
        return

    client = JiraClient()
    results = [
        add_comment_once(
            client,
            issue,
            marker,
            title,
            lines,
            code_blocks=code_blocks,
            update_existing=args.update_existing,
            visible_marker=False,
            fallback_texts=[title, pr.get("html_url") or "", pr.get("title") or ""],
            dry_run=False,
        ).__dict__
        for issue in issues
    ]
    print(json.dumps({"results": results}, indent=2) if args.json else "\n".join(str(r) for r in results))


if __name__ == "__main__":
    main()
