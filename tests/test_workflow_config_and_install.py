import os
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "speckit-jira-git" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from install_instructions import END, START, _ensure_claude_import, _policy, _upsert  # noqa: E402
from workflow_config import load_workflow_config  # noqa: E402


class WorkflowConfigAndInstallTests(unittest.TestCase):
    def test_config_is_neutral_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = Path.cwd()
            os.chdir(directory)
            try:
                config = load_workflow_config()
            finally:
                os.chdir(previous)
        self.assertEqual(config.reviewer, "")
        self.assertEqual(config.default_assignee, "")
        self.assertEqual(config.specs_reviewer, "")
        self.assertEqual(config.clarification_owner, "")
        self.assertEqual(config.pr_reviewer, "")

    def test_config_loads_identity_assignment_and_title(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".speckit-jira-git.toml"
            path.write_text(
                '[identity]\nreviewer = "Human Reviewer"\n'
                '[assignment]\ndefault_assignee = "Delivery Engineer"\n'
                'specs_reviewer = "Product Reviewer"\n'
                'clarification_owner = "Product Owner"\n'
                '[titles]\nstory = "{story_id} — {outcome}"\n',
                encoding="utf-8",
            )
            config = load_workflow_config(path)
        self.assertEqual(config.reviewer, "Human Reviewer")
        self.assertEqual(config.default_assignee, "Delivery Engineer")
        self.assertEqual(config.specs_reviewer, "Product Reviewer")
        self.assertEqual(config.clarification_owner, "Product Owner")
        self.assertEqual(config.story_title_template, "{story_id} — {outcome}")

    def test_policy_upsert_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "AGENTS.md"
            _upsert(path, _policy())
            first = path.read_text(encoding="utf-8")
            _upsert(path, _policy())
            second = path.read_text(encoding="utf-8")
        self.assertEqual(first, second)
        self.assertEqual(second.count(START), 1)
        self.assertEqual(second.count(END), 1)

    def test_claude_import_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "CLAUDE.md"
            _ensure_claude_import(path)
            _ensure_claude_import(path)
            value = path.read_text(encoding="utf-8")
        self.assertEqual(value.count("@AGENTS.md"), 1)


if __name__ == "__main__":
    unittest.main()
