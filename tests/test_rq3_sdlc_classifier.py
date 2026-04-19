from __future__ import annotations

import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rq3.train_sdlc_classifier import (
    artifact_id_for,
    build_artifact_features,
    clean_target_for_raw_labels,
    collect_artifact_table,
    decision_band,
    label_targets_from_export,
    main,
    parse_skill_markdown,
    select_threshold_for_precision,
)


class TestRq3SdlcClassifier(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path.cwd() / "outputs" / f"_test_rq3_classifier_{uuid.uuid4().hex}"
        self.tmpdir.mkdir(parents=True, exist_ok=True)
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_artifact_id_mapping_for_nested_and_root_skills(self):
        self.assertEqual(artifact_id_for("owner__repo", "skills/test-writer"), "owner__repo/skills/test-writer")
        self.assertEqual(artifact_id_for("owner__repo", ""), "owner__repo/root")

    def test_frontmatter_parser_handles_quoted_and_multiline_yaml(self):
        parsed = parse_skill_markdown(
            """---
name: "test-writer"
description: >-
  Generate comprehensive pytest suites
  for existing Python code.
---

# Test Writer

Run `pytest`.

```bash
pytest tests
```
"""
        )

        self.assertEqual(parsed["name"], "test-writer")
        self.assertIn("comprehensive pytest suites", parsed["description"])
        self.assertIn("Test Writer", parsed["headings"])
        self.assertIn("Test Writer", parsed["headings_text"])
        self.assertIn("pytest", parsed["body_chunk"])
        self.assertIn("bash", parsed["code_languages"])
        self.assertIn("pytest tests", parsed["commands"])
        self.assertEqual(parsed["code_fence_count"], 1)
        self.assertEqual(parsed["shell_fence_count"], 1)

    def test_frontmatter_parser_falls_back_on_malformed_yaml(self):
        parsed = parse_skill_markdown(
            """---
name: tmux
description: Use this for tmux sessions; IMPORTANT: only trigger carefully
---

# Tmux Skill
"""
        )

        self.assertEqual(parsed["name"], "tmux")
        self.assertIn("tmux sessions", parsed["description"])

    def test_clean_target_derivation_from_raw_labels(self):
        self.assertEqual(clean_target_for_raw_labels({"agent-skill"})["training_target"], "agent_meta")
        self.assertEqual(clean_target_for_raw_labels({"outside-scope"})["training_action"], "ignore")
        self.assertEqual(clean_target_for_raw_labels({"wrong-language"})["training_action"], "ignore")
        self.assertEqual(clean_target_for_raw_labels({"code-generation"})["training_target"], "sdlc")
        self.assertEqual(
            clean_target_for_raw_labels({"agent-skill", "outside-scope"})["ignore_reason"],
            "outside-scope",
        )

    def test_label_targets_from_raw_export(self):
        labels = label_targets_from_export(
            {
                "tags": [
                    {"id": "1", "name": "agent-skill"},
                    {"id": "2", "name": "code-generation"},
                    {"id": "3", "name": "outside-scope"},
                    {"id": "4", "name": "non-english"},
                ],
                "labels": {
                    "repo/root": {"tagIds": ["1"]},
                    "repo/skills/test": {"tagIds": ["2"]},
                    "repo/skills/outside": {"tagIds": ["3"]},
                    "repo/skills/wrong-lang": {"tagIds": ["4"]},
                },
            }
        )

        self.assertEqual(labels["repo/root"]["manual_target"], "agent_meta")
        self.assertEqual(labels["repo/root"]["training_action"], "include")
        self.assertEqual(labels["repo/skills/test"]["manual_target"], "sdlc")
        self.assertEqual(labels["repo/skills/test"]["sdlc_stage_labels"], "Code Generation")
        self.assertEqual(labels["repo/skills/outside"]["training_action"], "ignore")
        self.assertEqual(labels["repo/skills/wrong-lang"]["ignore_reason"], "wrong-language")

    def test_feature_extraction_includes_metadata_and_sibling_context(self):
        repo_dir = self.tmpdir / "raw_data" / "Python" / "owner__repo"
        skill_dir = repo_dir / "skills" / "test-writer"
        (skill_dir / "scripts").mkdir(parents=True)
        (skill_dir / "references").mkdir()
        (skill_dir / "assets").mkdir()
        (skill_dir / "SKILL.md").write_text(
            """---
name: test-writer
description: Generate tests for Python code.
---

# Test Writer

Use pytest.

- Run `pytest tests`.
- Inspect ./scripts/run.py.

```bash
pytest tests
```
""",
            encoding="utf-8",
        )
        (skill_dir / "scripts" / "run.py").write_text("print('ok')", encoding="utf-8")
        (skill_dir / "references" / "testing.md").write_text("notes", encoding="utf-8")
        (skill_dir / "assets" / "fixture.json").write_text("{}", encoding="utf-8")
        (skill_dir / "pytest.ini").write_text("[pytest]", encoding="utf-8")

        record = build_artifact_features(
            repo_dir=repo_dir,
            repo_folder="owner__repo",
            metadata={"repo": "owner/repo", "stars": 42, "has_AGENTS": 1},
            skill_meta={
                "skill_path": "skills/test-writer/SKILL.md",
                "parent_folder": "skills/test-writer",
                "total_files": 4,
                "references_count": 1,
                "assets_count": 1,
                "scripts_count": 1,
                "other_count": 0,
            },
        )

        self.assertEqual(record.artifact_id, "owner__repo/skills/test-writer")
        self.assertIn("Generate tests", record.text_features)
        self.assertEqual(record.frontmatter_name, "test-writer")
        self.assertIn("Generate tests", record.frontmatter_description)
        self.assertIn("Test Writer", record.headings_text)
        self.assertIn("pytest", record.body_chunk)
        self.assertIn("skills/test-writer", record.path_tokens)
        self.assertIn("scripts/run.py", record.path_context)
        self.assertIn("scripts/run.py", record.sibling_filenames)
        self.assertEqual(record.stars, 42)
        self.assertEqual(record.has_AGENTS, 1)
        self.assertEqual(record.sibling_file_count, 4)
        self.assertEqual(record.sibling_scripts_count, 1)
        self.assertGreaterEqual(record.sibling_references_count, 1)
        self.assertGreaterEqual(record.sibling_assets_count, 1)
        self.assertEqual(record.skill_directory_depth, 2)
        self.assertEqual(record.nearby_test_manifest, 1)
        self.assertEqual(record.bullet_count, 2)
        self.assertEqual(record.shell_fence_count, 1)
        self.assertGreaterEqual(record.local_reference_count, 1)
        self.assertIn("scripts/run.py", record.referenced_files)

    def test_threshold_banding(self):
        self.assertEqual(decision_band(0.80, 0.20), "auto_accept_sdlc")
        self.assertEqual(decision_band(0.20, 0.80), "auto_filter_agent_meta")
        self.assertEqual(decision_band(0.50, 0.50), "manual_review")

    def test_calibrated_threshold_selection_uses_validation_probabilities(self):
        selected = select_threshold_for_precision(
            ["sdlc", "sdlc", "agent_meta", "agent_meta"],
            [0.95, 0.60, 0.55, 0.10],
            positive_label="sdlc",
            target_precision=0.90,
        )

        self.assertTrue(selected["met_target_precision"])
        self.assertGreaterEqual(selected["precision"], 0.90)
        self.assertEqual(selected["threshold"], 0.60)

    def test_calibrated_threshold_fallback_is_deterministic(self):
        selected = select_threshold_for_precision(
            ["sdlc", "agent_meta", "agent_meta"],
            [0.90, 0.80, 0.70],
            positive_label="sdlc",
            target_precision=1.01,
        )

        self.assertFalse(selected["met_target_precision"])
        self.assertEqual(selected["threshold"], 0.90)

    def test_smoke_training_writes_model_evaluation_and_predictions(self):
        raw_dir = self.tmpdir / "raw_data" / "Python"
        results_dir = self.tmpdir / "results"
        processed_dir = results_dir / "processed"
        labels_file = processed_dir / "Python_All.json"
        raw_labels_file = results_dir / "raw_labels.json"
        out_dir = self.tmpdir / "classifier"
        processed_dir.mkdir(parents=True)
        results_dir.mkdir(exist_ok=True)

        label_map: dict[str, str] = {}
        examples = [
            ("sdlc_test", "skills/test-writer", "test-writer", "Generate pytest tests for Python code.", "sdlc"),
            ("sdlc_debug", "skills/debugger", "debugger", "Debug failing Python exceptions and stack traces.", "sdlc"),
            ("sdlc_deploy", "skills/deploy", "deploy", "Deploy services with Docker and CI.", "sdlc"),
            ("sdlc_review", "skills/review", "code-review", "Review pull requests for code quality.", "sdlc"),
            ("meta_summary", "skills/summary", "summary", "Summarize long documents into bullets.", "agent_meta"),
            ("meta_prompt", "skills/prompt", "prompting", "Improve agent prompts and instructions.", "agent_meta"),
            ("meta_skill", "skills/skill-creator", "skill-creator", "Create new skill files for agents.", "agent_meta"),
            ("meta_memory", "", "memory", "Manage agent memory and context.", "agent_meta"),
            ("ignored_outside", "skills/outside", "outside", "Do personal calendar triage.", "outside_scope"),
            ("ignored_wrong", "skills/wrong", "wrong", "Documentation in a non-English language.", "wrong_language"),
        ]
        for repo_name, parent, skill_name, description, target in examples:
            repo_folder = f"owner__{repo_name}"
            self._write_repo(raw_dir, repo_folder, parent, skill_name, description)
            label_map[artifact_id_for(repo_folder, parent)] = target

        tag_ids = {
            "sdlc": "sdlc-id",
            "agent_meta": "agent-id",
            "outside_scope": "outside-id",
            "wrong_language": "wrong-id",
        }
        raw_labels_file.write_text(
            json.dumps(
                {
                    "version": 1,
                    "dataset": {"rootName": "Python", "totalFiles": len(label_map)},
                    "tags": [
                        {"id": tag_ids["sdlc"], "name": "code-generation"},
                        {"id": tag_ids["agent_meta"], "name": "agent-skill"},
                        {"id": tag_ids["outside_scope"], "name": "outside-scope"},
                        {"id": tag_ids["wrong_language"], "name": "non-english"},
                    ],
                    "labels": {
                        artifact_id: {"tagIds": [tag_ids[target]]}
                        for artifact_id, target in label_map.items()
                    },
                }
            ),
            encoding="utf-8",
        )

        labels_file.write_text(
            json.dumps(
                {
                    "version": 1,
                    "dataset": {
                        "rootName": "Python_All",
                        "totalFiles": len(label_map),
                        "sourceFiles": [raw_labels_file.name],
                    },
                    "tags": [],
                    "labels": {},
                }
            ),
            encoding="utf-8",
        )

        result = main(
            [
                "train",
                "--raw-data-dir",
                str(raw_dir),
                "--labels-file",
                str(labels_file),
                "--raw-results-dir",
                str(results_dir),
                "--out-dir",
                str(out_dir),
                "--min-df",
                "1",
                "--cv-folds",
                "2",
                "--test-size",
                "0.25",
                "--max-text-features",
                "2000",
                "--max-path-features",
                "1000",
                "--max-char-features",
                "1000",
                "--active-learning-top-n",
                "3",
            ]
        )

        self.assertEqual(result, 0)
        self.assertTrue((out_dir / "sdlc_classifier.joblib").is_file())
        self.assertTrue((out_dir / "evaluation.json").is_file())
        self.assertTrue((out_dir / "evaluation.md").is_file())
        self.assertTrue((out_dir / "calibration_report.json").is_file())
        self.assertTrue((out_dir / "calibration_report.md").is_file())
        self.assertTrue((out_dir / "field_feature_summary.json").is_file())
        self.assertTrue((out_dir / "clean_training_manifest.csv").is_file())
        self.assertTrue((out_dir / "ignored_training_examples.csv").is_file())
        self.assertTrue((out_dir / "threshold_sensitivity.csv").is_file())
        self.assertTrue((out_dir / "training_manifest.csv").is_file())
        predictions = (out_dir / "python_predictions.csv").read_text(encoding="utf-8")
        self.assertIn("p_sdlc", predictions)
        self.assertIn("p_agent_meta", predictions)
        self.assertIn("decision_band", predictions)
        ignored = (out_dir / "ignored_training_examples.csv").read_text(encoding="utf-8")
        self.assertIn("outside-scope", ignored)
        self.assertIn("wrong-language", ignored)

        collected = collect_artifact_table(raw_dir)
        self.assertEqual(len(collected), len(examples))

    def _write_repo(
        self,
        raw_dir: Path,
        repo_folder: str,
        parent_folder: str,
        skill_name: str,
        description: str,
    ) -> None:
        repo_dir = raw_dir / repo_folder
        local_parent = repo_dir / (parent_folder if parent_folder else "root")
        local_parent.mkdir(parents=True, exist_ok=True)
        (local_parent / "SKILL.md").write_text(
            f"""---
name: {skill_name}
description: {description}
---

# {skill_name}

Use this skill when the task matches the description.

```bash
pytest
```
""",
            encoding="utf-8",
        )
        metadata = {
            "repo": repo_folder.replace("__", "/"),
            "language": "Python",
            "stars": 10,
            "has_README": 1,
            "has_AGENTS": 1,
            "skills": [
                {
                    "skill_path": f"{parent_folder}/SKILL.md" if parent_folder else "SKILL.md",
                    "parent_folder": parent_folder,
                    "total_files": 1,
                    "references_count": 0,
                    "assets_count": 0,
                    "scripts_count": 0,
                    "other_count": 0,
                }
            ],
        }
        (repo_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
