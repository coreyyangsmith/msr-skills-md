"""
Tests for extract_skill_repos_tree.py.

Covers the tree-first Stage 2 scanner without making real network calls.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from extract_skill_repos import OUTPUT_COLUMNS, RepoSource
from extract_skill_repos_tree import (
    FetchTreeResult,
    parse_args,
    scan_one_repo_tree,
    scan_tree_entries,
)
from github_client import GitHubClient, TokenPool


PINNED_SHA = "a" * 40


class TestParseArgs(unittest.TestCase):
    def test_compatibility_and_tree_specific_flags(self):
        args = parse_args(
            [
                "--seart-dir",
                "data/seart_csvs",
                "--out-csv",
                "outputs/scan.csv",
                "--shortlist-csv",
                "outputs/short.csv",
                "--match-name",
                "SKILL.md",
                "--max-repos",
                "10",
                "--blacklist",
                "blacklist.txt",
                "--resume",
                "--include-negative-results",
                "--concurrency",
                "2",
                "--cache-dir",
                "outputs/cache/tree_scan",
                "--fallback",
                "none",
                "--cache-mode",
                "off",
                "--log-level",
                "DEBUG",
            ]
        )

        self.assertEqual(args.seart_dir, "data/seart_csvs")
        self.assertEqual(args.out_csv, "outputs/scan.csv")
        self.assertEqual(args.shortlist_csv, "outputs/short.csv")
        self.assertEqual(args.max_repos, 10)
        self.assertTrue(args.resume)
        self.assertTrue(args.include_negative_results)
        self.assertEqual(args.concurrency, 2)
        self.assertEqual(args.cache_dir, "outputs/cache/tree_scan")
        self.assertEqual(args.fallback, "none")
        self.assertEqual(args.cache_mode, "off")


class TestScanTreeEntries(unittest.TestCase):
    def test_detects_best_skill_acf_and_readiness_flags(self):
        tree = [
            {"type": "blob", "path": "z/SKILL.md", "sha": "sha-z", "size": 10},
            {"type": "blob", "path": "SKILL.md", "sha": "sha-root", "size": 20},
            {"type": "blob", "path": "README.md", "sha": "sha-readme", "size": 1},
            {"type": "blob", "path": "CONTRIBUTING.md", "sha": "sha-contrib", "size": 1},
            {"type": "blob", "path": "SECURITY.md", "sha": "sha-security", "size": 1},
            {"type": "blob", "path": "CODE_OF_CONDUCT.md", "sha": "sha-coc", "size": 1},
            {"type": "blob", "path": "CLAUDE.md", "sha": "sha-claude", "size": 1},
            {"type": "blob", "path": ".github/copilot-instructions.md", "sha": "sha-copilot", "size": 1},
            {"type": "blob", "path": "nested/GEMINI.md", "sha": "sha-gemini", "size": 1},
        ]

        detected = scan_tree_entries(tree, "SKILL.md")

        self.assertEqual(detected.best_skill["path"], "SKILL.md")
        self.assertEqual(detected.best_skill["sha"], "sha-root")
        self.assertEqual(detected.best_skill["size"], 20)
        self.assertEqual(detected.readiness_flags["has_README"], "1")
        self.assertEqual(detected.readiness_flags["has_CONTRIBUTING"], "1")
        self.assertEqual(detected.readiness_flags["has_SECURITY"], "1")
        self.assertEqual(detected.readiness_flags["has_CODE_OF_CONDUCT"], "1")
        self.assertEqual(detected.acf_flags["has_CLAUDE"], "1")
        self.assertEqual(detected.acf_flags["has_AGENTS"], "0")
        self.assertEqual(detected.acf_flags["has_COPILOT"], "1")
        self.assertEqual(detected.acf_flags["has_GEMINI"], "1")

    def test_exact_case_skill_basename_only(self):
        tree = [
            {"type": "blob", "path": "skill.md", "sha": "lower", "size": 1},
            {"type": "blob", "path": "SKILL.MD", "sha": "upper-ext", "size": 1},
            {"type": "blob", "path": "docs/not-a-skill.txt", "sha": "txt", "size": 1},
        ]

        detected = scan_tree_entries(tree, "SKILL.md")

        self.assertIsNone(detected.best_skill)


class TestScanOneRepoTree(unittest.TestCase):
    def _src(self, repo: str = "owner/repo") -> RepoSource:
        return RepoSource(
            repo=repo,
            source_csv="input.csv",
            seart_data={
                "defaultBranch": "main",
                "stargazers": "42",
                "isFork": "false",
                "isArchived": "false",
                "mainLanguage": "Python",
            },
        )

    def _gh(self) -> GitHubClient:
        return GitHubClient(pool=TokenPool([]))

    def test_found_repo_populates_scan_result_from_tree(self):
        tree = [
            {"type": "blob", "path": "skills/foo/SKILL.md", "sha": "skill-sha", "size": 512},
            {"type": "blob", "path": "README.md", "sha": "readme-sha", "size": 10},
            {"type": "blob", "path": "AGENTS.md", "sha": "agents-sha", "size": 11},
        ]

        with mock.patch("extract_skill_repos_tree.resolve_commit_sha", return_value=PINNED_SHA), mock.patch(
            "extract_skill_repos_tree.fetch_repo_tree",
            return_value=FetchTreeResult(tree=tree, status=200, error="", scan_method="tree_recursive"),
        ):
            result = scan_one_repo_tree(
                self._gh(),
                self._src(),
                "SKILL.md",
                cache_dir="",
                cache_mode="off",
                fallback="walk-tree",
            )

        self.assertTrue(result.found)
        self.assertEqual(result.scan_method, "tree_recursive")
        self.assertEqual(result.match_path, "/skills/foo/SKILL.md")
        self.assertEqual(result.match_sha, "skill-sha")
        self.assertEqual(result.match_size_bytes, "512")
        self.assertEqual(result.commit_sha, PINNED_SHA)
        self.assertEqual(result.acf_ref, PINNED_SHA)
        self.assertEqual(result.match_url, "https://github.com/owner/repo/blob/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/skills/foo/SKILL.md")
        self.assertEqual(result.has_README, "1")
        self.assertEqual(result.has_AGENTS, "1")
        self.assertEqual(result.has_CLAUDE, "0")
        self.assertEqual(result.error_type, "none")

    def test_not_found_repo_is_not_error(self):
        tree = [{"type": "blob", "path": "README.md", "sha": "readme-sha", "size": 10}]

        with mock.patch("extract_skill_repos_tree.resolve_commit_sha", return_value=PINNED_SHA), mock.patch(
            "extract_skill_repos_tree.fetch_repo_tree",
            return_value=FetchTreeResult(tree=tree, status=200, error="", scan_method="tree_recursive"),
        ):
            result = scan_one_repo_tree(
                self._gh(),
                self._src(),
                "SKILL.md",
                cache_dir="",
                cache_mode="off",
                fallback="walk-tree",
            )

        self.assertFalse(result.found)
        self.assertEqual(result.error_type, "none")
        self.assertEqual(result.http_status, "200")
        self.assertEqual(result.commit_sha, "")
        self.assertEqual(result.has_README, "1")

    def test_tree_error_is_preserved(self):
        with mock.patch("extract_skill_repos_tree.resolve_commit_sha", return_value=PINNED_SHA), mock.patch(
            "extract_skill_repos_tree.fetch_repo_tree",
            return_value=FetchTreeResult(tree=[], status=403, error="API rate limit exceeded", scan_method="tree_recursive"),
        ):
            result = scan_one_repo_tree(
                self._gh(),
                self._src(),
                "SKILL.md",
                cache_dir="",
                cache_mode="off",
                fallback="walk-tree",
            )

        self.assertFalse(result.found)
        self.assertEqual(result.error_type, "rate_limited")
        self.assertIn("rate limit", result.error_message.lower())

    def test_output_schema_is_reused(self):
        self.assertIn("acf_ref", OUTPUT_COLUMNS)
        self.assertIn("has_GEMINI", OUTPUT_COLUMNS)

    def test_fetch_repo_tree_cache_written_and_reused(self):
        from extract_skill_repos_tree import fetch_repo_tree

        gh = mock.MagicMock(spec=GitHubClient)
        gh.request_json_with_headers.return_value = (
            200,
            {"truncated": False, "tree": [{"type": "blob", "path": "SKILL.md", "sha": "s", "size": 1}]},
            {"ETag": '"etag-1"'},
            "",
        )

        with tempfile.TemporaryDirectory() as tmp:
            first = fetch_repo_tree(
                gh,
                "owner/repo",
                PINNED_SHA,
                cache_dir=tmp,
                cache_mode="read-write",
                fallback="walk-tree",
            )
            second = fetch_repo_tree(
                gh,
                "owner/repo",
                PINNED_SHA,
                cache_dir=tmp,
                cache_mode="read-write",
                fallback="walk-tree",
            )

        self.assertEqual(first.tree, second.tree)
        gh.request_json_with_headers.assert_called_once()

    def test_truncated_tree_uses_walk_fallback(self):
        from extract_skill_repos_tree import fetch_repo_tree

        gh = mock.MagicMock(spec=GitHubClient)
        gh.request_json_with_headers.side_effect = [
            (200, {"truncated": True, "tree": []}, {}, ""),
            (
                200,
                {
                    "tree": [
                        {"type": "tree", "path": "skills", "sha": "tree-skills"},
                        {"type": "blob", "path": "README.md", "sha": "readme", "size": 1},
                    ]
                },
                {},
                "",
            ),
            (
                200,
                {"tree": [{"type": "blob", "path": "foo/SKILL.md", "sha": "skill", "size": 2}]},
                {},
                "",
            ),
        ]

        result = fetch_repo_tree(
            gh,
            "owner/repo",
            PINNED_SHA,
            cache_dir="",
            cache_mode="off",
            fallback="walk-tree",
        )

        self.assertEqual(result.scan_method, "tree_walk")
        self.assertEqual(result.error, "")
        self.assertEqual(
            sorted(item["path"] for item in result.tree),
            ["README.md", "skills/foo/SKILL.md"],
        )


if __name__ == "__main__":
    unittest.main()
