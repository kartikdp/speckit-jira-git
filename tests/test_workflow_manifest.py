import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "skills" / "speckit-jira-git" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from workflow_manifest import (  # noqa: E402
    format_story_title,
    normalize_phases,
    phase_title,
    sort_standard_kinds,
    standard_task_title,
)


class WorkflowManifestTests(unittest.TestCase):
    def test_standard_kinds_are_unique_and_canonical(self):
        actual = sort_standard_kinds(
            ["code-review", "specs-review", "specs-generation", "clarification-round", "code-review"],
            2,
        )
        self.assertEqual(
            actual,
            ["specs-generation", "specs-review", "clarification-round", "code-review"],
        )

    def test_generic_and_specific_pr_reviews_conflict(self):
        with self.assertRaisesRegex(ValueError, "not both"):
            sort_standard_kinds(["pr-review", "fe-pr-review"])

    def test_exact_standard_titles(self):
        self.assertEqual(standard_task_title("specs-generation", "Specs Generation"), "[01] Specs Generation")
        self.assertEqual(
            standard_task_title("clarification-round", "Clarification Round 3", 3),
            "[03.03] Clarification Round 3",
        )
        self.assertEqual(
            standard_task_title("fe-pr-review", "FE PR Review", pr_number=64),
            "[06.02] FE PR Review — PR #64",
        )

    def test_phase_sequence_is_sorted_and_contiguous(self):
        phases = [{"num": 2}, {"num": 1}]
        self.assertEqual([p["num"] for p in normalize_phases(phases)], [1, 2])
        self.assertEqual(phase_title(2, "Foundational"), "[04.02] Implementation Phase 2 — Foundational")

    def test_phase_gaps_and_duplicates_are_rejected(self):
        for phases in ([{"num": 1}, {"num": 1}], [{"num": 1}, {"num": 3}]):
            with self.subTest(phases=phases), self.assertRaises(ValueError):
                normalize_phases(phases)

    def test_story_title_omits_empty_workstream(self):
        self.assertEqual(
            format_story_title("{workstream} — {story_id} — {outcome}", "", "S-1", "deliver evidence"),
            "S-1 — deliver evidence",
        )


if __name__ == "__main__":
    unittest.main()
