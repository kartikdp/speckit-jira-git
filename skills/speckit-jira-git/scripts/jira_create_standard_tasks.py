"""Create standard Jira sub-tasks for planning, specs, review, and PR work."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

from github_client import parse_pr_url
from jira_client import JiraClient
from workflow_config import load_workflow_config
from workflow_manifest import sort_standard_kinds, standard_task_position, standard_task_title


@dataclass(frozen=True)
class TaskTemplate:
    title: str
    objective: str
    scope: tuple[str, ...]
    activities: tuple[str, ...]
    deliverables: tuple[str, ...]
    acceptance_criteria: tuple[str, ...]


TASK_TEMPLATES = {
    "specs-generation": TaskTemplate(
        title="Specs Generation",
        objective="Produce a complete, internally consistent Spec Kit packet that turns the parent story into testable product and engineering requirements.",
        scope=(
            "Feature specification, user scenarios, functional requirements, edge cases, and measurable success criteria.",
            "Implementation plan, technical context, constraints, dependencies, and architecture decisions.",
            "Dependency-ordered implementation tasks, contracts, data model, research, quickstart, and requirement checklist where applicable.",
        ),
        activities=(
            "Reconcile the parent Jira story, acceptance criteria, linked designs, dependencies, and non-goals.",
            "Generate or update the Spec Kit artifacts and remove unresolved placeholders or contradictory requirements.",
            "Trace every acceptance criterion to planned implementation and validation work.",
            "Record open questions explicitly for the clarification round instead of silently assuming behavior.",
        ),
        deliverables=(
            "A version-controlled Spec Kit packet with spec.md, plan.md, and tasks.md.",
            "Supporting research, data model, contracts, quickstart, and quality checklist required by the feature.",
            "A concise Jira update identifying the canonical spec directory and any unresolved decisions.",
        ),
        acceptance_criteria=(
            "The packet is complete enough for an independent reviewer to understand scope, behavior, constraints, and validation without reconstructing requirements from chat history.",
            "Requirements are testable, uniquely identified where the template requires identifiers, and mapped to actionable tasks.",
            "Dependencies, risks, non-goals, and cross-repository ownership boundaries are explicit.",
            "No unresolved NEEDS CLARIFICATION markers or undocumented scope assumptions remain.",
        ),
    ),
    "specs-review": TaskTemplate(
        title="Specs Review",
        objective="Independently verify that the attached Spec Kit packet is complete, consistent, feasible, and traceable to the parent Jira story before implementation or release decisions rely on it.",
        scope=(
            "Attached specification, plan, tasks, research, data model, contracts, quickstart, and requirements checklist.",
            "Parent-story acceptance criteria, dependencies, role and tenant boundaries, failure behavior, compatibility, and validation strategy.",
            "Cross-artifact consistency and coverage of frontend, backend, data, migration, security, and operational impact where applicable.",
        ),
        activities=(
            "Read the attached artifacts as the review baseline and confirm they match the canonical repository versions.",
            "Check acceptance-criteria traceability, missing scenarios, contradictions, ambiguous language, and unplanned work.",
            "Verify feasibility against current architecture and identify compatibility or migration risks.",
            "Record actionable findings with exact artifact sections and distinguish blockers from recommendations.",
        ),
        deliverables=(
            "A review outcome of approved, changes requested, or blocked, with a concise rationale.",
            "Actionable findings linked to exact attached artifacts and sections.",
            "Confirmation that all required Spec Kit artifacts are attached to this Jira task and identify the reviewed revision.",
        ),
        acceptance_criteria=(
            "The complete review packet is attached to this task and can be opened without local filesystem access.",
            "Every parent-story acceptance criterion is covered by the specification and at least one validation task.",
            "The plan and tasks do not contradict the specification, duplicate existing ownership, or omit required compatibility work.",
            "The final review decision and all remaining blockers are recorded in Jira.",
        ),
    ),
    "clarification-round": TaskTemplate(
        title="Clarification Round {round}",
        objective="Resolve material ambiguities that could change scope, contracts, implementation, estimates, or acceptance behavior.",
        scope=(
            "Open questions from specification review, code discovery, design review, and stakeholder feedback.",
            "Decisions affecting API contracts, data ownership, role behavior, failure modes, migrations, compatibility, or validation.",
        ),
        activities=(
            "List each unresolved question with context, options, trade-offs, and a recommended decision.",
            "Obtain an authoritative answer from the appropriate owner instead of inferring product behavior.",
            "Apply each decision consistently to Jira and all affected Spec Kit artifacts.",
            "Re-run consistency checks and identify any follow-up tasks created by the decisions.",
        ),
        deliverables=(
            "A decision log containing every question, answer, owner, and affected artifact.",
            "Updated specification, plan, tasks, contracts, and Jira acceptance criteria where required.",
            "A clear list of remaining blockers, or an explicit statement that the round is closed.",
        ),
        acceptance_criteria=(
            "No material question in the round remains unanswered or hidden in comments.",
            "Decisions are reflected consistently across every affected artifact.",
            "New scope or dependencies are represented by explicit tasks and estimates rather than implicit expectations.",
        ),
    ),
    "code-review": TaskTemplate(
        title="Code Review Round {round}",
        objective="Review the implementation against the approved requirements and current target branch, and report only reproducible, actionable findings.",
        scope=(
            "Actual current diff against the latest target branch, including merge-resolution changes.",
            "Correctness, contracts, data access, authorization and tenant isolation, compatibility, migrations, error handling, performance, and maintainability.",
            "Focused unit, contract, integration, build, lint, and static-analysis evidence appropriate to the change.",
        ),
        activities=(
            "Verify the reviewed head and base revisions before inspecting the diff.",
            "Trace changed behavior through callers, persistence, contracts, and tests.",
            "Run focused validation and separate confirmed defects from false positives or pre-existing issues.",
            "Record findings by severity with exact file and line references, impact, and a concrete remediation direction.",
        ),
        deliverables=(
            "A severity-ordered review report with exact code references and validation evidence.",
            "An explicit status for prior findings: resolved, still present, or superseded.",
            "A clear review outcome and remaining test or environment limitations.",
        ),
        acceptance_criteria=(
            "The review uses the actual current diff and verified revisions, not stale comments.",
            "Every finding is actionable, reproducible, in scope, and supported by code or test evidence.",
            "Required checks are run or the exact reason they could not run is documented.",
            "No review approval or authorship is impersonated by an automation account.",
        ),
    ),
    "pr-review": TaskTemplate(
        title="PR Review",
        objective="Perform the final pull-request review using the current head, current base, CI evidence, and linked Jira requirements.",
        scope=(
            "Complete PR diff, commits, merge base, conflicts, CI checks, linked specifications, and Jira acceptance criteria.",
            "Regression risk, release readiness, unresolved review threads, and required follow-up work.",
        ),
        activities=(
            "Verify PR identity, head SHA, base SHA, mergeability, and linked Jira key.",
            "Review the actual current diff and confirm earlier findings against the current head.",
            "Inspect required CI and execute focused local validation where risk warrants it.",
            "Record the review outcome and remaining blockers without transitioning Jira automatically.",
        ),
        deliverables=(
            "A PR review decision with severity-ordered actionable findings or an explicit no-findings result.",
            "Observed CI, mergeability, and validation evidence.",
            "A Jira comment linking the PR review activity and current outcome.",
        ),
        acceptance_criteria=(
            "The reviewed SHAs and current diff are explicitly verified.",
            "All required checks and unresolved review threads are accounted for.",
            "The task is assigned only to an explicitly selected reviewer, or remains unassigned.",
            "Jira status changes occur only when the user explicitly requests a target status.",
        ),
    ),
    "fe-pr-review": TaskTemplate(
        title="FE PR Review",
        objective="Review the frontend pull request for functional correctness, contract alignment, resilient UI state handling, accessibility, and visual regressions.",
        scope=(
            "Current frontend diff, API integrations, loading and error states, role-aware behavior, state freshness, and navigation.",
            "TypeScript compilation, lint, focused tests, production build, and browser evidence for affected workflows.",
        ),
        activities=(
            "Verify current PR head/base and reconcile the UI with the approved specification and backend contract.",
            "Exercise success, empty, loading, permission, partial-data, stale-data, and failure states.",
            "Check accessibility, responsive behavior, design-system consistency, and unintended legacy/new view overlap.",
            "Record actionable findings with exact component references and reproducible steps.",
        ),
        deliverables=(
            "A frontend PR review decision with exact findings or an explicit no-findings result.",
            "Build, lint, typecheck, test, and browser-validation evidence.",
            "A Jira-linked review update containing current SHA and remaining blockers.",
        ),
        acceptance_criteria=(
            "The frontend compiles and required checks pass, or failures are documented accurately.",
            "Affected user and role workflows are verified against the current backend contract.",
            "Visual and state-management regressions are either resolved or recorded as actionable findings.",
            "The task is assigned only to an explicitly selected reviewer, or remains unassigned.",
        ),
    ),
    "be-pr-review": TaskTemplate(
        title="BE PR Review",
        objective="Review the backend pull request for contract correctness, bounded data access, authorization, durable-state semantics, compatibility, and operational safety.",
        scope=(
            "Current backend diff, routes, services, persistence queries, migrations, schemas, provider evidence, and error envelopes.",
            "Tenant isolation, platform-admin cross-tenant behavior, stable pagination, secret redaction, concurrency, and compatibility with the latest target branch.",
            "Unit, contract, integration, database-backed, migration, lint, and static-analysis evidence appropriate to the change.",
        ),
        activities=(
            "Verify current PR head/base and trace changed endpoints through services, stores, and schemas.",
            "Inspect query bounds, filtering and pagination order, durable freshness timestamps, identities, and migrations.",
            "Validate authorization boundaries, provider evidence, support references, cloud identifiers, and redaction.",
            "Run focused tests and record only reproducible findings with exact code references.",
        ),
        deliverables=(
            "A backend PR review decision with severity-ordered actionable findings or an explicit no-findings result.",
            "Focused unit, contract, integration, and database-backed validation evidence.",
            "A Jira-linked review update containing current SHA, CI state, and remaining blockers.",
        ),
        acceptance_criteria=(
            "API behavior and schemas match the approved contract and remain backward compatible where required.",
            "Data access is bounded, tenant-safe, secret-safe, and stable under concurrent inserts or updates.",
            "Migrations and durable-state identity/freshness behavior are validated against the latest target branch.",
            "The task is assigned only to an explicitly selected reviewer, or remains unassigned.",
        ),
    ),
}

PR_REVIEW_KINDS = {"pr-review", "fe-pr-review", "be-pr-review"}


@dataclass(frozen=True)
class CreatedTask:
    key: str | None
    summary: str
    created: bool
    reason: str = ""
    attachments_added: tuple[str, ...] = ()


def _subtask_type_id(client: JiraClient) -> str:
    project = client.get(f"/rest/api/3/project/{client.config.project}") or {}
    issue_types = project.get("issueTypes", [])
    for issue_type in issue_types:
        if issue_type.get("subtask") and issue_type.get("name") in {"Sub-task", "Subtask"}:
            return issue_type["id"]
    raise SystemExit(
        f"ERROR: no Sub-task issue type found for Jira project {client.config.project}"
    )


def _existing_by_summary(
    client: JiraClient,
    parent: str,
    summary_aliases: dict[str, tuple[str, ...]],
) -> dict[str, str]:
    aliases = {alias for values in summary_aliases.values() for alias in values}
    if not aliases:
        return {}
    issues = client.search_jql_all(
        f"parent = {parent}",
        fields=["summary"],
        page_size=100,
        max_total=1000,
    )
    by_alias = {
        issue["fields"]["summary"]: issue["key"]
        for issue in issues
        if issue["fields"]["summary"] in aliases
    }
    matches: dict[str, str] = {}
    for canonical, values in summary_aliases.items():
        # Aliases are ordered canonical-first, so an already-normalized task
        # wins if both canonical and legacy summaries happen to exist.
        for alias in values:
            if alias in by_alias:
                matches[canonical] = by_alias[alias]
                break
    return matches


def _description(
    client: JiraClient,
    template: TaskTemplate,
    label: str,
    pr_url: str | None,
    spec_files: tuple[Path, ...],
) -> dict:
    lines = [
        client.adf_heading(label, level=4),
        client.adf_para(template.objective),
        client.adf_heading("Scope", level=5),
        client.adf_bullet_list(list(template.scope)),
        client.adf_heading("Required activities", level=5),
        client.adf_bullet_list(list(template.activities)),
        client.adf_heading("Deliverables", level=5),
        client.adf_bullet_list(list(template.deliverables)),
        client.adf_heading("Acceptance criteria", level=5),
        client.adf_bullet_list(list(template.acceptance_criteria)),
    ]
    if spec_files:
        lines.extend(
            [
                client.adf_heading("Attached Spec Kit review packet", level=5),
                client.adf_bullet_list([path.name for path in spec_files]),
            ]
        )
    if pr_url:
        lines.extend(
            [
                client.adf_heading("Pull request", level=5),
                client.adf_para(pr_url),
            ]
        )
    return client.adf_doc(lines)


def _legacy_summary(kind: str, round_label: str, prefix: str) -> str:
    title = TASK_TEMPLATES[kind].title.format(round=round_label or "1")
    return f"{prefix}{title}" if prefix else title


def _summary(
    kind: str,
    round_label: str,
    prefix: str,
    pr_number: int | None = None,
) -> str:
    label = _legacy_summary(kind, round_label, prefix)
    return standard_task_title(kind, label, round_label or "1", pr_number=pr_number)


def _validate_spec_files(raw_paths: list[str]) -> tuple[Path, ...]:
    resolved: list[Path] = []
    seen: set[Path] = set()
    for raw_path in raw_paths:
        path = Path(raw_path).expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"ERROR: spec attachment does not exist or is not a file: {path}")
        if path not in seen:
            resolved.append(path)
            seen.add(path)
    return tuple(resolved)


def _attach_missing_spec_files(
    client: JiraClient,
    issue_key: str,
    spec_files: tuple[Path, ...],
) -> tuple[str, ...]:
    issue = client.get(
        f"/rest/api/3/issue/{issue_key}",
        params={"fields": "attachment"},
    )
    existing = issue.get("fields", {}).get("attachment") or []
    added: list[str] = []
    for path in spec_files:
        local_content = path.read_bytes()
        candidates = [
            item
            for item in existing
            if item.get("filename") == path.name
            and item.get("size") == len(local_content)
            and item.get("content")
        ]
        matches_current = False
        for item in candidates:
            try:
                matches_current = client.get_bytes(item["content"]) == local_content
            except (RuntimeError, ValueError):
                matches_current = False
            if matches_current:
                break
        if matches_current:
            continue
        attached = client.attach_file(issue_key, path)
        added.append(path.name)
        existing.append(
            {
                "filename": path.name,
                "size": len(local_content),
                "content": attached.get("content") if isinstance(attached, dict) else None,
            }
        )
    return tuple(added)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create standard planning/review Jira sub-tasks")
    parser.add_argument("--parent", required=True, help="Parent Jira issue key")
    parser.add_argument(
        "--kinds",
        required=True,
        help="Comma-separated kinds: specs-generation,specs-review,clarification-round,code-review,pr-review,fe-pr-review,be-pr-review",
    )
    parser.add_argument("--round", default="1", help="Round number for round-based task names")
    parser.add_argument("--assignee", default="", help="Assignee for non-PR tasks")
    parser.add_argument("--reviewer", default="", help=argparse.SUPPRESS)
    parser.add_argument(
        "--specs-reviewer",
        default="",
        help="Human assignee for Specs Review; omit to leave it unassigned.",
    )
    parser.add_argument(
        "--clarification-owner",
        default="",
        help="Human assignee for Clarification rounds; defaults to Specs Review assignee.",
    )
    parser.add_argument(
        "--pr-reviewer",
        default="",
        help="Assignee for PR Review tasks. Omit to leave them unassigned.",
    )
    parser.add_argument("--estimate", default="", help='Original estimate, e.g. "3h"')
    parser.add_argument("--priority", default="", help="Optional Jira priority name")
    parser.add_argument("--pr-url", default="", help="Optional pull request URL")
    parser.add_argument(
        "--spec-file",
        action="append",
        default=[],
        help="Spec Kit artifact to attach to Specs Review. Repeat for the complete review packet.",
    )
    parser.add_argument("--prefix", default="", help="Optional summary prefix")
    parser.add_argument("--config", default="", help="Optional .speckit-jira-git.toml path")
    parser.add_argument("--allow-duplicates", action="store_true")
    parser.add_argument(
        "--update-existing",
        action="store_true",
        help="Update matching existing tasks with the current detailed description and missing spec attachments.",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    kinds = [kind.strip() for kind in args.kinds.split(",") if kind.strip()]
    unknown = [kind for kind in kinds if kind not in TASK_TEMPLATES]
    if unknown:
        raise SystemExit(f"ERROR: unknown task kinds: {', '.join(unknown)}")
    try:
        kinds = sort_standard_kinds(kinds, args.round)
        config = load_workflow_config(args.config or None)
    except ValueError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
    spec_files = _validate_spec_files(args.spec_file)
    if "specs-review" in kinds:
        required_core = {"spec.md", "plan.md", "tasks.md"}
        missing_core = sorted(required_core - {path.name for path in spec_files})
        if missing_core:
            raise SystemExit(
                "ERROR: Specs Review requires the core Spec Kit packet. Missing --spec-file "
                f"attachments: {', '.join(missing_core)}. Include supporting artifacts too."
            )

    client = JiraClient()
    subtask_type_id = _subtask_type_id(client)
    explicit_general_assignee = (args.assignee or args.reviewer).strip()
    assignee_name = (explicit_general_assignee or config.default_assignee).strip()
    if args.reviewer:
        print("WARNING: --reviewer is deprecated for standard-tasks; use --assignee.")
    specs_reviewer_name = (
        args.specs_reviewer or config.specs_reviewer or explicit_general_assignee
    ).strip()
    clarification_owner_name = (
        args.clarification_owner
        or config.clarification_owner
        or specs_reviewer_name
        or explicit_general_assignee
    ).strip()
    pr_reviewer_name = (args.pr_reviewer or config.pr_reviewer).strip()

    def resolve_account(name: str, label: str) -> str | None:
        if not name:
            return None
        account_id = client.find_user_account_id(name)
        if not account_id:
            raise SystemExit(f"ERROR: could not resolve {label} '{name}' to a Jira accountId")
        return account_id

    general_assignee = resolve_account(
        assignee_name,
        "assignee",
    ) if any(kind in {"specs-generation", "code-review"} for kind in kinds) else None
    specs_reviewer_assignee = resolve_account(
        specs_reviewer_name,
        "Specs Review assignee",
    ) if "specs-review" in kinds else None
    clarification_owner_assignee = resolve_account(
        clarification_owner_name,
        "Clarification owner",
    ) if "clarification-round" in kinds else None
    pr_reviewer_assignee = resolve_account(
        pr_reviewer_name,
        "PR Review assignee",
    ) if any(kind in PR_REVIEW_KINDS for kind in kinds) else None
    pr_number = None
    if args.pr_url:
        try:
            pr_number = parse_pr_url(args.pr_url).number
        except ValueError as exc:
            raise SystemExit(f"ERROR: {exc}") from exc
    summaries = [_summary(kind, args.round, args.prefix, pr_number) for kind in kinds]
    aliases = {
        summary: (summary, _legacy_summary(kind, args.round, args.prefix))
        for kind, summary in zip(kinds, summaries, strict=True)
    }
    existing = (
        {}
        if args.allow_duplicates
        else _existing_by_summary(client, args.parent, aliases)
    )

    results: list[CreatedTask] = []
    for kind, summary in zip(kinds, summaries, strict=True):
        if summary in existing:
            issue_key = existing[summary]
            if not args.update_existing:
                results.append(
                    CreatedTask(key=issue_key, summary=summary, created=False, reason="duplicate")
                )
                continue
            template = TASK_TEMPLATES[kind]
            label = template.title.format(round=args.round)
            description_spec_files = spec_files if kind == "specs-review" else ()
            if args.dry_run:
                results.append(
                    CreatedTask(
                        key=issue_key,
                        summary=summary,
                        created=False,
                        reason="dry-run-update",
                        attachments_added=tuple(path.name for path in description_spec_files),
                    )
                )
                continue
            client.put(
                f"/rest/api/3/issue/{issue_key}",
                {
                    "fields": {
                        "summary": summary,
                        "description": _description(
                            client,
                            template,
                            label,
                            args.pr_url or None,
                            description_spec_files,
                        )
                    }
                },
            )
            attachments_added = (
                _attach_missing_spec_files(client, issue_key, description_spec_files)
                if description_spec_files
                else ()
            )
            results.append(
                CreatedTask(
                    key=issue_key,
                    summary=summary,
                    created=False,
                    reason="updated",
                    attachments_added=attachments_added,
                )
            )
            continue
        template = TASK_TEMPLATES[kind]
        label = template.title.format(round=args.round)
        description_spec_files = spec_files if kind == "specs-review" else ()
        fields = {
            "project": {"key": client.config.project},
            "issuetype": {"id": subtask_type_id},
            "summary": summary,
            "parent": {"key": args.parent},
            "description": _description(
                client,
                template,
                label,
                args.pr_url or None,
                description_spec_files,
            ),
            "labels": list(standard_task_position(kind, args.round).labels),
        }
        if kind in PR_REVIEW_KINDS:
            assignee = pr_reviewer_assignee
        elif kind == "specs-review":
            assignee = specs_reviewer_assignee
        elif kind == "clarification-round":
            assignee = clarification_owner_assignee
        else:
            assignee = general_assignee
        if assignee:
            fields["assignee"] = {"accountId": assignee}
        if args.estimate:
            fields["timetracking"] = {"originalEstimate": args.estimate}
        if args.priority:
            fields["priority"] = {"name": args.priority}
        if args.dry_run:
            results.append(
                CreatedTask(
                    key=None,
                    summary=summary,
                    created=False,
                    reason="dry-run",
                    attachments_added=tuple(path.name for path in description_spec_files),
                )
            )
            continue
        result = client.post("/rest/api/3/issue", {"fields": fields}) or {}
        issue_key = result.get("key")
        attachments_added = (
            _attach_missing_spec_files(client, issue_key, description_spec_files)
            if issue_key and description_spec_files
            else ()
        )
        results.append(
            CreatedTask(
                key=issue_key,
                summary=summary,
                created=True,
                attachments_added=attachments_added,
            )
        )

    payload = {"results": [result.__dict__ for result in results]}
    print(json.dumps(payload, indent=2) if args.json else "\n".join(str(r) for r in results))


if __name__ == "__main__":
    main()
