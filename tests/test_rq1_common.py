from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path
import shutil

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq1.common import (
    aggregate_instances_to_repo,
    compute_project_age_years,
    filter_dataframe_by_languages,
    merge_repo_metadata,
    write_missing_data_note,
)
from rq1.fig1_prevalence_by_language import (
    compute_prevalence_axis_limits,
    compute_prevalence_rate_ticks,
)


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

    def test_compute_project_age_years_fills_missing_scan_with_snapshot(self):
        df = pd.DataFrame(
            [
                {"createdAt": "2024-01-01T00:00:00Z", "scanned_at_utc": "2026-07-01T00:00:00Z"},
                {"createdAt": "2024-01-01T00:00:00Z", "scanned_at_utc": None},
            ]
        )
        ages = compute_project_age_years(df)
        self.assertAlmostEqual(float(ages.iloc[0]), float(ages.iloc[1]), places=4)

    def test_filter_dataframe_by_languages_is_case_insensitive(self):
        df = pd.DataFrame(
            [
                {"repo": "a/py", "mainLanguage": "Python"},
                {"repo": "a/ts", "mainLanguage": "typescript"},
                {"repo": "a/go", "mainLanguage": "Go"},
                {"repo": "a/missing", "mainLanguage": ""},
            ]
        )
        filtered = filter_dataframe_by_languages(df, ["python", "TypeScript"])
        self.assertEqual(filtered["repo"].tolist(), ["a/py", "a/ts"])

    def test_prevalence_axis_limits_scale_with_data(self):
        count_axis_max, count_xlim_max, rate_axis_max, rate_xlim_max = compute_prevalence_axis_limits(
            pd.Series([4227, 4396]),
            pd.Series([6.2, 10.4]),
        )
        self.assertGreaterEqual(count_axis_max, 4396)
        self.assertGreater(count_xlim_max, count_axis_max)
        self.assertGreaterEqual(rate_axis_max, 10.4)
        self.assertGreater(rate_xlim_max, rate_axis_max)

    def test_prevalence_axis_max_is_multiple_of_two_percent(self):
        _, _, rate_axis_max, _ = compute_prevalence_axis_limits(
            pd.Series([100]),
            pd.Series([8.1]),
        )
        self.assertEqual(rate_axis_max, 10.0)

    def test_prevalence_rate_ticks_are_every_two_percent(self):
        ticks = compute_prevalence_rate_ticks(12.0)
        self.assertEqual(list(ticks), [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0])

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
