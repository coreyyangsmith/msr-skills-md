"""
Tests for C_generate_dataset.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

# Make src/ importable without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from C_generate_dataset import (
    RepoDatasetRow,
    SkillInstance,
    SkillMetrics,
    compute_skill_metrics,
    find_skill_instances,
    load_already_processed,
    load_found_repos,
    process_repo,
    write_dataset_header,
)
from github_client import GitHubClient, TokenPool


class TestBGenerateDataset(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.raw_data_dir = os.path.join(self.temp_dir.name, "raw_data")
        self.out_csv = os.path.join(self.temp_dir.name, "out.csv")
        self.gh = GitHubClient(TokenPool([]))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_compute_skill_metrics(self):
        # Empty
        m = compute_skill_metrics("skills/foo", [], "SKILL.md")
        self.assertEqual(m.total_files, 0)

        # Basic
        files = [
            {"path": "skills/foo/SKILL.md"},
            {"path": "skills/foo/references/doc.txt"},
            {"path": "skills/foo/assets/img.png"},
            {"path": "skills/foo/assets/logo.png"},
            {"path": "skills/foo/scripts/run.sh"},
            {"path": "skills/foo/other/misc.txt"},
            {"path": "skills/foo/top_level.txt"},
        ]
        m = compute_skill_metrics("skills/foo", files, "SKILL.md")
        self.assertEqual(m.total_files, 7)
        self.assertEqual(m.references_count, 1)
        self.assertEqual(m.assets_count, 2)
        self.assertEqual(m.scripts_count, 1)
        self.assertEqual(m.other_count, 2)  # other/misc.txt, top_level.txt

    def test_find_skill_instances(self):
        tree = [
            {"path": "SKILL.md", "type": "blob"},
            {"path": "readme.md", "type": "blob"},
            {"path": "docs/SKILL.md", "type": "blob"},
            {"path": "docs/info.txt", "type": "blob"},
            {"path": "docs/assets/pic.png", "type": "blob"},
            {"path": "docs/src", "type": "tree"}, # should be ignored
        ]
        
        skills = find_skill_instances(tree, "SKILL.md")
        self.assertEqual(len(skills), 2)
        
        # Skill 1 (root)
        s1 = skills[0]
        self.assertEqual(s1.skill_path, "SKILL.md")
        self.assertEqual(s1.parent_folder, "")
        self.assertEqual(s1.metrics.total_files, 5) # All blobs are included if parent is root
        
        # Skill 2 (docs)
        s2 = skills[1]
        self.assertEqual(s2.skill_path, "docs/SKILL.md")
        self.assertEqual(s2.parent_folder, "docs")
        self.assertEqual(s2.metrics.total_files, 3) # docs/SKILL.md, docs/info.txt, docs/assets/pic.png
        self.assertEqual(s2.metrics.other_count, 1) # info.txt
        self.assertEqual(s2.metrics.assets_count, 1) # assets/pic.png

    @mock.patch("C_generate_dataset.fetch_repo_tree")
    @mock.patch("C_generate_dataset.download_skill_files", return_value=[])
    def test_process_repo(self, mock_download, mock_fetch):
        mock_fetch.return_value = ([
            {"path": "skills/my_skill/SKILL.md", "type": "blob", "sha": "111", "size": 10},
            {"path": "skills/my_skill/references/ref.txt", "type": "blob", "sha": "222", "size": 20},
        ], "")
        
        row = {
            "repo": "owner/repo",
            "default_branch": "main",
            "stars": "100",
            "fork": "false",
            "archived": "false",
        }
        
        result_row, errors = process_repo(self.gh, row, self.raw_data_dir, "SKILL.md")
        
        self.assertIsNotNone(result_row)
        self.assertEqual(errors, [])
        self.assertEqual(result_row.repo, "owner/repo")
        self.assertEqual(result_row.skill_count, 1)
        self.assertEqual(result_row.skill_paths, "skills/my_skill/SKILL.md")
        self.assertEqual(result_row.total_files_in_skills, 2)
        self.assertEqual(result_row.references_file_count, 1)
        
        # Check metadata.json creation
        metadata_path = os.path.join(self.raw_data_dir, "owner__repo", "metadata.json")
        self.assertTrue(os.path.exists(metadata_path))
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            self.assertEqual(meta["repo"], "owner/repo")
            self.assertEqual(meta["skill_count"], 1)
            self.assertEqual(len(meta["skills"]), 1)
            self.assertEqual(meta["skills"][0]["skill_path"], "skills/my_skill/SKILL.md")

    @mock.patch("C_generate_dataset.fetch_repo_tree")
    def test_process_repo_resume_skips(self, mock_fetch):
        # Create metadata to simulate already processed
        repo_dir = os.path.join(self.raw_data_dir, "owner__repo")
        os.makedirs(repo_dir, exist_ok=True)
        with open(os.path.join(repo_dir, "metadata.json"), "w") as f:
            json.dump({"repo": "owner/repo"}, f)
            
        row = {"repo": "owner/repo", "default_branch": "main"}
        result_row, errors = process_repo(self.gh, row, self.raw_data_dir, "SKILL.md")
        
        self.assertIsNone(result_row)
        self.assertEqual(errors, [])
        mock_fetch.assert_not_called()

    @mock.patch("C_generate_dataset.download_blob")
    def test_download_skill_files(self, mock_download):
        mock_download.return_value = (b"test content", "")
        
        skill = SkillInstance(
            skill_path="sk/SKILL.md",
            parent_folder="sk",
            metrics=SkillMetrics(),
            files=[
                {"path": "sk/SKILL.md", "sha": "111", "size": 12},
                {"path": "sk/assets/img.png", "sha": "222", "size": 5},
            ]
        )
        
        from C_generate_dataset import download_skill_files
        errors = download_skill_files(self.gh, "owner/repo", skill, self.raw_data_dir)
        self.assertEqual(errors, [])
        
        self.assertTrue(os.path.exists(os.path.join(self.raw_data_dir, "owner__repo", "sk", "SKILL.md")))
        self.assertTrue(os.path.exists(os.path.join(self.raw_data_dir, "owner__repo", "sk", "assets", "img.png")))
        with open(os.path.join(self.raw_data_dir, "owner__repo", "sk", "SKILL.md"), "rb") as f:
            self.assertEqual(f.read(), b"test content")

if __name__ == "__main__":
    unittest.main()
