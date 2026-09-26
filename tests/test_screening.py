from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generate_screening_outputs import build_audit_rows, label_relevance
from screening import (
    artifact_id_to_repo_and_skill_path,
    filter_dataframe_by_screening,
    load_screening_decisions,
)


class TestScreeningDecisions(unittest.TestCase):
    def test_final_mode_rejects_unresolved_review_rows(self):
        tmp = Path.cwd() / "outputs" / f"_test_screening_{uuid.uuid4().hex}.csv"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text("repo,decision\nowner/repo,review\n", encoding="utf-8")
        self.addCleanup(lambda: tmp.unlink(missing_ok=True))
        with self.assertRaisesRegex(ValueError, "unresolved review"):
            load_screening_decisions(tmp, final=True)

    def test_filter_dataframe_by_screening_keeps_only_keep_decisions(self):
        df = pd.DataFrame([{"repo": "a/keep"}, {"repo": "b/review"}, {"repo": "c/missing"}])
        decisions = pd.DataFrame(
            [
                {"repo": "a/keep", "decision": "keep"},
                {"repo": "b/review", "decision": "review"},
            ]
        )
        filtered = filter_dataframe_by_screening(df, decisions)
        self.assertEqual(filtered["repo"].tolist(), ["a/keep", "c/missing"])


class TestScreeningAudit(unittest.TestCase):
    def test_artifact_id_to_repo_and_skill_path(self):
        repo, skill_path = artifact_id_to_repo_and_skill_path("octo__repo/src/skills/build")
        self.assertEqual(repo, "octo/repo")
        self.assertEqual(skill_path, "src/skills/build/SKILL.md")

    def test_label_relevance_maps_sdlc_to_in_scope(self):
        relevance, reason, taxonomy = label_relevance({"code-generation", "commands"})
        self.assertEqual(relevance, "in-scope SE repo")
        self.assertIn("Code Implementation", reason)
        self.assertEqual(taxonomy, "true positive SE repo")

    def test_label_relevance_distinguishes_filter_sources_before_collapse(self):
        relevance, reason, taxonomy = label_relevance({"agent-skill", "descriptive"})
        self.assertEqual(relevance, "out-of-scope marketplace or config repo")
        self.assertEqual(reason, "manual agent-skill label")
        self.assertEqual(taxonomy, "skill marketplace / skill hub")

    def test_build_audit_rows_counts_v1_keyword(self):
        rows = build_audit_rows(
            {
                "owner__template-api/skills/build": {
                    "artifact_id": "owner__template-api/skills/build",
                    "manual_labels": {"code-generation"},
                    "source_files": {"labels.json"},
                }
            },
            v1_decisions=pd.DataFrame(
                [{"repo": "owner/template-api", "decision": "exclude"}]
            ),
            name_filter_matches={},
            v1_rules_terms=["template"],
        )
        self.assertEqual(rows[0]["repo"], "owner/template-api")
        self.assertEqual(rows[0]["filter_outcome_initial"], "exclude")
        self.assertEqual(rows[0]["human_relevance"], "in-scope SE repo")
        self.assertEqual(rows[0]["matched_v1_keyword"], "template")


if __name__ == "__main__":
    unittest.main()
