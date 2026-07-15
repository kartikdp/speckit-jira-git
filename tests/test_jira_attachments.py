import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "speckit-jira-git" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from jira_client import JiraClient  # noqa: E402
from jira_create_standard_tasks import _attach_missing_spec_files  # noqa: E402


class FakeJiraClient:
    def __init__(self, attachments: list[dict], contents: dict[str, bytes]) -> None:
        self.attachments = attachments
        self.contents = contents
        self.attached: list[Path] = []

    def get(self, path: str, params: dict | None = None) -> dict:
        return {"fields": {"attachment": list(self.attachments)}}

    def get_bytes(self, path_or_url: str) -> bytes:
        return self.contents[path_or_url]

    def attach_file(self, issue_key: str, file_path: str | Path) -> dict:
        path = Path(file_path)
        self.attached.append(path)
        return {"filename": path.name, "size": path.stat().st_size}


class JiraAttachmentTests(unittest.TestCase):
    def test_identical_attachment_is_not_uploaded_again(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spec.md"
            path.write_bytes(b"current")
            client = FakeJiraClient(
                [{"filename": "spec.md", "size": 7, "content": "/attachment/1"}],
                {"/attachment/1": b"current"},
            )

            added = _attach_missing_spec_files(client, "PROJ-1", (path,))

        self.assertEqual(added, ())
        self.assertEqual(client.attached, [])

    def test_same_name_and_size_with_changed_content_is_uploaded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spec.md"
            path.write_bytes(b"updated")
            client = FakeJiraClient(
                [{"filename": "spec.md", "size": 7, "content": "/attachment/1"}],
                {"/attachment/1": b"outdate"},
            )

            added = _attach_missing_spec_files(client, "PROJ-1", (path,))

        self.assertEqual(added, ("spec.md",))
        self.assertEqual([item.name for item in client.attached], ["spec.md"])

    def test_metadata_without_download_url_is_not_treated_as_current(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spec.md"
            path.write_bytes(b"current")
            client = FakeJiraClient(
                [{"filename": "spec.md", "size": 7}],
                {},
            )

            added = _attach_missing_spec_files(client, "PROJ-1", (path,))

        self.assertEqual(added, ("spec.md",))

    def test_binary_download_rejects_another_origin(self):
        config = SimpleNamespace(
            url="https://jira.example.com",
            email="user@example.com",
            token="secret",
        )
        client = JiraClient(config)

        with self.assertRaisesRegex(ValueError, "another origin"):
            client.get_bytes("https://evil.example.com/attachment/1")


if __name__ == "__main__":
    unittest.main()
