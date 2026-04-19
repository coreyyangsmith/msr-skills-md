"""
Tests for generate_dataset.py
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

# Make src/ importable without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generate_dataset import (
    SkillInstance,
    SkillInstanceRow,
    SkillMetrics,
    compute_skill_metrics,
    fetch_repo_tree,
    find_skill_instances,
    load_already_processed,
    load_found_repos,
    parse_args,
    process_repo,
    record_failure,
    validate_existing_output_header,
    write_dataset_header,
)
from github_client import GitHubClient, TokenPool


def _workspace_test_dir(prefix: str) -> Path:
    path = Path.cwd() / "outputs" / f"{prefix}_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class TestComputeSkillMetrics(unittest.TestCase):
    def test_empty_files(self):
        m = compute_skill_metrics("skills/foo", [], "SKILL.md")
        self.assertEqual(m.total_files, 0)

    def test_basic_categorisation(self):
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


class TestFindSkillInstances(unittest.TestCase):
    def test_finds_multiple_instances(self):
        tree = [
            {"path": "SKILL.md", "type": "blob"},
            {"path": "readme.md", "type": "blob"},
            {"path": "docs/SKILL.md", "type": "blob"},
            {"path": "docs/info.txt", "type": "blob"},
            {"path": "docs/assets/pic.png", "type": "blob"},
            {"path": "docs/src", "type": "tree"},  # trees are ignored
        ]
        skills = find_skill_instances(tree, "SKILL.md")
        self.assertEqual(len(skills), 2)

    def test_root_skill_includes_root_blobs_and_skill_subdirs(self):
        tree = [
            {"path": "SKILL.md", "type": "blob"},
            {"path": "readme.md", "type": "blob"},
            {"path": "assets/pic.png", "type": "blob"},
            {"path": "scripts/run.sh", "type": "blob"},
            {"path": "other/misc.txt", "type": "blob"},
            {"path": "docs/nested.md", "type": "blob"},  # not a skill subdir
        ]
        skills = find_skill_instances(tree, "SKILL.md")
        self.assertEqual(len(skills), 1)
        # Only root-level files and skill subdirs (assets, scripts) included
        paths = {f["path"] for f in skills[0].files}
        self.assertIn("SKILL.md", paths)
        self.assertIn("readme.md", paths)
        self.assertIn("assets/pic.png", paths)
        self.assertIn("scripts/run.sh", paths)
        self.assertNotIn("docs/nested.md", paths)

    def test_subdir_skill_metrics(self):
        tree = [
            {"path": "docs/SKILL.md", "type": "blob"},
            {"path": "docs/info.txt", "type": "blob"},
            {"path": "docs/assets/pic.png", "type": "blob"},
        ]
        skills = find_skill_instances(tree, "SKILL.md")
        self.assertEqual(len(skills), 1)
        s = skills[0]
        self.assertEqual(s.skill_path, "docs/SKILL.md")
        self.assertEqual(s.parent_folder, "docs")
        self.assertEqual(s.metrics.total_files, 3)
        self.assertEqual(s.metrics.other_count, 1)  # info.txt
        self.assertEqual(s.metrics.assets_count, 1)  # assets/pic.png

    def test_case_sensitive_match(self):
        tree = [
            {"path": "SKILL.MD", "type": "blob"},
            {"path": "skill.md", "type": "blob"},
        ]
        skills = find_skill_instances(tree, "SKILL.md")
        self.assertEqual(len(skills), 0)

    def test_instances_sorted_by_path(self):
        tree = [
            {"path": "z/SKILL.md", "type": "blob"},
            {"path": "a/SKILL.md", "type": "blob"},
        ]
        skills = find_skill_instances(tree, "SKILL.md")
        self.assertEqual([s.skill_path for s in skills], ["a/SKILL.md", "z/SKILL.md"])


class TestFetchRepoTree(unittest.TestCase):
    def _gh(self):
        return GitHubClient(TokenPool([]))

    def test_success_returns_tree_items(self):
        gh = self._gh()
        tree_data = {"tree": [{"path": "SKILL.md", "type": "blob"}], "truncated": False}
        gh.request_json = mock.MagicMock(return_value=(200, tree_data, ""))
        items, err = fetch_repo_tree(gh, "owner/repo", "main")
        self.assertEqual(err, "")
        self.assertEqual(len(items), 1)

    def test_truncated_tree_returns_error(self):
        """A truncated tree must be treated as an error, not silently accepted."""
        gh = self._gh()
        tree_data = {"tree": [{"path": "SKILL.md", "type": "blob"}], "truncated": True}
        gh.request_json = mock.MagicMock(return_value=(200, tree_data, ""))
        items, err = fetch_repo_tree(gh, "owner/repo", "main")
        self.assertEqual(items, [])
        self.assertEqual(err, "tree_truncated")

    def test_404_returns_tree_not_found(self):
        gh = self._gh()
        gh.request_json = mock.MagicMock(return_value=(404, {}, "Not Found"))
        items, err = fetch_repo_tree(gh, "owner/repo", "main")
        self.assertEqual(items, [])
        self.assertEqual(err, "tree_not_found")

    def test_409_empty_repo_returns_tree_not_found(self):
        gh = self._gh()
        gh.request_json = mock.MagicMock(return_value=(409, {}, ""))
        items, err = fetch_repo_tree(gh, "owner/repo", "main")
        self.assertEqual(items, [])
        self.assertEqual(err, "tree_not_found")


class TestParseArgs(unittest.TestCase):
    def _parse(self, *extra):
        return parse_args([
            "--found-csv", "found.csv",
            "--out-csv", "out.csv",
            "--raw-data-dir", "raw",
            *extra,
        ])

    def test_default_name_filter_enabled(self):
        args = self._parse()
        self.assertFalse(args.no_name_filter)

    def test_default_relevance_terms_path(self):
        args = self._parse()
        self.assertEqual(args.relevance_terms, "relevance_terms.txt")

    def test_no_name_filter_flag(self):
        args = self._parse("--no-name-filter")
        self.assertTrue(args.no_name_filter)


class TestProcessRepo(unittest.TestCase):
    def setUp(self):
        self.temp_dir = _workspace_test_dir("generate_dataset_process")
        self.raw_data_dir = os.path.join(self.temp_dir, "raw_data")
        self.gh = GitHubClient(TokenPool([]))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def _row(self, **kwargs):
        defaults = {
            "repo": "owner/repo",
            "default_branch": "main",
            "stars": "100",
            "fork": "false",
            "archived": "false",
            "has_README": "0",
            "has_CONTRIBUTING": "0",
            "has_SECURITY": "0",
            "has_CODE_OF_CONDUCT": "0",
        }
        defaults.update(kwargs)
        return defaults

    @mock.patch("generate_dataset.fetch_repo_tree")
    @mock.patch("generate_dataset.download_skill_files", return_value=[])
    def test_process_repo_writes_metadata_when_skills_found(self, mock_download, mock_fetch):
        mock_fetch.return_value = ([
            {"path": "skills/my_skill/SKILL.md", "type": "blob", "sha": "111", "size": 10},
            {"path": "skills/my_skill/references/ref.txt", "type": "blob", "sha": "222", "size": 20},
        ], "")

        skill_rows, errors = process_repo(self.gh, self._row(), self.raw_data_dir, "SKILL.md")

        self.assertEqual(errors, [])
        self.assertEqual(len(skill_rows), 1)
        self.assertEqual(skill_rows[0].repo, "owner/repo")
        self.assertEqual(skill_rows[0].skill_path, "skills/my_skill/SKILL.md")
        self.assertEqual(skill_rows[0].references_file_count, 1)

        # metadata.json must exist when skills were found
        language = ""
        repo_safe = "owner__repo"
        language_safe = "unknown"
        metadata_path = os.path.join(self.raw_data_dir, language_safe, repo_safe, "metadata.json")
        self.assertTrue(os.path.exists(metadata_path))
        with open(metadata_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.assertEqual(meta["repo"], "owner/repo")
        self.assertEqual(meta["skill_count"], 1)

    @mock.patch("generate_dataset.fetch_repo_tree")
    @mock.patch("generate_dataset.download_skill_files", return_value=[])
    def test_process_repo_carries_maintainer_flags_into_rows_and_metadata(self, mock_download, mock_fetch):
        mock_fetch.return_value = ([
            {"path": "skills/my_skill/SKILL.md", "type": "blob", "sha": "111", "size": 10},
        ], "")

        row = self._row(
            has_README="1",
            has_CONTRIBUTING="1",
            has_SECURITY="0",
            has_CODE_OF_CONDUCT="1",
        )
        skill_rows, errors = process_repo(self.gh, row, self.raw_data_dir, "SKILL.md")

        self.assertEqual(errors, [])
        self.assertEqual(len(skill_rows), 1)
        skill_row = skill_rows[0]
        self.assertEqual(skill_row.has_README, 1)
        self.assertEqual(skill_row.has_CONTRIBUTING, 1)
        self.assertEqual(skill_row.has_SECURITY, 0)
        self.assertEqual(skill_row.has_CODE_OF_CONDUCT, 1)

        metadata_path = os.path.join(self.raw_data_dir, "unknown", "owner__repo", "metadata.json")
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        self.assertEqual(metadata["has_README"], 1)
        self.assertEqual(metadata["has_CONTRIBUTING"], 1)
        self.assertEqual(metadata["has_SECURITY"], 0)
        self.assertEqual(metadata["has_CODE_OF_CONDUCT"], 1)

    @mock.patch("generate_dataset.fetch_repo_tree")
    @mock.patch("generate_dataset.download_skill_files", return_value=[])
    def test_process_repo_defaults_missing_maintainer_flags_to_zero(self, mock_download, mock_fetch):
        mock_fetch.return_value = ([
            {"path": "skills/my_skill/SKILL.md", "type": "blob", "sha": "111", "size": 10},
        ], "")

        row = self._row()
        for column in ("has_README", "has_CONTRIBUTING", "has_SECURITY", "has_CODE_OF_CONDUCT"):
            row.pop(column, None)

        skill_rows, errors = process_repo(self.gh, row, self.raw_data_dir, "SKILL.md")

        self.assertEqual(errors, [])
        self.assertEqual(skill_rows[0].has_README, 0)
        self.assertEqual(skill_rows[0].has_CONTRIBUTING, 0)
        self.assertEqual(skill_rows[0].has_SECURITY, 0)
        self.assertEqual(skill_rows[0].has_CODE_OF_CONDUCT, 0)

    @mock.patch("generate_dataset.fetch_repo_tree")
    def test_process_repo_no_metadata_when_zero_skills(self, mock_fetch):
        """metadata.json must NOT be written when the tree has no matching files."""
        mock_fetch.return_value = ([
            {"path": "README.md", "type": "blob", "sha": "abc"},
        ], "")

        skill_rows, errors = process_repo(self.gh, self._row(), self.raw_data_dir, "SKILL.md")

        self.assertEqual(skill_rows, [])
        self.assertEqual(errors, ["zero_skills_found"])

        # No metadata.json should exist
        repo_safe = "owner__repo"
        language_safe = "unknown"
        metadata_path = os.path.join(self.raw_data_dir, language_safe, repo_safe, "metadata.json")
        self.assertFalse(os.path.exists(metadata_path))

    @mock.patch("generate_dataset.fetch_repo_tree")
    def test_process_repo_resume_skips_when_metadata_exists(self, mock_fetch):
        """--resume: skip repo when metadata.json already exists (skill_count > 0 run)."""
        language_safe = "unknown"
        repo_dir = os.path.join(self.raw_data_dir, language_safe, "owner__repo")
        os.makedirs(repo_dir, exist_ok=True)
        with open(os.path.join(repo_dir, "metadata.json"), "w") as f:
            json.dump({"repo": "owner/repo", "skill_count": 1}, f)

        skill_rows, errors = process_repo(self.gh, self._row(), self.raw_data_dir, "SKILL.md")

        self.assertEqual(skill_rows, [])
        self.assertEqual(errors, [])
        mock_fetch.assert_not_called()

    @mock.patch("generate_dataset.fetch_repo_tree")
    def test_process_repo_tree_fetch_error_returns_error(self, mock_fetch):
        mock_fetch.return_value = ([], "tree_not_found")
        skill_rows, errors = process_repo(self.gh, self._row(), self.raw_data_dir, "SKILL.md")
        self.assertEqual(skill_rows, [])
        self.assertTrue(any("tree_not_found" in e for e in errors))

    @mock.patch("generate_dataset.fetch_repo_tree")
    def test_process_repo_uses_commit_sha_when_available(self, mock_fetch):
        """Stage 3 should use commit_sha from the found CSV instead of default_branch."""
        mock_fetch.return_value = ([
            {"path": "SKILL.md", "type": "blob", "sha": "aaa"},
        ], "")

        row = self._row(commit_sha="deadbeefdeadbeef", default_branch="main")
        with mock.patch("generate_dataset.download_skill_files", return_value=[]):
            process_repo(self.gh, row, self.raw_data_dir, "SKILL.md")

        call_args = mock_fetch.call_args
        # Third positional arg is the ref passed to fetch_repo_tree
        ref_used = call_args[0][2]
        self.assertEqual(ref_used, "deadbeefdeadbeef")

        metadata_path = os.path.join(self.raw_data_dir, "unknown", "owner__repo", "metadata.json")
        with open(metadata_path, "r", encoding="utf-8") as f:
            metadata = json.load(f)
        self.assertEqual(metadata["tree_ref"], "deadbeefdeadbeef")

    @mock.patch("generate_dataset.fetch_repo_tree")
    def test_process_repo_falls_back_to_branch_when_no_commit_sha(self, mock_fetch):
        """When commit_sha is absent, default_branch is used as the ref."""
        mock_fetch.return_value = ([
            {"path": "SKILL.md", "type": "blob", "sha": "aaa"},
        ], "")

        row = self._row(commit_sha="", default_branch="develop")
        with mock.patch("generate_dataset.download_skill_files", return_value=[]):
            process_repo(self.gh, row, self.raw_data_dir, "SKILL.md")

        ref_used = mock_fetch.call_args[0][2]
        self.assertEqual(ref_used, "develop")


class TestDownloadSkillFiles(unittest.TestCase):
    def setUp(self):
        self.temp_dir = _workspace_test_dir("generate_dataset_download")
        self.raw_data_dir = str(self.temp_dir)
        self.gh = GitHubClient(TokenPool([]))
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    @mock.patch("generate_dataset.download_blob")
    def test_downloads_files_to_correct_paths(self, mock_download):
        from generate_dataset import download_skill_files
        mock_download.return_value = (b"test content", "")

        skill = SkillInstance(
            skill_path="sk/SKILL.md",
            parent_folder="sk",
            metrics=SkillMetrics(),
            files=[
                {"path": "sk/SKILL.md", "sha": "111", "size": 12},
                {"path": "sk/assets/img.png", "sha": "222", "size": 5},
            ],
        )
        errors = download_skill_files(self.gh, "owner/repo", skill, self.raw_data_dir)
        self.assertEqual(errors, [])
        self.assertTrue(os.path.exists(os.path.join(self.raw_data_dir, "sk", "SKILL.md")))
        self.assertTrue(os.path.exists(os.path.join(self.raw_data_dir, "sk", "assets", "img.png")))


class TestLoadFoundRepos(unittest.TestCase):
    def test_returns_empty_for_missing_file(self):
        self.assertEqual(load_found_repos("/nonexistent/path.csv"), [])

    def test_reads_rows_from_csv(self):
        import csv
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
        ) as f:
            writer = csv.DictWriter(f, fieldnames=["repo", "default_branch"])
            writer.writeheader()
            writer.writerow({"repo": "owner/repo", "default_branch": "main"})
            tmp_path = f.name
        try:
            rows = load_found_repos(tmp_path)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["repo"], "owner/repo")
        finally:
            os.unlink(tmp_path)


class TestValidateExistingOutputHeader(unittest.TestCase):
    def setUp(self):
        self.tmpdir = _workspace_test_dir("generate_dataset_header")
        self.out_csv = self.tmpdir / "instances.csv"
        self.addCleanup(lambda: shutil.rmtree(self.tmpdir, ignore_errors=True))

    def test_missing_file_is_allowed(self):
        validate_existing_output_header(str(self.out_csv))

    def test_matching_header_is_allowed(self):
        from generate_dataset import OUTPUT_COLUMNS

        with self.out_csv.open("w", newline="", encoding="utf-8") as f:
            import csv

            writer = csv.writer(f)
            writer.writerow(OUTPUT_COLUMNS)
        validate_existing_output_header(str(self.out_csv))

    def test_mismatched_header_raises(self):
        with self.out_csv.open("w", newline="", encoding="utf-8") as f:
            import csv

            writer = csv.writer(f)
            writer.writerow(["repo", "skill_path"])
        with self.assertRaises(ValueError):
            validate_existing_output_header(str(self.out_csv))


class TestRecordFailure(unittest.TestCase):
    def setUp(self):
        self.temp_dir = _workspace_test_dir("generate_dataset_failures")
        self.log_path = os.path.join(self.temp_dir, "failures.tsv")
        self.addCleanup(lambda: shutil.rmtree(self.temp_dir, ignore_errors=True))

    def test_creates_file_on_first_write(self):
        record_failure(self.log_path, "owner/repo", "zero_skills_found", "")
        self.assertTrue(os.path.exists(self.log_path))

    def test_appends_tab_separated_columns(self):
        record_failure(self.log_path, "owner/repo", "tree_fetch_failed", "tree_not_found")
        with open(self.log_path, "r", encoding="utf-8") as f:
            line = f.readline()
        parts = line.strip().split("\t")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "owner/repo")
        self.assertEqual(parts[1], "tree_fetch_failed")
        self.assertEqual(parts[2], "tree_not_found")

    def test_multiple_failures_are_each_on_own_line(self):
        record_failure(self.log_path, "a/b", "zero_skills_found", "")
        record_failure(self.log_path, "c/d", "exception", "boom")
        with open(self.log_path, "r", encoding="utf-8") as f:
            lines = [l for l in f.readlines() if l.strip()]
        self.assertEqual(len(lines), 2)

    def test_creates_parent_dirs_if_missing(self):
        nested_path = os.path.join(self.temp_dir.name, "subdir", "failures.tsv")
        record_failure(nested_path, "owner/repo", "zero_skills_found", "")
        self.assertTrue(os.path.exists(nested_path))


class TestLoadAlreadyProcessed(unittest.TestCase):
    def test_returns_empty_for_missing_file(self):
        self.assertEqual(load_already_processed("/nonexistent.csv"), set())

    def test_reads_repos_from_existing_csv(self):
        import csv
        from generate_dataset import OUTPUT_COLUMNS
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8"
        ) as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            row = {col: "" for col in OUTPUT_COLUMNS}
            row["repo"] = "owner/repo"
            writer.writerow(row)
            tmp_path = f.name
        try:
            result = load_already_processed(tmp_path)
            self.assertIn("owner/repo", result)
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
