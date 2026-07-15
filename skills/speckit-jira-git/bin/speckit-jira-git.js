#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __filename = fileURLToPath(import.meta.url);
const root = path.resolve(path.dirname(__filename), "..");

const commands = new Map([
  ["setup-check", "setup_check.py"],
  ["find-jira-key", "git_find_jira_key.py"],
  ["pr-to-jira", "git_pr_activity_to_jira.py"],
  ["review-to-jira", "git_review_activity_to_jira.py"],
  ["standard-tasks", "jira_create_standard_tasks.py"],
  ["story-title", "format_story_title.py"],
  ["time-report", "jira_time_report.py"],
  ["find-parent", "find_parent_story.py"],
  ["generate-subtasks", "generate_subtasks_payload.py"],
  ["push-subtasks", "push_subtasks.py"],
  ["add-comment", "add_comment.py"],
  ["log-worklog", "log_worklog.py"],
  ["update-worklog", "update_worklog.py"],
  ["transition", "transition_issue.py"],
  ["update-estimate", "update_estimate.py"],
  ["discover-project", "discover_project_metadata.py"],
  ["install-instructions", "install_instructions.py"],
]);

function printHelp() {
  console.log(`speckit-jira-git

Usage:
  speckit-jira-git <command> [args...]

Primary use cases:
  setup             Check Jira/GitHub access and show the credentials file to update
                    Commands: setup-check, install-instructions

  plan-to-jira      Add stories/tasks/sub-tasks from Spec Kit plans into Jira
                    Commands: story-title, find-parent, standard-tasks, generate-subtasks, push-subtasks

  sync-git-jira     Sync GitHub PR/review status back to the linked Jira story
                    Commands: find-jira-key, pr-to-jira, review-to-jira

  time-logging      Check, add, update, and report Jira logged hours
                    Commands: log-worklog, update-worklog, time-report

  jira-maintenance  Add comments, move issues, update estimates, inspect project metadata
                    Commands: add-comment, transition, update-estimate, discover-project

Common examples:
  speckit-jira-git setup-check
  speckit-jira-git story-title --workstream "Group 4" --story-id OBS-RUN-L0-1 --outcome "define the contract boundary"
  speckit-jira-git standard-tasks --parent PROJ-123 --kinds specs-review --spec-file specs/012-feature/spec.md --spec-file specs/012-feature/plan.md --spec-file specs/012-feature/tasks.md
  speckit-jira-git pr-to-jira --pr-url https://github.com/org/repo/pull/123 --event updated --commit abc123 --change "Implemented contract" --validation "passed|unit tests|42 passed" --remaining "None" --post-github
  speckit-jira-git review-to-jira --pr-url https://github.com/org/repo/pull/123 --status changes_requested --reviewer "Human Reviewer" --round 1 --finding "P2|Validate cursor|src/api.ts|42|Bad cursors restart pagination|Return HTTP 400"
  speckit-jira-git time-report --from 2026-07-01 --to 2026-07-15 --markdown exports/time.md

Run a command with --help for command-specific options.
`);
}

const [command, ...args] = process.argv.slice(2);

if (!command || command === "-h" || command === "--help" || command === "help") {
  printHelp();
  process.exit(0);
}

if (!commands.has(command)) {
  console.error(`Unknown command: ${command}`);
  console.error("Run `speckit-jira-git --help` for available commands.");
  process.exit(2);
}

const script = path.join(root, "scripts", commands.get(command));
const result = spawnSync("python3", [script, ...args], {
  cwd: process.cwd(),
  stdio: "inherit",
  env: process.env,
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}

process.exit(result.status ?? 0);
