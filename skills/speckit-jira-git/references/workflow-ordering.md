# Canonical Jira workflow ordering

The delivery sequence is stable across stories:

| Stage | Kind | Canonical title |
|---|---|---|
| 01 | Specs Generation | `[01] Specs Generation` |
| 02 | Specs Review | `[02] Specs Review` |
| 03 | Clarification round N | `[03.NN] Clarification Round N` |
| 04 | Implementation phase N | `[04.NN] Implementation Phase N — <phase title>` |
| 05 | Code review round N | `[05.NN] Code Review Round N` |
| 06 | PR review | `[06.NN] <area> PR Review — PR #N` |

`standard-tasks` sorts process kinds before creation and adds `speckit-stage-*` and `speckit-sequence-*` labels. `generate-subtasks` validates that implementation phases are positive, unique, and contiguous from Phase 1 before producing payloads.

The numeric prefix is the portable ordering mechanism. Jira Rank is board-specific and is not mutated implicitly. Teams may rank issues separately after creation without changing the canonical titles.

Backend and frontend PR reviews use deterministic slots 06.01 and 06.02. Generic PR Review occupies 06.01 and must not coexist with repository-specific PR Review tasks in the same workflow.

Parent story titles are configuration-driven and default to:

```text
{workstream} — {story_id} — {outcome}
```

Use `story-title` to render them. The CLI does not create or rename a Jira parent story implicitly.

Creation and normalization never transition Jira status. `[X]` source checkboxes, merged PRs, CI state, or parent status are not transition instructions.
