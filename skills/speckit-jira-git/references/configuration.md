# Project configuration

Store non-secret workflow preferences in `.speckit-jira-git.toml` at the project root or an ancestor of the current directory.

```toml
[identity]
reviewer = "Human Reviewer"

[assignment]
default_assignee = "Delivery Engineer"
specs_reviewer = "Product Reviewer"
clarification_owner = "Product Owner"
pr_reviewer = "Independent Reviewer"

[titles]
story = "{workstream} — {story_id} — {outcome}"
```

Resolution rules:

- Explicit CLI arguments override configuration.
- Configuration overrides neutral empty defaults.
- No personal name or account ID is built into the package.
- Secrets do not belong in this file; use the Jira credential sources from `setup.md`.

`identity.reviewer` supplies review attribution when `review-to-jira --reviewer`
is omitted. `assignment.default_assignee` supplies Specs Generation and Code
Review assignment. `assignment.specs_reviewer` and
`assignment.clarification_owner` keep product/stakeholder work distinct.
`assignment.pr_reviewer` supplies PR Review assignment only when a project
intentionally configures it.

Render a parent story title without a Jira write:

```bash
speckit-jira-git story-title \
  --workstream "Group 4" \
  --story-id OBS-RUN-L0-1 \
  --outcome "define the contract boundary"
```

Supported title placeholders are `{workstream}`, `{story_id}`, and `{outcome}`. `story_id` and `outcome` are required inputs.
