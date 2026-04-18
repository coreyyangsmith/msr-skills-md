from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq3.label_processing import iter_label_exports, normalise_label
from rq3.preprocess_labels import build_summary


class TestRq3PreprocessLabels(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path.cwd() / "outputs" / f"_test_rq3_preprocess_{uuid.uuid4().hex}"
        self.tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def _write_json(self, name: str, data: dict) -> Path:
        path = self.tmpdir / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_normalise_label_collapses_known_variants(self):
        self.assertEqual(normalise_label("Instructive"), "instructive")
        self.assertEqual(normalise_label("software design"), "software-design")
        self.assertEqual(normalise_label("SE workflow management"), "se-workflow-management")
        self.assertEqual(normalise_label("non-english"), "wrong-language")

    def test_iter_label_exports_skips_non_exports_and_derived_outputs(self):
        self._write_json("comparison_output.json", {"anything": True})
        self._write_json("kappa_sample.json", {"tags": [], "labels": {}})
        valid = self._write_json(
            "labels.json",
            {
                "tags": [{"id": "1", "name": "instructive"}],
                "labels": {"doc": {"tagIds": ["1"]}},
            },
        )

        paths = iter_label_exports(self.tmpdir)

        self.assertEqual(paths, [valid])

    def test_build_summary_reports_raw_and_normalized_supersets(self):
        path1 = self._write_json(
            "a.json",
            {
                "tags": [
                    {"id": "1", "name": "Instructive"},
                    {"id": "2", "name": "software design"},
                ],
                "labels": {"doc-a": {"tagIds": ["1", "2"]}},
            },
        )
        path2 = self._write_json(
            "b.json",
            {
                "tags": [
                    {"id": "3", "name": "instructive"},
                    {"id": "4", "name": "software-design"},
                    {"id": "5", "name": "agent-facing"},
                ],
                "labels": {"doc-b": {"tagIds": ["3", "4", "5"]}},
            },
        )

        summary = build_summary([path1, path2])

        self.assertEqual(summary["raw_label_superset_count"], 5)
        self.assertEqual(summary["normalized_label_superset_count"], 3)
        self.assertEqual(
            summary["normalized_label_superset"],
            ["agent-facing", "instructive", "software-design"],
        )
        self.assertEqual(
            summary["normalized_alias_groups"]["instructive"],
            ["Instructive", "instructive"],
        )
        self.assertEqual(
            summary["normalized_alias_groups"]["software-design"],
            ["software design", "software-design"],
        )


if __name__ == "__main__":
    unittest.main()
