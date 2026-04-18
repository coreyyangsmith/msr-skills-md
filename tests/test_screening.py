from __future__ import annotations

import sys
import unittest
import uuid
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generate_screening_outputs import build_audit_rows, label_relevance
from rq2.collect_skill_documents import filter_documents_by_screening
from screening import (
    DECISION_EXCLUDE,
    DECISION_KEEP,
    DECISION_REVIEW,
    DEFAULT_V1_RULES_PATH,
    DEFAULT_V2_RULES_PATH,
    artifact_id_to_repo_and_skill_path,
    decide_repo,
    filter_dataframe_by_screening,
    load_filter_rules,
    load_screening_decisions,
)


class TestScreeningDecisions(unittest.TestCase):
    def setUp(self):
        self.v1 = load_filter_rules(DEFAULT_V1_RULES_PATH)
        self.v2 = load_filter_rules(DEFAULT_V2_RULES_PATH)

    def test_blacklist_always_excludes(self):
        decision = decide_repo("owner/repo", {}, self.v2, {"owner/repo"})
        self.assertEqual(decision.decision, DECISION_EXCLUDE)
        self.assertEqual(decision.primary_reason, "blacklist")

    def test_v1_reproduces_hard_name_filter(self):
        decision = decide_repo("owner/python-skill-template", {}, self.v1, set())
        self.assertEqual(decision.decision, DECISION_EXCLUDE)
        self.assertEqual(decision.primary_reason, "name_filter:skill")

    def test_v2_hard_exclusion_for_dotfiles(self):
        decision = decide_repo("owner/dotfiles", {"has_package_json": 1}, self.v2, set())
        self.assertEqual(decision.decision, DECISION_EXCLUDE)
        self.assertEqual(decision.primary_reason, "name_filter:dotfiles")

    def test_v2_noisy_name_becomes_review_without_signals(self):
        decision = decide_repo("owner/template-pack", {}, self.v2, set())
        self.assertEqual(decision.decision, DECISION_REVIEW)
        self.assertEqual(decision.primary_reason, "name_review:template")

    def test_v2_noisy_name_kept_with_strong_software_signals(self):
        decision = decide_repo(
            "owner/template-api",
            {"has_package_json": 1, "skill_to_source_file_ratio": 0.01},
            self.v2,
            set(),
        )
        self.assertEqual(decision.decision, DECISION_KEEP)
        self.assertEqual(decision.primary_reason, "keep_override:strong_software_signals")
        self.assertIn("has_package_json", decision.supporting_signals)

    def test_path_pattern_can_override_software_signals(self):
        decision = decide_repo(
            "owner/normal-app",
            {
                "has_src_dir": 1,
                "skill_paths": "skill-repository/standard/web-scraping/SKILL.md",
            },
            self.v2,
            set(),
        )
        self.assertEqual(decision.decision, DECISION_EXCLUDE)
        self.assertEqual(decision.primary_reason, "path_filter:skill-repository/")

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

    def test_rq2_document_filter_uses_repo_decisions(self):
        tmp = Path.cwd() / "outputs" / f"_test_rq2_screening_{uuid.uuid4().hex}.csv"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text("repo,decision\nowner/keep,keep\nowner/drop,exclude\n", encoding="utf-8")
        self.addCleanup(lambda: tmp.unlink(missing_ok=True))

        docs = [
            {"repo": "owner__keep", "repo_full_name": "owner/keep"},
            {"repo": "owner__drop", "repo_full_name": "owner/drop"},
            {"repo": "owner__missing", "repo_full_name": "owner/missing"},
        ]
        filtered = filter_documents_by_screening(docs, str(tmp), "provisional")
        self.assertEqual([doc["repo_full_name"] for doc in filtered], ["owner/keep", "owner/missing"])


class TestScreeningAudit(unittest.TestCase):
    def test_artifact_id_to_repo_and_skill_path(self):
        repo, skill_path = artifact_id_to_repo_and_skill_path("octo__repo/src/skills/build")
        self.assertEqual(repo, "octo/repo")
        self.assertEqual(skill_path, "src/skills/build/SKILL.md")

    def test_label_relevance_maps_sdlc_to_in_scope(self):
        relevance, reason, taxonomy = label_relevance({"code-generation", "commands"})
        self.assertEqual(relevance, "in-scope SE repo")
        self.assertIn("Code Generation", reason)
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
