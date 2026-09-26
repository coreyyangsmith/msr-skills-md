from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq1.table_repo_group_descriptives import (
    GROUP_NONSKILL,
    GROUP_SKILL,
    build_descriptive_tables,
    build_group_tests,
    cliffs_delta_mwu,
    format_latex_table,
)


class TestTableRepoGroupDescriptives(unittest.TestCase):
    def test_group_ns_and_star_median(self) -> None:
        scan_df = pd.DataFrame(
            [
                {
                    "repo": "a/one",
                    "found": True,
                    "stargazers": 10,
                    "contributors": 1,
                    "size": 1024,
                    "createdAt": "2024-03-13T00:00:00Z",
                    "scanned_at_utc": "2026-03-13T00:00:00Z",
                },
                {
                    "repo": "a/two",
                    "found": True,
                    "stargazers": 30,
                    "contributors": 3,
                    "size": 3072,
                    "createdAt": "2024-03-13T00:00:00Z",
                    "scanned_at_utc": "2026-03-13T00:00:00Z",
                },
                {
                    "repo": "b/three",
                    "found": False,
                    "stargazers": 4,
                    "contributors": 2,
                    "size": 512,
                    "createdAt": "2025-03-13T00:00:00Z",
                    "scanned_at_utc": "2026-03-13T00:00:00Z",
                },
                {
                    "repo": "b/four",
                    "found": False,
                    "stargazers": 8,
                    "contributors": 6,
                    "size": 1536,
                    "createdAt": "2025-03-13T00:00:00Z",
                    "scanned_at_utc": "2026-03-13T00:00:00Z",
                },
            ]
        )
        instances_df = pd.DataFrame(
            [
                {"repo": "a/one", "skill_path": "skills/x/SKILL.md"},
                {"repo": "a/one", "skill_path": "skills/y/SKILL.md"},
                {"repo": "a/two", "skill_path": "SKILL.md"},
            ]
        )
        tidy, skill_wide, nonskill_wide = build_descriptive_tables(scan_df, instances_df)

        skill_stars = tidy[(tidy["group"] == GROUP_SKILL) & (tidy["metric"] == "Stars")].iloc[0]
        nonskill_stars = tidy[(tidy["group"] == GROUP_NONSKILL) & (tidy["metric"] == "Stars")].iloc[0]
        self.assertEqual(int(skill_stars["n"]), 2)
        self.assertEqual(int(nonskill_stars["n"]), 2)
        self.assertEqual(skill_stars["median"], 20.0)
        self.assertEqual(nonskill_stars["min"], 4)
        self.assertEqual(nonskill_stars["max"], 8)

        skill_files = tidy[(tidy["group"] == GROUP_SKILL) & (tidy["metric"] == "SKILL.md files")].iloc[0]
        nonskill_files = tidy[(tidy["group"] == GROUP_NONSKILL) & (tidy["metric"] == "SKILL.md files")].iloc[0]
        self.assertEqual(int(skill_files["n"]), 2)
        self.assertEqual(skill_files["min"], 1)
        self.assertEqual(skill_files["max"], 2)
        self.assertEqual(nonskill_files["min"], 0)
        self.assertEqual(nonskill_files["max"], 0)

        self.assertEqual(int(skill_wide.loc[skill_wide["metric"] == "Stars", "n"].iloc[0]), 2)
        self.assertEqual(int(nonskill_wide.loc[nonskill_wide["metric"] == "Stars", "n"].iloc[0]), 2)

        tex = format_latex_table(tidy, n_skill=2, n_nonskill=2)
        self.assertIn("SKILL.md repos", tex)
        self.assertIn("No SKILL.md", tex)
        self.assertIn("Stars", tex)

    def test_cliffs_delta_bounds_and_sign(self) -> None:
        high, low = pd.Series([5, 6, 7]), pd.Series([1, 2, 3, 4])
        self.assertEqual(cliffs_delta_mwu(high, low)["cliffs_delta"], 1.0)
        self.assertEqual(cliffs_delta_mwu(low, high)["cliffs_delta"], -1.0)
        self.assertEqual(cliffs_delta_mwu(low, low)["cliffs_delta"], 0.0)

    def test_group_tests_skip_skill_count_and_pin_age_reference(self) -> None:
        scan_df = pd.DataFrame(
            {
                "repo": ["a/1", "a/2", "b/1", "b/2"],
                "found": [True, True, False, False],
                "stargazers": [30, 40, 10, 20],
                "contributors": [1, 2, 1, 2],
                "size": [1024, 2048, 1024, 2048],
                "createdAt": ["2026-01-01T00:00:00Z"] * 4,
                "scanned_at_utc": ["2026-07-01T00:00:00Z", "2026-07-01T00:00:00Z", None, None],
            }
        )
        tests = build_group_tests(scan_df).set_index("metric")
        self.assertNotIn("SKILL.md files", tests.index)
        self.assertEqual(tests.loc["Stars", "cliffs_delta"], 1.0)
        self.assertEqual(tests.loc["Project age (years)", "cliffs_delta"], 0.0)


if __name__ == "__main__":
    unittest.main()
