# Standard planning and review tasks

`standard-tasks` creates recurring process sub-tasks with structured descriptions containing objective, scope, required activities, deliverables, and acceptance criteria.

Supported kinds:

```text
specs-generation
specs-review
clarification-round
code-review
pr-review
fe-pr-review
be-pr-review
```

The CLI removes duplicates, sorts kinds into canonical workflow order, and prefixes summaries with stable stage codes. See `workflow-ordering.md`.

## Specs Generation and Specs Review

```bash
speckit-jira-git standard-tasks \
  --parent PROJ-123 \
  --kinds specs-generation,specs-review \
  --assignee "Delivery Engineer" \
  --specs-reviewer "Product Reviewer" \
  --spec-file specs/feature/spec.md \
  --spec-file specs/feature/plan.md \
  --spec-file specs/feature/tasks.md \
  --spec-file specs/feature/research.md \
  --spec-file specs/feature/data-model.md \
  --spec-file specs/feature/quickstart.md
```

`spec.md`, `plan.md`, and `tasks.md` are mandatory whenever Specs Review is requested. Add every available research file, data model, quickstart, requirements checklist, and referenced contract. Jira attachment uploads are idempotent by filename and byte size.

## Clarification and Code Review rounds

```bash
speckit-jira-git standard-tasks \
  --parent PROJ-123 \
  --kinds clarification-round,code-review \
  --round 2 \
  --assignee "Delivery Engineer"
```

Use separate invocations when clarification and code-review round numbers differ. Round numbers must be positive integers.

Use `--clarification-owner` when clarification belongs to a different human
than Specs Review. Assignment is role-specific: `--assignee` covers Specs
Generation and Code Review, while review/clarification/PR flags cover their
respective stages. Omitted roles remain unassigned unless configured.

## PR Review

PR Review is a reviewer activity and remains unassigned by default:

```bash
speckit-jira-git standard-tasks \
  --parent PROJ-123 \
  --kinds be-pr-review,fe-pr-review \
  --pr-url https://github.com/org/repo/pull/123
```

Assign it only when the human reviewer is known:

```bash
speckit-jira-git standard-tasks \
  --parent PROJ-123 \
  --kinds pr-review \
  --pr-reviewer "Human Reviewer"
```

Do not combine generic `pr-review` with repository-specific `be-pr-review` or `fe-pr-review` in one workflow.

## Updating existing tasks

```bash
speckit-jira-git standard-tasks \
  --parent PROJ-123 \
  --kinds specs-review \
  --spec-file spec.md --spec-file plan.md --spec-file tasks.md \
  --update-existing
```

Legacy unprefixed summaries are recognized and normalized. Updating does not change status or assignee. Creation likewise leaves the default Jira status unchanged.
