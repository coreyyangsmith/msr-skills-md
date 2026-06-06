from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq3.build_python_all_dataset import main
from rq3.build_python_all_dataset import merge_processed_exports
from rq3.build_python_all_dataset import language_defaults
from rq3.label_processing import load_json, write_json


class TestRq3BuildPythonAll(unittest.TestCase):
    def test_merge_processed_exports_combines_disjoint_documents(self):
        export_a = {
            "dataset": {"rootName": "A", "savedAt": "2026-04-06T00:00:00Z", "totalFiles": 2},
            "processing": {
                "filter_source_document_counts": {"agent-skill": 1, "outside-scope": 0, "wrong-language": 0},
                "counts": {"documents": 2, "documents_collapsed_to_filter": 1},
            },
            "tags": [
                {"id": "1", "name": "filter"},
                {"id": "2", "name": "instructive"},
            ],
            "labels": {
                "doc-a": {"tagIds": ["1"]},
                "doc-b": {"tagIds": ["2"]},
            },
        }
        export_b = {
            "dataset": {"rootName": "B", "savedAt": "2026-04-07T00:00:00Z", "totalFiles": 1},
            "processing": {
                "filter_source_document_counts": {"agent-skill": 0, "outside-scope": 1, "wrong-language": 0},
                "counts": {"documents": 1, "documents_collapsed_to_filter": 1},
            },
            "tags": [
                {"id": "3", "name": "Code Generation"},
            ],
            "labels": {
                "doc-c": {"tagIds": ["3"]},
            },
        }

        merged = merge_processed_exports(
            [("A.json", export_a), ("B.json", export_b)],
            selected_both_file="B.json",
        )

        self.assertEqual(merged["dataset"]["rootName"], "Python_All")
        self.assertEqual(merged["dataset"]["selectedBothFile"], "B.json")
        self.assertEqual(len(merged["labels"]), 3)
        self.assertEqual(
            merged["processing"]["filter_source_document_counts"],
            {"agent-skill": 1, "outside-scope": 1, "wrong-language": 0},
        )
        self.assertEqual(merged["processing"]["counts"]["documents"], 3)

    def test_merge_processed_exports_accepts_typescript_root_name(self):
        export = {
            "dataset": {"rootName": "Both", "savedAt": "2026-04-06T00:00:00Z", "totalFiles": 1},
            "processing": {"filter_source_document_counts": {}, "counts": {"documents": 1}},
            "tags": [{"id": "1", "name": "Code Generation"}],
            "labels": {"owner__repo/SKILL.md": {"tagIds": ["1"]}},
        }

        merged = merge_processed_exports(
            [("2026-03-29_CY_Labels_Both_TS.json", export)],
            root_name="TypeScript_All",
            selected_both_file="2026-03-29_CY_Labels_Both_TS.json",
        )

        self.assertEqual(merged["dataset"]["rootName"], "TypeScript_All")
        self.assertEqual(merged["dataset"]["sourceFiles"], ["2026-03-29_CY_Labels_Both_TS.json"])
        self.assertEqual(len(merged["labels"]), 1)

    def test_language_defaults_include_python_and_typescript(self):
        python_defaults = language_defaults("Python")
        typescript_defaults = language_defaults("TypeScript")

        self.assertEqual(python_defaults.root_name, "Python_All")
        self.assertEqual(typescript_defaults.root_name, "TypeScript_All")
        self.assertEqual(typescript_defaults.output_name, "TypeScript_All.json")
        self.assertIn("2026-03-29_CY_Labels_Both_TS.json", typescript_defaults.source_files)

    def test_main_builds_typescript_all_from_default_source(self):
        export = {
            "dataset": {"rootName": "Both", "savedAt": "2026-04-06T00:00:00Z", "totalFiles": 1},
            "processing": {"filter_source_document_counts": {}, "counts": {"documents": 1}},
            "tags": [{"id": "1", "name": "Code Generation"}],
            "labels": {"owner__repo/SKILL.md": {"tagIds": ["1"]}},
        }

        with tempfile.TemporaryDirectory() as tmp:
            processed_dir = Path(tmp)
            write_json(processed_dir / "2026-03-29_CY_Labels_Both_TS.json", export)

            main(["--processed-dir", str(processed_dir), "--language", "TypeScript"])

            output = load_json(processed_dir / "TypeScript_All.json")

        self.assertEqual(output["dataset"]["rootName"], "TypeScript_All")
        self.assertEqual(output["dataset"]["selectedBothFile"], "2026-03-29_CY_Labels_Both_TS.json")

    def test_merge_processed_exports_rejects_overlap(self):
        export = {
            "dataset": {"rootName": "A", "savedAt": "2026-04-06T00:00:00Z", "totalFiles": 1},
            "processing": {"filter_source_document_counts": {}, "counts": {}},
            "tags": [{"id": "1", "name": "filter"}],
            "labels": {"shared-doc": {"tagIds": ["1"]}},
        }

        with self.assertRaises(ValueError):
            merge_processed_exports([("A.json", export), ("B.json", export)])


if __name__ == "__main__":
    unittest.main()
