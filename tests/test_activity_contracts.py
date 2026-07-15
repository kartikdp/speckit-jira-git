import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "speckit-jira-git" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from activity_contracts import one_line, parse_finding, parse_validation, redact_text  # noqa: E402
from git_pr_activity_to_jira import _selected_commits  # noqa: E402


class ActivityContractTests(unittest.TestCase):
    def test_validation_parser(self):
        item = parse_validation("passed|unit tests|42 passed")
        self.assertEqual((item.status, item.name, item.detail), ("passed", "unit tests", "42 passed"))

    def test_finding_parser(self):
        item = parse_finding("P2|Reject cursor|api.py|42|Restarts paging|Return 400")
        self.assertEqual(item.severity, "P2")
        self.assertEqual(item.line, 42)
        self.assertEqual(item.required_action, "Return 400")

    def test_invalid_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_validation("unknown|test|detail")
        with self.assertRaises(ValueError):
            parse_finding("P9|bad")
        with self.assertRaises(ValueError):
            one_line("line one\nline two", "headline")
        with self.assertRaises(ValueError):
            parse_validation("passed|unit tests|line one\nline two")

    def test_secrets_are_redacted(self):
        value = redact_text(
            "JIRA_TOKEN=secret Bearer abc.def https://user:password@example.com ghp_abcdefghijklmnopqrstuvwxyz"
        )
        self.assertNotIn("secret", value)
        self.assertNotIn("abc.def", value)
        self.assertNotIn("password", value)
        self.assertNotIn("ghp_", value)

    def test_explicit_pushed_commits_are_resolved_in_requested_order(self):
        commits = [
            {"sha": "a" * 40, "commit": {"message": "first"}},
            {"sha": "b" * 40, "commit": {"message": "second"}},
        ]
        selected = _selected_commits(commits, ["bbbbbbbb", "aaaaaaaa"])
        self.assertEqual([item["sha"][0] for item in selected], ["b", "a"])
        with self.assertRaisesRegex(ValueError, "exactly one"):
            _selected_commits(commits, ["cccccccc"])


if __name__ == "__main__":
    unittest.main()
