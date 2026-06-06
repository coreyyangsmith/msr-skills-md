from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq2.analyze_tfidf_sklearn import filter_documents_by_language
from rq3.generate_processed_analysis_plots import (
    filter_language_datasets,
    select_language_both_pairs,
)


class TestLanguageAnalysisFilters(unittest.TestCase):
    def test_select_language_both_pairs_accepts_typescript_ts_alias(self):
        pair_df = pd.DataFrame(
            [
                {
                    "pair_file": "kappa_ts.json",
                    "file1": "2026-03-29_CY_Labels_Both_TS.json",
                    "file2": "2026-04-01_MV_Labels_Both_TS.json",
                },
                {
                    "pair_file": "kappa_py.json",
                    "file1": "2026-03-28_CY_Labels_Both_Python.json",
                    "file2": "2026-03-31_MV_Labels_Both_Python.json",
                },
            ]
        )

        selected = select_language_both_pairs(pair_df, "TypeScript")

        self.assertEqual(selected["pair_file"].tolist(), ["kappa_ts.json"])

    def test_filter_language_datasets_keeps_typescript_aliases(self):
        dataset_df = pd.DataFrame(
            [
                {"file": "2026-03-29_CY_Labels_Both_TS.json"},
                {"file": "TypeScript_All.json"},
                {"file": "Python_All.json"},
            ]
        )

        selected = filter_language_datasets(dataset_df, "TypeScript")

        self.assertEqual(selected["file"].tolist(), ["2026-03-29_CY_Labels_Both_TS.json", "TypeScript_All.json"])

    def test_filter_documents_by_language_is_case_insensitive(self):
        docs = [
            {"language": "Python", "text": "one"},
            {"language": "TypeScript", "text": "two"},
            {"language": "Rust", "text": "three"},
        ]

        selected = filter_documents_by_language(docs, {"typescript"})

        self.assertEqual(selected, [{"language": "TypeScript", "text": "two"}])


if __name__ == "__main__":
    unittest.main()
