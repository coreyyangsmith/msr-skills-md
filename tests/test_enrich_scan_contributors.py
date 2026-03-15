from __future__ import annotations

import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock
import shutil

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from enrich_scan_contributors import fetch_contributor_count, main, parse_last_page, prepare_working_dataframe


class TestEnrichScanContributors(unittest.TestCase):
    def _tempdir(self):
        path = Path.cwd() / "outputs" / f"_test_enrich_{uuid.uuid4().hex}"
        path.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(path, ignore_errors=True))
        return path

    def test_parse_last_page(self):
        link = '<https://api.github.com/repositories/1/contributors?per_page=1&page=2>; rel="next", <https://api.github.com/repositories/1/contributors?per_page=1&page=7>; rel="last"'
        self.assertEqual(parse_last_page(link), 7)

    def test_fetch_contributor_count_204_returns_zero(self):
        gh = mock.MagicMock()
        gh.request_json_with_headers.return_value = (204, {}, {}, "")
        count, err = fetch_contributor_count(gh, "owner/repo")
        self.assertEqual(count, 0)
        self.assertEqual(err, "")

    def test_fetch_contributor_count_uses_last_page(self):
        gh = mock.MagicMock()
        gh.request_json_with_headers.return_value = (
            200,
            [{"login": "alice"}],
            {"Link": '<https://api.github.com/repositories/1/contributors?per_page=1&page=9>; rel="last"'},
            "",
        )
        count, err = fetch_contributor_count(gh, "owner/repo")
        self.assertEqual(count, 9)
        self.assertEqual(err, "")

    def test_prepare_working_dataframe_merges_resume_values(self):
        tmpdir = self._tempdir()
        scan_csv = Path(tmpdir) / "scan.csv"
        out_csv = Path(tmpdir) / "out.csv"
        pd.DataFrame(
            [
                {"repo": "a/b", "contributors": ""},
                {"repo": "c/d", "contributors": ""},
            ]
        ).to_csv(scan_csv, index=False)
        pd.DataFrame(
            [
                {"repo": "a/b", "contributors": 5},
                {"repo": "c/d", "contributors": ""},
            ]
        ).to_csv(out_csv, index=False)

        df = prepare_working_dataframe(str(scan_csv), str(out_csv), resume=True)
        self.assertEqual(int(df.loc[df["repo"] == "a/b", "contributors"].iloc[0]), 5)
        self.assertTrue(pd.isna(df.loc[df["repo"] == "c/d", "contributors"].iloc[0]))

    def test_main_respects_resume_and_writes_output(self):
        tmpdir = self._tempdir()
        scan_csv = Path(tmpdir) / "scan.csv"
        out_csv = Path(tmpdir) / "out.csv"
        pd.DataFrame(
            [
                {"repo": "a/b", "contributors": ""},
                {"repo": "c/d", "contributors": ""},
            ]
        ).to_csv(scan_csv, index=False)
        pd.DataFrame([{"repo": "a/b", "contributors": 4}]).to_csv(out_csv, index=False)

        with mock.patch("enrich_scan_contributors.fetch_contributor_count", return_value=(7, "")):
            rc = main(
                [
                    "--scan-csv",
                    str(scan_csv),
                    "--out-csv",
                    str(out_csv),
                    "--resume",
                    "--concurrency",
                    "1",
                ]
            )

        self.assertEqual(rc, 0)
        out_df = pd.read_csv(out_csv)
        self.assertEqual(int(out_df.loc[out_df["repo"] == "a/b", "contributors"].iloc[0]), 4)
        self.assertEqual(int(out_df.loc[out_df["repo"] == "c/d", "contributors"].iloc[0]), 7)

    def test_main_leaves_blank_when_fetch_fails(self):
        tmpdir = self._tempdir()
        scan_csv = Path(tmpdir) / "scan.csv"
        out_csv = Path(tmpdir) / "out.csv"
        pd.DataFrame([{"repo": "a/b", "contributors": ""}]).to_csv(scan_csv, index=False)

        with mock.patch("enrich_scan_contributors.fetch_contributor_count", return_value=(None, "boom")):
            rc = main(["--scan-csv", str(scan_csv), "--out-csv", str(out_csv), "--concurrency", "1"])

        self.assertEqual(rc, 0)
        out_df = pd.read_csv(out_csv)
        self.assertTrue(pd.isna(out_df.loc[0, "contributors"]))


if __name__ == "__main__":
    unittest.main()
