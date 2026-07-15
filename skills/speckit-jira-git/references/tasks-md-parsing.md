# tasks.md parsing

`scripts/parse_tasks_md.py` turns a Spec Kit `tasks.md` into a JSON list of
phase records. This file documents what the parser expects and what it
extracts, so you know how to write a tasks.md that the skill can consume
cleanly, and how to fix things if extraction goes wrong.

## Input format expected

The parser is tolerant but expects the structure produced by
`/speckit-tasks`. Each phase looks roughly like this:

```markdown
## Phase 3: User Story 1 - Detect unhealthy agents (Priority: P1)

**Goal**: A running agent that stops responding is reported as unhealthy.

**Independent Test**: Deploy an agent, kill its process, verify state.

### Tests for User Story 1

- [ ] T008 [P] [US1] Write unit tests for compute_health_transition()...
- [ ] T009 [P] [US1] Write unit tests for get_deployed_agents()...

### Implementation for User Story 1

- [ ] T011 [US1] Implement compute_health_transition() in services/...
- [ ] T012 [US1] Implement get_deployed_agents() in services/...

**Checkpoint**: Backend health polling is complete.

---
```

The horizontal rule (`---`) at the bottom is optional but recommended. It
prevents the parser from accidentally pulling tasks from a different phase
when phase headings are missing.

## What the parser extracts

For each `## Phase N: ...` heading the parser produces a record:

```json
{
  "num": 3,
  "title": "User Story 1 - Detect unhealthy agents (Priority: P1)",
  "meta": {
    "purpose": "",
    "goal": "A running agent that stops responding is reported as unhealthy.",
    "independent_test": "Deploy an agent, kill its process, verify state.",
    "checkpoint": "Backend health polling is complete."
  },
  "tasks": [
    {"id": "T008", "tags": "[P] [US1]", "desc": "Write unit tests for compute_health_transition()..."},
    {"id": "T009", "tags": "[P] [US1]", "desc": "Write unit tests for get_deployed_agents()..."},
    {"id": "T011", "tags": "[US1]",     "desc": "Implement compute_health_transition() in services/..."},
    {"id": "T012", "tags": "[US1]",     "desc": "Implement get_deployed_agents() in services/..."}
  ]
}
```

The four `meta` keys are recognised when they appear as `**Purpose**:` /
`**Goal**:` / `**Independent Test**:` / `**Checkpoint**:` somewhere in the
phase body. They are optional individually; missing ones come back as empty
strings.

## Task line regex

```
^- \[[ xX]\] (T\d+)((?:\s*\[[^\]]+\])*)\s+(.+)$
```

So all of these are recognised as tasks:

```
- [ ] T008 Write unit tests
- [ ] T009 [P] Write more tests
- [ ] T010 [P] [US1] Write integration test
- [X] T001 Already done
```

The captured groups are: `id` (T-number), `tags` (the bracketed markers,
joined as a string), and `desc` (the rest of the line).

## Effort breakdown table (optional)

If your tasks.md contains an "Estimated Effort Breakdown" table near the
bottom, the parser can read it with the `--with-estimates` flag (or
`generate_subtasks_payload.py --from-table`). Expected shape:

```markdown
### Estimated Effort Breakdown

| Phase | Tasks | Estimate |
|-------|-------|----------|
| Setup | T001-T002 | 15m |
| Foundational | T003-T007 | 30m |
| User Story 1 backend | T008-T018 | 5h |
| User Story 2 frontend | T019-T022 | 3h |
| User Story 3 timing | T023-T025 | 1h |
| Validation | T026-T033 | 90m |
```

The parser keys the result by row order (1-based), not by phase number, so
the order of rows must match the order of `## Phase` headings in the file.
Jira time strings like `15m`, `30m`, `5h`, `90m`, `1h 30m` are accepted as
written; minute-suffixed forms like `15 min` are normalised to `15m`.

## When the output looks wrong

- **Phase missing entirely**: the heading is probably a different level
  (`### Phase 3:` instead of `## Phase 3:`). Fix to `##`.
- **Tasks missing**: a checkbox character is unusual. The parser accepts
  `[ ]`, `[X]`, `[x]`. Anything else (e.g. `[~]` for cancelled) is skipped.
- **Tasks bleeding into the wrong phase**: insert a `---` horizontal rule
  between phases.
- **Tags merged with description**: the parser only consumes contiguous
  `[...]` brackets immediately after the task id. If a tag includes a space
  it must still be one bracket pair: `[High Priority]`, not
  `[High] [Priority]` if they're meant as a single tag.

## Testing the parser

```bash
python scripts/parse_tasks_md.py path/to/tasks.md --pretty | head -40
python scripts/parse_tasks_md.py path/to/tasks.md --with-estimates --pretty
```

Run this whenever you change the tasks.md format. The parser should be
permissive; if it isn't, prefer fixing the parser over forcing tasks.md
into a fragile shape.
