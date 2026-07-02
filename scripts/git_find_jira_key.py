"""Find Jira issue keys from git, PR, or arbitrary text."""
from __future__ import annotations

import argparse
import json

from activity_common import current_branch, extract_issue_keys, recent_commit_subjects
from github_client import GitHubClient, parse_pr_url


def main() -> None:
    parser = argparse.ArgumentParser(description="Find Jira issue keys from git and GitHub context")
    parser.add_argument("--text", action="append", default=[], help="Text to scan; can be passed more than once")
    parser.add_argument("--pr-url", help="GitHub pull request URL to scan")
    parser.add_argument("--pattern", default=None, help="Custom Jira key regex")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of plain keys")
    args = parser.parse_args()

    texts = list(args.text)
    texts.append(current_branch())
    texts.extend(recent_commit_subjects())

    if args.pr_url:
        ref = parse_pr_url(args.pr_url)
        gh = GitHubClient()
        pr = gh.pull_request(ref)
        texts.extend(
            [
                pr.get("title"),
                pr.get("body"),
                (pr.get("head") or {}).get("ref"),
                (pr.get("base") or {}).get("ref"),
            ]
        )
        for commit in gh.pull_request_commits(ref):
            texts.append(((commit.get("commit") or {}).get("message") or "").splitlines()[0])

    keys = extract_issue_keys(texts, args.pattern) if args.pattern else extract_issue_keys(texts)
    if args.json:
        print(json.dumps({"issue_keys": keys}, indent=2))
    else:
        print("\n".join(keys))


if __name__ == "__main__":
    main()
