import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "speckit-jira-git" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from github_client import GitHubClient  # noqa: E402


class FakeGitHubClient(GitHubClient):
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def get(self, path, params=None):
        self.calls.append((path, params))
        return self.pages[params["page"] - 1]


class GitHubClientTests(unittest.TestCase):
    def test_get_all_reads_every_list_page(self):
        client = FakeGitHubClient([[{"id": i} for i in range(100)], [{"id": 100}]])
        rows = client.get_all("/items")
        self.assertEqual(len(rows), 101)
        self.assertEqual([call[1]["page"] for call in client.calls], [1, 2])

    def test_get_all_reads_nested_check_runs(self):
        client = FakeGitHubClient([{"check_runs": [{"id": 1}]}])
        self.assertEqual(client.get_all("/checks", item_key="check_runs"), [{"id": 1}])

    def test_get_all_rejects_non_list_payloads(self):
        client = FakeGitHubClient([{"unexpected": []}])
        with self.assertRaises(RuntimeError):
            client.get_all("/items")


if __name__ == "__main__":
    unittest.main()
