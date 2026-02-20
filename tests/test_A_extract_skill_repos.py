"""
Tests for A_extract_skill_repos.py

Covers:
- normalize_repo        (pure function)
- extract_repo_from_row (pure function)
- classify_error        (pure function)
- parse_args            (CLI wiring)
- ingest_seart_csvs     (file I/O)
- load_already_scanned  (file I/O)
- write_header_if_needed / append_result (file I/O)
- write_shortlist       (file I/O)
- try_contents_path     (mocked HTTP)
- try_code_search       (mocked HTTP)
- GitHubClient          (mocked HTTP, retry/backoff behaviour)
- scan_one_repo         (mocked dependencies)

All tests are deterministic: no real network calls, time is frozen where
timestamps are asserted, and temp directories are cleaned up after each test.
"""

from __future__ import annotations

import csv
import os
import shutil
import sys
import tempfile
import time
import unittest
import unittest.mock as mock
from pathlib import Path

import requests

# Make src/ importable without installing the package.
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from A_extract_skill_repos import (
    OUTPUT_COLUMNS,
    RepoSource,
    ScanResult,
    append_result,
    check_rate_limit,
    classify_error,
    extract_repo_from_row,
    ingest_seart_csvs,
    load_already_scanned,
    normalize_repo,
    parse_args,
    scan_one_repo,
    setup_logging,
    try_code_search,
    try_contents_path,
    write_header_if_needed,
    write_shortlist,
)
from github_client import GitHubClient, TokenPool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scan_result(repo: str = "owner/repo", found: bool = False) -> ScanResult:
    return ScanResult(
        repo=repo,
        source_csv="test.csv",
        found=found,
        match_name="SKILL.md",
        match_path="/SKILL.md" if found else "",
        default_branch="main",
        ref_scanned="main",
        match_url="https://github.com/owner/repo/blob/main/SKILL.md" if found else "",
        match_sha="abc123" if found else "",
        match_size_bytes="512" if found else "",
        scan_method="contents_api",
        http_status="200" if found else "404",
        error_type="none",
        error_message="",
        scanned_at_utc="2024-01-01T00:00:00Z",
        stars="42",
        fork="false",
        archived="false",
    )


def _make_http_response(
    status_code: int,
    json_data: dict | None = None,
    text: str = "",
    headers: dict | None = None,
) -> mock.MagicMock:
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.text = text
    if json_data is not None:
        resp.content = b"x"
        resp.json.return_value = json_data
    else:
        resp.content = b""
        resp.json.side_effect = Exception("no body")
    return resp


def _make_meta(
    branch: str = "main",
    stars: int = 10,
    fork: bool = False,
    archived: bool = False,
) -> dict:
    return {
        "default_branch": branch,
        "stargazers_count": stars,
        "fork": fork,
        "archived": archived,
    }


# ---------------------------------------------------------------------------
# normalize_repo
# ---------------------------------------------------------------------------

class TestNormalizeRepo(unittest.TestCase):

    def test_plain_owner_repo(self):
        self.assertEqual(normalize_repo("psf/requests"), "psf/requests")

    def test_strips_git_suffix(self):
        self.assertEqual(normalize_repo("psf/requests.git"), "psf/requests")

    def test_https_url(self):
        self.assertEqual(normalize_repo("https://github.com/psf/requests"), "psf/requests")

    def test_http_url(self):
        self.assertEqual(normalize_repo("http://github.com/psf/requests"), "psf/requests")

    def test_url_with_trailing_path_segments(self):
        self.assertEqual(
            normalize_repo("https://github.com/psf/requests/issues/123"),
            "psf/requests",
        )

    def test_url_with_git_suffix(self):
        self.assertEqual(
            normalize_repo("https://github.com/psf/requests.git"),
            "psf/requests",
        )

    def test_strips_surrounding_whitespace(self):
        self.assertEqual(normalize_repo("  psf/requests  "), "psf/requests")

    def test_dashes_and_underscores_are_valid(self):
        self.assertEqual(normalize_repo("my-org/my_repo"), "my-org/my_repo")

    def test_dots_in_names_are_valid(self):
        self.assertEqual(normalize_repo("my.org/my.repo"), "my.org/my.repo")

    def test_empty_string_returns_none(self):
        self.assertIsNone(normalize_repo(""))

    def test_single_segment_returns_none(self):
        self.assertIsNone(normalize_repo("not-a-repo"))

    def test_space_in_name_returns_none(self):
        self.assertIsNone(normalize_repo("owner/repo name"))

    def test_three_segments_not_url_returns_none(self):
        self.assertIsNone(normalize_repo("a/b/c"))


# ---------------------------------------------------------------------------
# extract_repo_from_row
# ---------------------------------------------------------------------------

class TestExtractRepoFromRow(unittest.TestCase):

    def test_full_name_column(self):
        self.assertEqual(
            extract_repo_from_row({"full_name": "psf/requests"}), "psf/requests"
        )

    def test_repo_column(self):
        self.assertEqual(
            extract_repo_from_row({"repo": "psf/requests"}), "psf/requests"
        )

    def test_repository_column(self):
        self.assertEqual(
            extract_repo_from_row({"repository": "psf/requests"}), "psf/requests"
        )

    def test_full_name_takes_priority_over_repo(self):
        row = {"full_name": "owner/correct", "repo": "owner/wrong"}
        self.assertEqual(extract_repo_from_row(row), "owner/correct")

    def test_owner_and_name_pair(self):
        self.assertEqual(
            extract_repo_from_row({"owner": "psf", "name": "requests"}), "psf/requests"
        )

    def test_org_and_repo_name_pair(self):
        self.assertEqual(
            extract_repo_from_row({"org": "psf", "repo_name": "requests"}), "psf/requests"
        )

    def test_repo_owner_and_repo_name_pair(self):
        self.assertEqual(
            extract_repo_from_row({"repo_owner": "psf", "repo_name": "requests"}),
            "psf/requests",
        )

    def test_html_url_column(self):
        self.assertEqual(
            extract_repo_from_row({"html_url": "https://github.com/psf/requests"}),
            "psf/requests",
        )

    def test_url_column(self):
        self.assertEqual(
            extract_repo_from_row({"url": "https://github.com/psf/requests"}),
            "psf/requests",
        )

    def test_empty_row_returns_none(self):
        self.assertIsNone(extract_repo_from_row({}))

    def test_unsupported_columns_returns_none(self):
        self.assertIsNone(extract_repo_from_row({"id": "123", "language": "Python"}))

    def test_empty_values_are_skipped(self):
        self.assertIsNone(extract_repo_from_row({"full_name": "", "repo": ""}))

    def test_pair_skipped_when_one_value_is_empty(self):
        # Only one half of the pair present -- should not combine into "psf/"
        self.assertIsNone(extract_repo_from_row({"owner": "psf", "name": ""}))

    def test_name_column_with_owner_slash_repo(self):
        # SEART exports store owner/repo in the "name" column
        self.assertEqual(
            extract_repo_from_row({"name": "maxbbraun/accent"}), "maxbbraun/accent"
        )

    def test_name_column_without_slash_returns_none(self):
        # Short name alone is not a valid owner/repo
        self.assertIsNone(extract_repo_from_row({"name": "accent"}))

    def test_name_column_falls_through_to_pair_when_short(self):
        # name="accent" (no owner) falls through; owner+name pair is used instead
        self.assertEqual(
            extract_repo_from_row({"owner": "psf", "name": "requests"}), "psf/requests"
        )


# ---------------------------------------------------------------------------
# classify_error
# ---------------------------------------------------------------------------

class TestClassifyError(unittest.TestCase):

    def test_status_zero_is_network(self):
        self.assertEqual(classify_error(0, "connection refused"), "network")

    def test_401_is_auth(self):
        self.assertEqual(classify_error(401, "Unauthorized"), "auth")

    def test_404_with_not_found_message_is_invalid_repo(self):
        self.assertEqual(classify_error(404, "Not Found"), "invalid_repo")

    def test_404_without_not_found_message_is_not_found(self):
        self.assertEqual(classify_error(404, "some other message"), "not_found")

    def test_403_is_rate_limited(self):
        self.assertEqual(classify_error(403, "API rate limit exceeded"), "rate_limited")

    def test_429_is_rate_limited(self):
        self.assertEqual(classify_error(429, "Too Many Requests"), "rate_limited")

    def test_500_is_other(self):
        self.assertEqual(classify_error(500, "Internal Server Error"), "other")

    def test_422_is_other(self):
        self.assertEqual(classify_error(422, "Unprocessable Entity"), "other")

    def test_empty_message_does_not_crash(self):
        self.assertEqual(classify_error(404, ""), "not_found")


# ---------------------------------------------------------------------------
# parse_args
# ---------------------------------------------------------------------------

class TestParseArgs(unittest.TestCase):

    def _parse(self, *extra):
        return parse_args(["--seart-dir", "data/", "--out-csv", "out.csv", *extra])

    def test_required_args_parsed(self):
        args = self._parse()
        self.assertEqual(args.seart_dir, "data/")
        self.assertEqual(args.out_csv, "out.csv")

    def test_default_match_name_is_skill_md(self):
        self.assertEqual(self._parse().match_name, "SKILL.md")

    def test_default_concurrency(self):
        self.assertEqual(self._parse().concurrency, 4)

    def test_default_min_stars_is_zero(self):
        self.assertEqual(self._parse().min_stars, 0)

    def test_disable_code_search_flag(self):
        self.assertTrue(self._parse("--disable-code-search").disable_code_search)

    def test_code_search_on_by_default(self):
        self.assertFalse(self._parse().disable_code_search)

    def test_disallow_forks_flag(self):
        self.assertTrue(self._parse("--disallow-forks").disallow_forks)

    def test_disallow_archived_flag(self):
        self.assertTrue(self._parse("--disallow-archived").disallow_archived)

    def test_resume_flag(self):
        self.assertTrue(self._parse("--resume").resume)

    def test_include_negative_results_flag(self):
        self.assertTrue(self._parse("--include-negative-results").include_negative_results)

    def test_search_path_appends(self):
        args = self._parse("--search-path", "/SKILL.md", "--search-path", "/docs/SKILL.md")
        self.assertEqual(args.search_path, ["/SKILL.md", "/docs/SKILL.md"])

    def test_missing_required_args_raises(self):
        with self.assertRaises(SystemExit):
            parse_args([])

    def test_default_log_level_is_info(self):
        self.assertEqual(self._parse().log_level, "INFO")

    def test_log_level_debug(self):
        self.assertEqual(self._parse("--log-level", "DEBUG").log_level, "DEBUG")

    def test_github_tokens_flag(self):
        args = self._parse("--github-tokens", "tok1,tok2")
        self.assertEqual(args.github_tokens, "tok1,tok2")

    def test_github_token_single_flag_still_works(self):
        args = self._parse("--github-token", "ghp_single")
        self.assertEqual(args.github_token, "ghp_single")


# ---------------------------------------------------------------------------
# ingest_seart_csvs
# ---------------------------------------------------------------------------

class TestIngestSEARTCSVs(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_csv(self, filename: str, fieldnames: list, rows: list) -> str:
        path = os.path.join(self.tmpdir, filename)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_empty_directory_returns_error(self):
        repos, errors = ingest_seart_csvs(self.tmpdir)
        self.assertEqual(repos, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("No CSV files found", errors[0])

    def test_csv_with_full_name_column(self):
        self._write_csv(
            "repos.csv",
            ["full_name"],
            [{"full_name": "psf/requests"}, {"full_name": "django/django"}],
        )
        repos, errors = ingest_seart_csvs(self.tmpdir)
        self.assertEqual(errors, [])
        repo_names = {r.repo for r in repos}
        self.assertIn("psf/requests", repo_names)
        self.assertIn("django/django", repo_names)

    def test_csv_with_html_url_column(self):
        self._write_csv(
            "repos.csv",
            ["html_url"],
            [{"html_url": "https://github.com/psf/requests"}],
        )
        repos, errors = ingest_seart_csvs(self.tmpdir)
        self.assertEqual(errors, [])
        self.assertEqual(repos[0].repo, "psf/requests")

    def test_deduplication_across_multiple_csvs(self):
        self._write_csv("a.csv", ["full_name"], [{"full_name": "psf/requests"}])
        self._write_csv("b.csv", ["full_name"], [{"full_name": "psf/requests"}])
        repos, _ = ingest_seart_csvs(self.tmpdir)
        names = [r.repo for r in repos]
        self.assertEqual(names.count("psf/requests"), 1)

    def test_source_csv_is_multiple_when_repo_in_two_files(self):
        self._write_csv("a.csv", ["full_name"], [{"full_name": "psf/requests"}])
        self._write_csv("b.csv", ["full_name"], [{"full_name": "psf/requests"}])
        repos, _ = ingest_seart_csvs(self.tmpdir)
        match = next(r for r in repos if r.repo == "psf/requests")
        self.assertEqual(match.source_csv, "MULTIPLE")

    def test_source_csv_set_to_filename_when_single_source(self):
        self._write_csv("repos.csv", ["full_name"], [{"full_name": "psf/requests"}])
        repos, _ = ingest_seart_csvs(self.tmpdir)
        self.assertEqual(repos[0].source_csv, "repos.csv")

    def test_unsupported_schema_records_error(self):
        self._write_csv("repos.csv", ["id", "language"], [{"id": "1", "language": "Python"}])
        repos, errors = ingest_seart_csvs(self.tmpdir)
        self.assertEqual(repos, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("repos.csv", errors[0])

    def test_invalid_repo_values_are_skipped(self):
        self._write_csv(
            "repos.csv",
            ["full_name"],
            [{"full_name": "not-valid"}, {"full_name": "psf/requests"}],
        )
        repos, _ = ingest_seart_csvs(self.tmpdir)
        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0].repo, "psf/requests")

    def test_result_list_is_sorted(self):
        self._write_csv(
            "repos.csv",
            ["full_name"],
            [{"full_name": "z/z"}, {"full_name": "a/a"}],
        )
        repos, _ = ingest_seart_csvs(self.tmpdir)
        names = [r.repo for r in repos]
        self.assertEqual(names, sorted(names))

    def test_seart_style_csv_with_name_column(self):
        # Mirrors the real SEART export format where "name" = owner/repo
        seart_fields = ["id", "name", "isFork", "commits", "mainLanguage", "defaultBranch"]
        self._write_csv(
            "repos.csv",
            seart_fields,
            [
                {"id": "3390424", "name": "maxbbraun/accent", "isFork": "false",
                 "commits": "260", "mainLanguage": "Python", "defaultBranch": "master"},
                {"id": "3393605", "name": "mendhak/waveshare-epaper-display", "isFork": "false",
                 "commits": "549", "mainLanguage": "Python", "defaultBranch": "master"},
            ],
        )
        repos, errors = ingest_seart_csvs(self.tmpdir)
        self.assertEqual(errors, [])
        repo_names = {r.repo for r in repos}
        self.assertIn("maxbbraun/accent", repo_names)
        self.assertIn("mendhak/waveshare-epaper-display", repo_names)


# ---------------------------------------------------------------------------
# load_already_scanned
# ---------------------------------------------------------------------------

class TestLoadAlreadyScanned(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_nonexistent_file_returns_empty_set(self):
        result = load_already_scanned(os.path.join(self.tmpdir, "nonexistent.csv"))
        self.assertEqual(result, set())

    def test_empty_string_path_returns_empty_set(self):
        self.assertEqual(load_already_scanned(""), set())

    def test_returns_repos_from_existing_csv(self):
        path = os.path.join(self.tmpdir, "results.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            for repo in ("psf/requests", "django/django"):
                row = {col: "" for col in OUTPUT_COLUMNS}
                row["repo"] = repo
                writer.writerow(row)
        result = load_already_scanned(path)
        self.assertIn("psf/requests", result)
        self.assertIn("django/django", result)

    def test_strips_whitespace_from_repo_names(self):
        path = os.path.join(self.tmpdir, "results.csv")
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            row = {col: "" for col in OUTPUT_COLUMNS}
            row["repo"] = "  psf/requests  "
            writer.writerow(row)
        result = load_already_scanned(path)
        self.assertIn("psf/requests", result)


# ---------------------------------------------------------------------------
# write_header_if_needed / append_result
# ---------------------------------------------------------------------------

class TestWriteHeaderAndAppend(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.out_csv = os.path.join(self.tmpdir, "results.csv")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _read_rows(self):
        with open(self.out_csv, "r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_creates_file_with_correct_header(self):
        write_header_if_needed(self.out_csv)
        self.assertTrue(os.path.exists(self.out_csv))
        with open(self.out_csv, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.assertEqual(list(reader.fieldnames), OUTPUT_COLUMNS)

    def test_does_not_overwrite_existing_nonempty_file(self):
        write_header_if_needed(self.out_csv)
        append_result(self.out_csv, _make_scan_result())
        write_header_if_needed(self.out_csv)  # second call
        self.assertEqual(len(self._read_rows()), 1)

    def test_append_writes_row(self):
        write_header_if_needed(self.out_csv)
        append_result(self.out_csv, _make_scan_result(repo="psf/requests", found=True))
        rows = self._read_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["repo"], "psf/requests")
        self.assertEqual(rows[0]["found"], "True")

    def test_append_multiple_rows_preserves_order(self):
        write_header_if_needed(self.out_csv)
        append_result(self.out_csv, _make_scan_result(repo="a/a"))
        append_result(self.out_csv, _make_scan_result(repo="b/b"))
        rows = self._read_rows()
        self.assertEqual([r["repo"] for r in rows], ["a/a", "b/b"])

    def test_all_output_columns_present_in_row(self):
        write_header_if_needed(self.out_csv)
        append_result(self.out_csv, _make_scan_result())
        rows = self._read_rows()
        for col in OUTPUT_COLUMNS:
            self.assertIn(col, rows[0])

    def test_creates_parent_directories(self):
        nested = os.path.join(self.tmpdir, "sub", "results.csv")
        write_header_if_needed(nested)
        self.assertTrue(os.path.exists(nested))


# ---------------------------------------------------------------------------
# write_shortlist
# ---------------------------------------------------------------------------

class TestWriteShortlist(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.results_csv = os.path.join(self.tmpdir, "results.csv")
        self.shortlist_csv = os.path.join(self.tmpdir, "shortlist.csv")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _seed_results(self, rows: list[tuple[str, bool]]) -> None:
        with open(self.results_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            for repo, found in rows:
                base = {col: "" for col in OUTPUT_COLUMNS}
                base["repo"] = repo
                base["found"] = str(found)
                writer.writerow(base)

    def _read_shortlist(self):
        with open(self.shortlist_csv, "r", newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def test_only_found_rows_appear_in_shortlist(self):
        self._seed_results([("a/b", True), ("c/d", False), ("e/f", True)])
        write_shortlist(self.results_csv, self.shortlist_csv)
        rows = self._read_shortlist()
        self.assertEqual(len(rows), 2)
        repos = {r["repo"] for r in rows}
        self.assertIn("a/b", repos)
        self.assertIn("e/f", repos)
        self.assertNotIn("c/d", repos)

    def test_shortlist_is_empty_when_nothing_found(self):
        self._seed_results([("a/b", False)])
        write_shortlist(self.results_csv, self.shortlist_csv)
        self.assertEqual(self._read_shortlist(), [])

    def test_shortlist_has_correct_header(self):
        self._seed_results([("a/b", True)])
        write_shortlist(self.results_csv, self.shortlist_csv)
        with open(self.shortlist_csv, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            self.assertEqual(list(reader.fieldnames), OUTPUT_COLUMNS)

    def test_creates_parent_directories(self):
        nested = os.path.join(self.tmpdir, "sub", "shortlist.csv")
        self._seed_results([("a/b", True)])
        write_shortlist(self.results_csv, nested)
        self.assertTrue(os.path.exists(nested))


# ---------------------------------------------------------------------------
# GitHubClient
# ---------------------------------------------------------------------------

class TestGitHubClient(unittest.TestCase):
    """
    Smoke tests for GitHubClient via the new TokenPool-backed API.

    Comprehensive tests live in tests/test_github_client.py.
    These tests verify backward-compatible behaviour from find_skills_md's
    perspective (single token, no token, retry semantics).
    """

    def _client(self, token=None):
        tokens = [token] if token else []
        return GitHubClient(pool=TokenPool(tokens))

    def test_token_added_to_request_header(self):
        client = self._client("ghp_test")
        resp = _make_http_response(200, {})
        captured = []

        def fake_request(method, url, **kwargs):
            captured.append(kwargs.get("headers", {}))
            return resp

        with mock.patch.object(client.session, "request", side_effect=fake_request):
            client.request_json("GET", "/rate_limit")

        self.assertTrue(any("ghp_test" in str(h) for h in captured))

    def test_no_token_means_no_auth_header(self):
        client = self._client(None)
        resp = _make_http_response(200, {})
        captured = []

        def fake_request(method, url, **kwargs):
            captured.append(kwargs.get("headers", {}))
            return resp

        with mock.patch.object(client.session, "request", side_effect=fake_request):
            client.request_json("GET", "/rate_limit")

        self.assertFalse(any("Authorization" in h for h in captured))

    def test_success_200_returns_json(self):
        client = self._client(None)
        resp = _make_http_response(200, {"name": "requests"})
        with mock.patch.object(client.session, "request", return_value=resp):
            status, data, err = client.request_json("GET", "/repos/psf/requests")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"name": "requests"})
        self.assertEqual(err, "")

    def test_404_does_not_retry(self):
        client = self._client(None)
        resp = _make_http_response(404, {"message": "Not Found"})
        with mock.patch.object(client.session, "request", return_value=resp) as m:
            status, _, _ = client.request_json("GET", "/repos/missing/repo", max_retries=3)
        self.assertEqual(status, 404)
        self.assertEqual(m.call_count, 1)

    def test_401_does_not_retry(self):
        client = self._client(None)
        resp = _make_http_response(401, {"message": "Requires authentication"})
        with mock.patch.object(client.session, "request", return_value=resp) as m:
            status, _, _ = client.request_json("GET", "/repos/private/repo", max_retries=3)
        self.assertEqual(status, 401)
        self.assertEqual(m.call_count, 1)

    def test_5xx_retries_until_success(self):
        client = self._client(None)
        err_resp = _make_http_response(503, {}, text="Service Unavailable")
        ok_resp = _make_http_response(200, {"ok": True})
        with mock.patch.object(
            client.session, "request", side_effect=[err_resp, ok_resp]
        ):
            with mock.patch("time.sleep"):
                status, data, _ = client.request_json("GET", "/repos/x/y", max_retries=2)
        self.assertEqual(status, 200)
        self.assertEqual(data, {"ok": True})

    def test_5xx_exhausted_retries_returns_error_status(self):
        client = self._client(None)
        err_resp = _make_http_response(500, {}, text="error")
        with mock.patch.object(client.session, "request", return_value=err_resp) as m:
            with mock.patch("time.sleep"):
                status, _, _ = client.request_json("GET", "/repos/x/y", max_retries=2)
        self.assertEqual(status, 500)
        self.assertEqual(m.call_count, 3)  # initial + 2 retries

    def test_network_error_retries_and_returns_zero(self):
        client = self._client(None)
        with mock.patch.object(
            client.session,
            "request",
            side_effect=requests.RequestException("connection refused"),
        ) as m:
            with mock.patch("time.sleep"):
                status, _, err = client.request_json("GET", "/repos/x/y", max_retries=2)
        self.assertEqual(status, 0)
        self.assertIn("network_error", err)
        self.assertEqual(m.call_count, 3)

    def test_rate_limit_403_retries_with_second_token(self):
        pool = TokenPool(["tok1", "tok2"])
        client = GitHubClient(pool=pool)
        rate_resp = _make_http_response(
            403,
            {"message": "API rate limit exceeded"},
            headers={
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 3600),
                "X-RateLimit-Limit": "5000",
            },
        )
        ok_resp = _make_http_response(200, {"ok": True})
        with mock.patch.object(
            client.session, "request", side_effect=[rate_resp, ok_resp]
        ):
            status, _, _ = client.request_json("GET", "/repos/x/y", max_retries=2)
        self.assertEqual(status, 200)


# ---------------------------------------------------------------------------
# try_contents_path
# ---------------------------------------------------------------------------

class TestTryContentsPath(unittest.TestCase):

    def _mock_gh(self, status: int, body: dict) -> GitHubClient:
        gh = mock.MagicMock(spec=GitHubClient)
        gh.request_json.return_value = (status, body, "")
        return gh

    def test_returns_true_when_file_found(self):
        file_body = {"type": "file", "path": "SKILL.md", "sha": "abc", "size": 100, "html_url": "http://x"}
        gh = self._mock_gh(200, file_body)
        ok, data, status, err = try_contents_path(gh, "owner/repo", "/SKILL.md", "main")
        self.assertTrue(ok)
        self.assertEqual(data["sha"], "abc")

    def test_returns_false_on_404(self):
        gh = self._mock_gh(404, {})
        gh.request_json.return_value = (404, {}, "Not Found")
        ok, data, status, err = try_contents_path(gh, "owner/repo", "/SKILL.md", "main")
        self.assertFalse(ok)
        self.assertEqual(status, 404)

    def test_returns_false_when_path_is_directory(self):
        gh = self._mock_gh(200, {"type": "dir"})
        ok, _, status, err = try_contents_path(gh, "owner/repo", "/SKILL.md", "main")
        self.assertFalse(ok)
        self.assertEqual(err, "path_is_not_file")

    def test_strips_leading_slash_from_path(self):
        gh = mock.MagicMock(spec=GitHubClient)
        gh.request_json.return_value = (404, {}, "")
        try_contents_path(gh, "owner/repo", "/SKILL.md", "main")
        called_path = gh.request_json.call_args[0][1]
        self.assertIn("SKILL.md", called_path)
        self.assertFalse(called_path.endswith("//SKILL.md"))


# ---------------------------------------------------------------------------
# try_code_search
# ---------------------------------------------------------------------------

class TestTryCodeSearch(unittest.TestCase):

    def test_returns_true_and_best_item_when_found(self):
        items = [
            {"path": "deep/nested/SKILL.md", "html_url": "http://a", "sha": "aaa"},
            {"path": "SKILL.md", "html_url": "http://b", "sha": "bbb"},
        ]
        gh = mock.MagicMock(spec=GitHubClient)
        gh.request_json.return_value = (200, {"items": items}, "")
        found, item, status, err = try_code_search(gh, "owner/repo", "SKILL.md")
        self.assertTrue(found)
        self.assertEqual(item["path"], "SKILL.md")  # shortest path wins

    def test_returns_false_when_no_items(self):
        gh = mock.MagicMock(spec=GitHubClient)
        gh.request_json.return_value = (200, {"items": []}, "")
        found, item, status, err = try_code_search(gh, "owner/repo", "SKILL.md")
        self.assertFalse(found)
        self.assertIsNone(item)

    def test_returns_false_on_non_200(self):
        gh = mock.MagicMock(spec=GitHubClient)
        gh.request_json.return_value = (403, {}, "rate limited")
        found, item, status, err = try_code_search(gh, "owner/repo", "SKILL.md")
        self.assertFalse(found)
        self.assertEqual(status, 403)

    def test_tie_broken_lexicographically(self):
        items = [
            {"path": "b/SKILL.md", "html_url": "", "sha": ""},
            {"path": "a/SKILL.md", "html_url": "", "sha": ""},
        ]
        gh = mock.MagicMock(spec=GitHubClient)
        gh.request_json.return_value = (200, {"items": items}, "")
        _, item, _, _ = try_code_search(gh, "owner/repo", "SKILL.md")
        self.assertEqual(item["path"], "a/SKILL.md")


# ---------------------------------------------------------------------------
# scan_one_repo
# ---------------------------------------------------------------------------

class TestScanOneRepo(unittest.TestCase):

    def _gh(self):
        return GitHubClient(pool=TokenPool([]))

    def _src(self, repo: str = "owner/repo") -> RepoSource:
        return RepoSource(repo=repo, source_csv="test.csv")

    def _file_data(self, path: str = "SKILL.md") -> dict:
        return {
            "type": "file",
            "path": path,
            "sha": "abc123",
            "size": 512,
            "html_url": f"https://github.com/owner/repo/blob/main/{path}",
        }

    def test_found_via_contents_api(self):
        with mock.patch("A_extract_skill_repos.get_repo_metadata", return_value=(_make_meta(), 200, "")), \
             mock.patch("A_extract_skill_repos.try_contents_path", return_value=(True, self._file_data(), 200, "")):
            result = scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=False, min_stars=0, allow_forks=True, allow_archived=True,
            )
        self.assertTrue(result.found)
        self.assertEqual(result.scan_method, "contents_api")
        self.assertEqual(result.match_sha, "abc123")
        self.assertEqual(result.match_size_bytes, "512")
        self.assertEqual(result.match_path, "/SKILL.md")
        self.assertEqual(result.error_type, "none")

    def test_not_found_contents_api_returns_found_false(self):
        with mock.patch("A_extract_skill_repos.get_repo_metadata", return_value=(_make_meta(), 200, "")), \
             mock.patch("A_extract_skill_repos.try_contents_path", return_value=(False, {}, 404, "")):
            result = scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=False, min_stars=0, allow_forks=True, allow_archived=True,
            )
        self.assertFalse(result.found)
        self.assertEqual(result.error_type, "none")

    def test_repo_metadata_404_sets_invalid_repo_error(self):
        with mock.patch("A_extract_skill_repos.get_repo_metadata", return_value=(None, 404, "Not Found")):
            result = scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=False, min_stars=0, allow_forks=True, allow_archived=True,
            )
        self.assertFalse(result.found)
        self.assertEqual(result.error_type, "invalid_repo")

    def test_filtered_by_min_stars(self):
        with mock.patch("A_extract_skill_repos.get_repo_metadata", return_value=(_make_meta(stars=3), 200, "")): 
            result = scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=False, min_stars=10, allow_forks=True, allow_archived=True,
            )
        self.assertFalse(result.found)
        self.assertEqual(result.error_type, "filtered")
        self.assertIn("stars", result.error_message)

    def test_filtered_fork(self):
        with mock.patch("A_extract_skill_repos.get_repo_metadata", return_value=(_make_meta(fork=True), 200, "")):
            result = scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=False, min_stars=0, allow_forks=False, allow_archived=True,
            )
        self.assertFalse(result.found)
        self.assertEqual(result.error_type, "filtered")

    def test_filtered_archived(self):
        with mock.patch("A_extract_skill_repos.get_repo_metadata", return_value=(_make_meta(archived=True), 200, "")):
            result = scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=False, min_stars=0, allow_forks=True, allow_archived=False,
            )
        self.assertFalse(result.found)
        self.assertEqual(result.error_type, "filtered")

    def test_code_search_fallback_finds_file_in_subdir(self):
        search_item = {
            "path": "docs/SKILL.md",
            "html_url": "https://github.com/owner/repo/blob/main/docs/SKILL.md",
            "sha": "def456",
        }
        with mock.patch("A_extract_skill_repos.get_repo_metadata", return_value=(_make_meta(), 200, "")), \
             mock.patch("A_extract_skill_repos.try_contents_path", return_value=(False, {}, 404, "")), \
             mock.patch("A_extract_skill_repos.try_code_search", return_value=(True, search_item, 200, "")):
            result = scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=True, min_stars=0, allow_forks=True, allow_archived=True,
            )
        self.assertTrue(result.found)
        self.assertEqual(result.scan_method, "code_search")
        self.assertEqual(result.match_path, "/docs/SKILL.md")
        self.assertEqual(result.match_sha, "def456")

    def test_code_search_not_called_when_disabled(self):
        with mock.patch("A_extract_skill_repos.get_repo_metadata", return_value=(_make_meta(), 200, "")), \
             mock.patch("A_extract_skill_repos.try_contents_path", return_value=(False, {}, 404, "")), \
             mock.patch("A_extract_skill_repos.try_code_search") as mock_search:
            scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=False, min_stars=0, allow_forks=True, allow_archived=True,
            )
        mock_search.assert_not_called()

    def test_auth_error_on_contents_stops_scan_early(self):
        """401 from the contents API is a permanent auth failure; stops immediately."""
        with mock.patch("A_extract_skill_repos.get_repo_metadata", return_value=(_make_meta(), 200, "")), \
             mock.patch("A_extract_skill_repos.try_contents_path", return_value=(False, {}, 401, "Unauthorized")), \
             mock.patch("A_extract_skill_repos.try_code_search") as mock_search:
            result = scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=True, min_stars=0, allow_forks=True, allow_archived=True,
            )
        self.assertFalse(result.found)
        self.assertEqual(result.error_type, "auth")
        mock_search.assert_not_called()

    def test_rate_limit_on_contents_falls_through_to_code_search(self):
        """403 from the contents API is not an early stop; the scan continues to code search.

        In production, request_json retries 403 indefinitely until the rate limit
        resets — so scan_one_repo never sees 403. In the rare case it does (e.g.
        an unusual 403 not caused by rate limits), the scan continues rather than
        abandoning the repository.
        """
        with mock.patch("A_extract_skill_repos.get_repo_metadata", return_value=(_make_meta(), 200, "")), \
             mock.patch("A_extract_skill_repos.try_contents_path", return_value=(False, {}, 403, "rate limited")), \
             mock.patch("A_extract_skill_repos.try_code_search", return_value=(False, None, 200, "")) as mock_search:
            result = scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=True, min_stars=0, allow_forks=True, allow_archived=True,
            )
        self.assertFalse(result.found)
        self.assertEqual(result.error_type, "none")   # clean not-found, no hard error
        mock_search.assert_called_once()               # code search was attempted

    def test_metadata_populated_from_repo_meta(self):
        with mock.patch("A_extract_skill_repos.get_repo_metadata",
                        return_value=(_make_meta(branch="develop", stars=99, fork=True, archived=False), 200, "")), \
             mock.patch("A_extract_skill_repos.try_contents_path", return_value=(False, {}, 404, "")):
            result = scan_one_repo(
                self._gh(), self._src(), "SKILL.md", ["/SKILL.md"],
                enable_code_search=False, min_stars=0, allow_forks=True, allow_archived=True,
            )
        self.assertEqual(result.default_branch, "develop")
        self.assertEqual(result.ref_scanned, "develop")
        self.assertEqual(result.stars, "99")
        self.assertEqual(result.fork, "true")
        self.assertEqual(result.archived, "false")


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------

class TestSetupLogging(unittest.TestCase):

    def test_does_not_raise(self):
        setup_logging("INFO")

    def test_debug_level(self):
        import logging as _logging
        setup_logging("DEBUG")
        self.assertEqual(_logging.getLogger().level, _logging.DEBUG)

    def test_unknown_level_falls_back_to_info(self):
        import logging as _logging
        setup_logging("NOTAREAL")
        # getattr falls back to INFO (numeric 20)
        self.assertEqual(_logging.getLogger().level, _logging.INFO)


# ---------------------------------------------------------------------------
# check_rate_limit
# ---------------------------------------------------------------------------

class TestCheckRateLimit(unittest.TestCase):

    def _make_resources(self, core_remaining=4999, core_limit=5000,
                        search_remaining=29, search_limit=30,
                        reset_epoch=9_999_999_999):
        return {
            "resources": {
                "core": {"remaining": core_remaining, "limit": core_limit, "reset": reset_epoch},
                "search": {"remaining": search_remaining, "limit": search_limit, "reset": reset_epoch},
            }
        }

    def _mock_gh(self, token_count: int = 1):
        """Return a GitHubClient with a mocked pool for check_rate_limit tests."""
        pool = mock.MagicMock(spec=TokenPool)
        pool.stats.return_value = {
            "token_count": token_count,
            "total_remaining": 4999 * token_count,
            "total_requests": 0,
            "tokens": [],
        }
        gh = GitHubClient(pool=pool)
        # Stub out the HTTP session so no real network calls are made.
        gh.request_json = mock.MagicMock()
        return gh

    def test_returns_resources_dict_on_success(self):
        gh = self._mock_gh()
        gh.request_json.return_value = (200, self._make_resources(), "")
        result = check_rate_limit(gh)
        self.assertIn("core", result)
        self.assertIn("search", result)

    def test_logs_remaining_counts(self):
        gh = self._mock_gh()
        gh.request_json.return_value = (200, self._make_resources(core_remaining=1234), "")
        with self.assertLogs("A_extract_skill_repos", level="INFO") as cm:
            check_rate_limit(gh)
        self.assertTrue(any("1234" in line for line in cm.output))

    def test_returns_empty_dict_on_non_200(self):
        gh = self._mock_gh()
        gh.request_json.return_value = (403, {}, "Forbidden")
        with self.assertLogs("A_extract_skill_repos", level="WARNING"):
            result = check_rate_limit(gh)
        self.assertEqual(result, {})

    def test_logs_warning_on_non_200(self):
        gh = self._mock_gh()
        gh.request_json.return_value = (403, {}, "Forbidden")
        with self.assertLogs("A_extract_skill_repos", level="WARNING") as cm:
            check_rate_limit(gh)
        self.assertTrue(any("403" in line for line in cm.output))

    def test_logs_pool_stats_for_multiple_tokens(self):
        gh = self._mock_gh(token_count=3)
        gh.request_json.return_value = (200, self._make_resources(), "")
        with self.assertLogs("A_extract_skill_repos", level="INFO") as cm:
            check_rate_limit(gh)
        self.assertTrue(any("3" in line and "token" in line.lower() for line in cm.output))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
