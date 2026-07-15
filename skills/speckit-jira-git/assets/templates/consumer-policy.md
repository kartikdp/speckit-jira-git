<!-- speckit-jira-git:start -->
## speckit-jira-git

Use the installed `speckit-jira-git` skill for Jira, Spec Kit, and linked GitHub PR activity. Resolve the CLI from `PATH` or from the installed skill root; do not hardcode an agent-specific installation directory.

Detect the Jira key from the branch, commits, PR title, or PR body. If no key is available, request it before writing to Jira. Run `--dry-run` first whenever the target issue, PR, review area, or activity content is uncertain.

Create Spec Kit Jira work in this order:

1. Specs Generation
2. Specs Review
3. Clarification Round(s)
4. Implementation Phase(s)
5. Code Review Round(s)
6. PR Review(s)

Use the CLI-generated stage-coded titles. Do not infer Jira transitions from checked source tasks, parent status, commits, CI, or PR state. Transition only when an explicit target status is requested.

Keep attribution and assignment separate. `review-to-jira --reviewer` identifies the actual human reviewer. PR Review tasks remain unassigned unless a human reviewer is explicitly supplied with `standard-tasks --pr-reviewer`. Configure reusable names in `.speckit-jira-git.toml`; never bake personal identities into shared instructions.

For Specs Review, attach the complete review packet with repeatable `--spec-file` arguments, including `spec.md`, `plan.md`, `tasks.md`, and available supporting research, data model, quickstart, checklist, and contracts.

After every successful push containing commits, verify the remote SHA and open PR. Post one structured PR conversation update containing all pushed commit SHAs, changes, truthful validation, observed CI/merge state, and remaining work, then synchronize it to Jira:

```bash
speckit-jira-git pr-to-jira --pr-url <PR_URL> --event updated \
  --commit <PUSHED_SHA> \
  --change "<change>" \
  --validation "passed|<check>|<observed result>" \
  --remaining "<remaining work or None>" \
  --post-github
```

Synchronize review activity with structured findings and actual reviewer attribution:

```bash
speckit-jira-git review-to-jira --pr-url <PR_URL> \
  --status <approved|changes_requested|commented|review_requested> \
  --reviewer "<human reviewer>" --round <N> --area <area> \
  --finding "P2|<summary>|<path>|<line>|<impact>|<required action>" \
  --validation "passed|<check>|<observed result>"
```

Never include secrets or claim checks, approvals, comments, or CI results that were not observed.
<!-- speckit-jira-git:end -->
