import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "speckit-jira-git" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from activity_contracts import (  # noqa: E402
    CommitEvidence,
    PullRequestActivityV1,
    ReviewActivityV1,
    ReviewFinding,
    ValidationEvidence,
)
from activity_renderers import (  # noqa: E402
    render_pr_adf,
    render_pr_markdown,
    render_review_markdown,
)


class ActivityRendererTests(unittest.TestCase):
    def _pr(self):
        return PullRequestActivityV1(
            event="updated", repository="org/repo", number=7, title="Improve workflow",
            url="https://github.com/org/repo/pull/7", author="author",
            source_branch="feature/PROJ-7", target_branch="develop", head_sha="abc123",
            state="open", draft=False, mergeability="clean", checks="passed",
            checks_detail="2 success", review_state="approved", review_detail="reviewer",
            changed_files=2, additions=10, deletions=1,
            commits=(CommitEvidence("abc123", "feat: improve workflow"),),
            changes=("Normalized titles",),
            validations=(ValidationEvidence("passed", "unit tests", "12 passed"),),
            remaining=("None",),
        )

    def test_pr_markdown_has_deterministic_sections(self):
        rendered = render_pr_markdown(self._pr())
        headings = [
            "#### Context", "#### Commits", "#### Changes", "#### Validation",
            "#### CI and merge state", "#### Remaining work", "#### Evidence",
        ]
        positions = [rendered.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("`abc123` — feat: improve workflow", rendered)

    def test_pr_adf_contains_marker(self):
        marker = "speckit-jira-git:v1:test"
        adf = render_pr_adf(self._pr(), marker)
        self.assertEqual(adf["type"], "doc")
        self.assertIn(marker, str(adf))

    def test_review_markdown_contains_actionable_finding(self):
        activity = ReviewActivityV1(
            status="changes_requested", repository="org/repo", number=7,
            title="Improve workflow", url="https://github.com/org/repo/pull/7",
            area="backend", reviewer="Human Reviewer", round=1, head_sha="abc123",
            findings=(ReviewFinding("P2", "Reject bad cursor", "api.py", 42, "Restarts", "Return 400"),),
        )
        rendered = render_review_markdown(activity)
        self.assertIn("[P2] Reject bad cursor — `api.py:42`", rendered)
        self.assertIn("Required action: Return 400", rendered)


if __name__ == "__main__":
    unittest.main()
