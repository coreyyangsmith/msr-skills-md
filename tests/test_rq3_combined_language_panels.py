from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq3.fig1_prevalence_panels import combine_language_tables, overall_prevalence_table


class TestRq3CombinedLanguagePanels(unittest.TestCase):
    def test_overall_prevalence_is_document_weighted(self):
        python = pd.DataFrame(
            {
                "label": ["Testing", "Requirements"],
                "count": [60, 20],
                "pct_docs": [30.0, 10.0],
                "retained_documents": [200, 200],
            }
        )
        typescript = pd.DataFrame(
            {
                "label": ["Testing", "Requirements"],
                "count": [80, 40],
                "pct_docs": [40.0, 20.0],
                "retained_documents": [200, 200],
            }
        )

        combined = combine_language_tables(python, typescript)

        testing = combined[combined["label"] == "Testing"].set_index("dataset")
        self.assertEqual(testing.loc["Overall", "count"], 140)
        self.assertEqual(testing.loc["Overall", "retained_documents"], 400)
        self.assertEqual(testing.loc["Overall", "pct_docs"], 35.0)
        self.assertEqual(testing.loc["Python", "pct_docs"], 30.0)
        self.assertEqual(testing.loc["TypeScript", "pct_docs"], 40.0)

        overall = overall_prevalence_table(python, typescript)
        self.assertEqual(list(overall["dataset"]), ["Overall", "Overall"])
        self.assertEqual(overall.iloc[0]["label"], "Testing")
        self.assertEqual(overall.iloc[0]["pct_docs"], 35.0)
        self.assertEqual(overall.iloc[0]["retained_documents"], 400)


if __name__ == "__main__":
    unittest.main()
