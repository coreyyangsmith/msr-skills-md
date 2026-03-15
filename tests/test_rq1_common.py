from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path
import shutil

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq1.common import aggregate_instances_to_repo, compute_project_age_years, merge_repo_metadata, write_missing_data_note


class TestRq1Common(unittest.TestCase):
    def test_aggregate_instances_to_repo_sums_metrics(self):
        inst_df = pd.DataFrame(
            [
                {"repo": "a/b", "references_file_count": 1, "assets_file_count": 2, "mainLanguage": "Python"},
                {"repo": "a/b", "references_file_count": 3, "assets_file_count": 4, "mainLanguage": "Python"},
            ]
        )
        repo_df = aggregate_instances_to_repo(inst_df)
        self.assertEqual(int(repo_df.loc[0, "skill_count"]), 2)
        self.assertEqual(int(repo_df.loc[0, "references_file_count"]), 4)
        self.assertEqual(int(repo_df.loc[0, "assets_file_count"]), 6)

    def test_merge_repo_metadata_fills_missing_values(self):
        repo_df = pd.DataFrame([{"repo": "a/b", "contributors": pd.NA, "has_README": pd.NA}])
        scan_df = pd.DataFrame(
            [
                {
                    "repo": "a/b",
                    "contributors": 12,
                    "createdAt": "2024-01-01T00:00:00Z",
                    "has_README": 1,
                }
            ]
        )
        merged = merge_repo_metadata(repo_df, scan_df)
        self.assertEqual(int(merged.loc[0, "contributors"]), 12)
        self.assertEqual(merged.loc[0, "createdAt"], "2024-01-01T00:00:00Z")
        self.assertEqual(int(merged.loc[0, "has_README"]), 1)

    def test_compute_project_age_years_uses_scanned_at(self):
        df = pd.DataFrame(
            [
                {
                    "createdAt": "2024-03-13T00:00:00Z",
                    "scanned_at_utc": "2026-03-13T00:00:00Z",
                }
            ]
        )
        ages = compute_project_age_years(df)
        self.assertAlmostEqual(float(ages.iloc[0]), 2.0, places=2)

    def test_write_missing_data_note(self):
        tmpdir = Path.cwd() / "outputs" / f"_test_rq1_common_{uuid.uuid4().hex}"
        tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(tmpdir, ignore_errors=True))
        note_path = write_missing_data_note(str(tmpdir), "artifact", "Missing columns", ["contributors"])
        text = Path(note_path).read_text(encoding="utf-8")
        self.assertIn("contributors", text)
        self.assertIn("artifact", text)


if __name__ == "__main__":
    unittest.main()
