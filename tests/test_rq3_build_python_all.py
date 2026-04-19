from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq3.build_python_all_dataset import merge_processed_exports


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
