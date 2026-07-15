"""Deterministic Markdown and Jira ADF renderers for activity contracts."""
from __future__ import annotations

from collections import Counter

from activity_contracts import PullRequestActivityV1, ReviewActivityV1
from jira_client import JiraClient


def _none(items: tuple[str, ...]) -> tuple[str, ...]:
    return items or ("None",)


def render_pr_markdown(activity: PullRequestActivityV1) -> str:
    lines = [
        f"### PR update — {activity.event}",
        "",
        "#### Context",
        f"- PR: [{activity.title}]({activity.url})",
        f"- Repository: `{activity.repository}`",
        f"- Source → target: `{activity.source_branch}` → `{activity.target_branch}`",
        f"- Head SHA: `{activity.head_sha}`",
        f"- Author: `{activity.author}`",
        f"- State: `{activity.state}`; draft: `{str(activity.draft).lower()}`",
        "",
        "#### Commits",
    ]
    lines.extend(f"- `{commit.sha}` — {commit.subject}" for commit in activity.commits)
    if not activity.commits:
        lines.append("- None")
    lines.extend(["", "#### Changes"])
    lines.extend(f"- {item}" for item in _none(activity.changes))
    lines.extend(["", "#### Validation"])
    if activity.validations:
        lines.extend(
            f"- {item.status.upper()} — {item.name}: {item.detail or 'No additional detail'}"
            for item in activity.validations
        )
    else:
        lines.append("- Not reported")
    lines.extend(
        [
            "",
            "#### CI and merge state",
            f"- Checks: `{activity.checks}` — {activity.checks_detail}",
            f"- Review: `{activity.review_state}` — {activity.review_detail}",
            f"- Mergeability: `{activity.mergeability}`",
            f"- Change size: {activity.changed_files} files, +{activity.additions}/-{activity.deletions}",
            "",
            "#### Remaining work",
        ]
    )
    lines.extend(f"- {item}" for item in _none(activity.remaining))
    if activity.note:
        lines.extend(["", "#### Source note", f"- Source: {activity.note_source or 'unspecified'}", "", activity.note])
    lines.extend(["", "#### Evidence", f"- PR: {activity.url}"])
    if activity.github_comment_url:
        lines.append(f"- GitHub comment: {activity.github_comment_url}")
    if activity.headline:
        lines.insert(2, activity.headline)
        lines.insert(3, "")
    return "\n".join(lines).rstrip() + "\n"


def render_review_markdown(activity: ReviewActivityV1) -> str:
    round_label = str(activity.round) if activity.round is not None else "not specified"
    counts = Counter(finding.severity for finding in activity.findings)
    lines = [
        f"### Review round {round_label} — {activity.status.replace('_', ' ')}",
        "",
        "#### Context",
        f"- PR: [{activity.title}]({activity.url})",
        f"- Repository: `{activity.repository}`",
        f"- Area: `{activity.area}`",
        f"- Reviewer: `{activity.reviewer}`",
        f"- Head SHA: `{activity.head_sha}`",
        "",
        "#### Findings",
        *[f"- {severity}: {counts.get(severity, 0)}" for severity in ("P0", "P1", "P2", "P3")],
        "",
        "#### Actionable findings",
    ]
    if activity.findings:
        for finding in activity.findings:
            location = finding.path
            if finding.line is not None:
                location += f":{finding.line}"
            lines.append(f"- [{finding.severity}] {finding.summary}" + (f" — `{location}`" if location else ""))
            if finding.impact:
                lines.append(f"  - Impact: {finding.impact}")
            if finding.required_action:
                lines.append(f"  - Required action: {finding.required_action}")
    else:
        lines.append("- None")
    lines.extend(["", "#### Validation performed"])
    if activity.validations:
        lines.extend(
            f"- {item.status.upper()} — {item.name}: {item.detail or 'No additional detail'}"
            for item in activity.validations
        )
    else:
        lines.append("- Not reported")
    lines.extend(["", "#### Disposition", f"- {activity.status.replace('_', ' ').title()}"])
    if activity.note:
        lines.extend(["", "#### Source note", f"- Source: {activity.note_source or 'unspecified'}", "", activity.note])
    lines.extend(["", "#### Evidence", f"- PR: {activity.url}"])
    if activity.review_url:
        lines.append(f"- GitHub review: {activity.review_url}")
    if activity.headline:
        lines.insert(2, activity.headline)
        lines.insert(3, "")
    return "\n".join(lines).rstrip() + "\n"


def _section(title: str, items: list[str]) -> list[dict]:
    return [JiraClient.adf_heading(title, level=4), JiraClient.adf_bullet_list(items or ["None"])]


def render_pr_adf(activity: PullRequestActivityV1, marker: str) -> dict:
    blocks = [JiraClient.adf_heading(f"PR update — {activity.event}", level=3)]
    if activity.headline:
        blocks.append(JiraClient.adf_para(activity.headline))
    blocks.extend(
        _section(
            "Context",
            [
                f"PR: {activity.title} ({activity.url})",
                f"Repository: {activity.repository}",
                f"Source to target: {activity.source_branch} to {activity.target_branch}",
                f"Head SHA: {activity.head_sha}",
                f"Author: {activity.author}",
                f"State: {activity.state}; draft: {str(activity.draft).lower()}",
            ],
        )
    )
    blocks.extend(_section("Commits", [f"{item.sha} — {item.subject}" for item in activity.commits]))
    blocks.extend(_section("Changes", list(_none(activity.changes))))
    blocks.extend(
        _section(
            "Validation",
            [f"{item.status.upper()} — {item.name}: {item.detail or 'No additional detail'}" for item in activity.validations]
            or ["Not reported"],
        )
    )
    blocks.extend(
        _section(
            "CI and merge state",
            [
                f"Checks: {activity.checks} — {activity.checks_detail}",
                f"Review: {activity.review_state} — {activity.review_detail}",
                f"Mergeability: {activity.mergeability}",
                f"Change size: {activity.changed_files} files, +{activity.additions}/-{activity.deletions}",
            ],
        )
    )
    blocks.extend(_section("Remaining work", list(_none(activity.remaining))))
    if activity.note:
        blocks.extend(_section("Source note", [f"Source: {activity.note_source or 'unspecified'}"]))
        blocks.append(JiraClient.adf_code_block(activity.note))
    evidence = [f"PR: {activity.url}"]
    if activity.github_comment_url:
        evidence.append(f"GitHub comment: {activity.github_comment_url}")
    blocks.extend(_section("Evidence", evidence))
    blocks.append(JiraClient.adf_para(marker))
    return JiraClient.adf_doc(blocks)


def render_review_adf(activity: ReviewActivityV1, marker: str) -> dict:
    round_label = str(activity.round) if activity.round is not None else "not specified"
    counts = Counter(finding.severity for finding in activity.findings)
    blocks = [
        JiraClient.adf_heading(
            f"Review round {round_label} — {activity.status.replace('_', ' ')}",
            level=3,
        )
    ]
    if activity.headline:
        blocks.append(JiraClient.adf_para(activity.headline))
    blocks.extend(
        _section(
            "Context",
            [
                f"PR: {activity.title} ({activity.url})",
                f"Repository: {activity.repository}",
                f"Area: {activity.area}",
                f"Reviewer: {activity.reviewer}",
                f"Head SHA: {activity.head_sha}",
            ],
        )
    )
    blocks.extend(_section("Findings", [f"{severity}: {counts.get(severity, 0)}" for severity in ("P0", "P1", "P2", "P3")]))
    finding_items = []
    for finding in activity.findings:
        location = finding.path + (f":{finding.line}" if finding.line is not None else "")
        line = f"[{finding.severity}] {finding.summary}" + (f" — {location}" if location else "")
        if finding.impact:
            line += f"; impact: {finding.impact}"
        if finding.required_action:
            line += f"; required action: {finding.required_action}"
        finding_items.append(line)
    blocks.extend(_section("Actionable findings", finding_items))
    blocks.extend(
        _section(
            "Validation performed",
            [f"{item.status.upper()} — {item.name}: {item.detail or 'No additional detail'}" for item in activity.validations]
            or ["Not reported"],
        )
    )
    blocks.extend(_section("Disposition", [activity.status.replace("_", " ").title()]))
    if activity.note:
        blocks.extend(_section("Source note", [f"Source: {activity.note_source or 'unspecified'}"]))
        blocks.append(JiraClient.adf_code_block(activity.note))
    evidence = [f"PR: {activity.url}"]
    if activity.review_url:
        evidence.append(f"GitHub review: {activity.review_url}")
    blocks.extend(_section("Evidence", evidence))
    blocks.append(JiraClient.adf_para(marker))
    return JiraClient.adf_doc(blocks)
