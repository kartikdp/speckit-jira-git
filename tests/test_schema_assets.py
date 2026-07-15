import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "skills" / "speckit-jira-git" / "assets" / "schemas"


class SchemaAssetTests(unittest.TestCase):
    def test_versioned_schemas_are_packaged_and_strict(self):
        for name in ("pr-activity-v1.schema.json", "review-activity-v1.schema.json"):
            with self.subTest(name=name):
                schema = json.loads((SCHEMAS / name).read_text(encoding="utf-8"))
                self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
                self.assertFalse(schema["additionalProperties"])
                self.assertIn("schema_version", schema["required"])


if __name__ == "__main__":
    unittest.main()
