"""Add or replace a comment on a Jira issue with an ADF body.

Reads the comment body from a markdown file (preferred) or stdin and converts
it to ADF via the local markdown-to-ADF converter. The conversion handles
paragraphs, headings, bullet lists, and inline code; anything more elaborate
should be kept simple to render predictably.

Usage:
    python add_comment.py --issue PROJ-100 --comment-file note.md
    python add_comment.py --issue PROJ-100 --update-id 4405121534 --comment-file note.md
    cat note.md | python add_comment.py --issue PROJ-100
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from jira_client import JiraClient
from markdown_to_adf import markdown_to_adf


def main() -> None:
    ap = argparse.ArgumentParser(description="Post or edit a Jira comment")
    ap.add_argument("--issue", required=True, help="Issue key, e.g. PROJ-100")
    ap.add_argument(
        "--comment-file",
        help="Path to markdown file. If omitted, reads from stdin.",
    )
    ap.add_argument(
        "--update-id",
        help="If given, PUT (edit) the existing comment id instead of creating one",
    )
    args = ap.parse_args()

    if args.comment_file:
        body_md = Path(args.comment_file).read_text(encoding="utf-8")
    else:
        body_md = sys.stdin.read()

    if not body_md.strip():
        sys.exit("Empty comment body")

    adf = markdown_to_adf(body_md)
    client = JiraClient()

    if args.update_id:
        path = f"/rest/api/3/issue/{args.issue}/comment/{args.update_id}"
        client.put(path, {"body": adf})
        print(f"Updated comment {args.update_id} on {args.issue}")
    else:
        path = f"/rest/api/3/issue/{args.issue}/comment"
        result = client.post(path, {"body": adf}) or {}
        print(f"Posted comment id={result.get('id')} on {args.issue}")


if __name__ == "__main__":
    main()
