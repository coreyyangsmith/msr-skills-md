# Data Collection

This document details how the repository collection, `SKILL.md` discovery, and raw skill-artifact download pipeline was run. It complements `README.md` by focusing on GitHub retrieval, REST API usage, request counts, script entry points, command examples, and the intermediate files that connect each stage.

The data collection pipeline is read-only. It does not clone full repositories, open issues, write to upstream projects, or mutate any remote GitHub state.

---

## Overview

The collection process has four core stages:

```text
Stage 1: Repository population
  src/search_github_repos.py
  data/seart_csvs/github_search_results.csv

Stage 2: SKILL.md scan
  src/extract_skill_repos_tree.py
  outputs/skill_md_scan_results.csv
  outputs/skill_md_scan_results_found.csv

Stage 2.5: Active-repository filtering
  utils/filter_active_repos.py
  data/skill_only_scan/skill_repositories.csv

Stage 3: Skill artifact extraction
  src/generate_dataset.py
  outputs/full_skills_instances.csv
  outputs/raw_data/<Language>/<owner>__<repo>/
```

Optional enrichment scripts add contributor counts, repository metadata, READMEs, and legacy ACF backfills:

- `src/enrich_scan_contributors.py`
- `src/fetch_repo_metadata_readmes.py`
- `src/enrich_extended_acf_columns.py`

Shared GitHub API behavior lives in:

- `src/github_client/client.py`
- `src/github_client/token_pool.py`
- `src/github_client/__init__.py`

Filtering behavior lives in:

- `src/filters.py`
- `blacklist.txt`
- `relevance_terms.txt`

---

## Authentication And Rate Limits

GitHub personal access tokens are strongly recommended. The scripts support one or more tokens and rotate across them automatically.

Token resolution order:

1. `--github-tokens ghp_1,ghp_2`
2. `--github-token ghp_1`
3. `GH_TOKENS` from the environment or `.env`
4. `GH_TOKEN`
5. `GITHUB_TOKEN`
6. Unauthenticated requests

Example:

```sh
export GH_TOKENS=ghp_token1,ghp_token2,ghp_token3   # macOS/Linux
$env:GH_TOKENS = "ghp_token1,ghp_token2,ghp_token3" # PowerShell
```

`TokenPool` selects the token with the most remaining quota, updates quota from `X-RateLimit-*` response headers, rotates away from exhausted tokens, and sleeps until reset if all tokens are exhausted.

Relevant GitHub REST rate limits:

| API resource | Endpoint family | Authenticated limit |
|---|---|---:|
| Repository search | `GET /search/repositories` | 30 requests/min/token |
| Code search | `GET /search/code` | 10 requests/min/token |
| Core REST API | `GET /repos/...`, `GET /git/...`, `GET /contents/...` | 5,000 requests/hour/token |

The repository and code search limits are separate from the core REST API limit.

---

## Stage 1: Build The Repository Population

Script:

- `src/search_github_repos.py`

Primary output:

- `data/seart_csvs/github_search_results.csv`

Additional outputs:

- `data/seart_csvs/github_search_results_<language>_<license>.csv`

Purpose:

Stage 1 collects the initial population of GitHub repositories. It can be skipped if using externally generated SEART CSV exports, but the rest of the pipeline expects SEART-compatible columns.

Default repository criteria:

- At least 10 stars
- License in `mit`, `apache-2.0`, `bsd-3-clause`, `bsd-2-clause`
- Primary language in `TypeScript`, `Python`, `C#`, `Go`, `C++`, `JavaScript`, `Java`, `C`, `PHP`, `Rust`
- Pushed since `2025-10-16`
- Pushed no later than `--end-date`, which defaults to the date at script startup

Default command:

```sh
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --resume
```

More explicit reproducibility command:

```sh
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --min-stars 10 \
  --pushed-since 2025-10-16 \
  --end-date 2026-06-06 \
  --languages TypeScript Python C# Go C++ JavaScript Java C PHP Rust \
  --licenses mit apache-2.0 bsd-3-clause bsd-2-clause \
  --resume
```

Useful variants:

```sh
# Search only; skip slower per-repo enrichment.
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --skip-enrich

# Fill missing enrichment columns in an existing Stage 1 CSV.
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --enrich-only \
  --enrich-concurrency 8

# Collect a smaller test population.
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results_python_mit.csv \
  --languages Python \
  --licenses mit \
  --min-stars 25 \
  --pushed-since 2025-10-16 \
  --end-date 2026-06-06
```

### Stage 1 REST Calls

Repository discovery uses:

```text
GET /search/repositories
```

Request parameters:

- `q`: GitHub repository search query
- `per_page=100`
- `page=1..10`

A default query is built from:

```text
stars:<range> language:"<language>" license:<license> pushed:<start>..<end>
```

The default run has 10 languages and 4 licenses, or 40 language/license combinations. Each combination first probes page 1. If GitHub reports fewer than 1,000 results, the script paginates directly. If the result count reaches the 1,000-result cap, the script subdivides the query:

1. Full pushed date range and minimum star threshold
2. Static star brackets
3. Weekly pushed windows
4. Daily windows
5. 12-hour windows
6. 6-hour windows
7. Star-range bisection inside a 6-hour window

This subdivision exists because GitHub Search returns at most 1,000 results per query, even when `total_count` is larger.

### Stage 1 Request Count

Minimum repository-search requests:

```text
languages * licenses
```

For the default configuration:

```text
10 languages * 4 licenses = 40 first-page probe requests
```

Upper-bound direct pagination cost per combination:

```text
min(ceil(total_count / 100), 10) requests
```

Approximate default direct-pagination upper bound:

```text
40 combinations * 10 pages = 400 repository-search requests
```

Actual request counts can exceed 400 when large combinations trigger subdivision, because each split window also needs a first-page probe. The script logs request counts and rate-limit state during execution.

### Stage 1 Enrichment REST Calls

After repository search, enrichment runs by default unless `--skip-enrich` is passed. For each row with missing enrichment fields, the script may call:

```text
GET /repos/{owner}/{repo}/contributors?per_page=1&anon=1
GET /repos/{owner}/{repo}/commits?per_page=1
GET /repos/{owner}/{repo}/branches?per_page=1
GET /repos/{owner}/{repo}/releases?per_page=1
GET /repos/{owner}/{repo}/languages
```

Approximate enrichment request count:

```text
repos_needing_enrichment * up to 5 core REST calls
```

Counts for paginated endpoints are inferred from the `Link` header when possible.

### Stage 1 Output Schema

The output CSV uses the SEART-compatible column set declared in `search_github_repos.py`:

- `id`
- `name`
- `isFork`
- `commits`
- `branches`
- `releases`
- `forks`
- `mainLanguage`
- `defaultBranch`
- `license`
- `homepage`
- `watchers`
- `stargazers`
- `contributors`
- `size`
- `createdAt`
- `pushedAt`
- `updatedAt`
- `totalIssues`
- `openIssues`
- `totalPullRequests`
- `openPullRequests`
- `blankLines`
- `codeLines`
- `commentLines`
- `metrics`
- `lastCommit`
- `lastCommitSHA`
- `hasWiki`
- `isArchived`
- `isDisabled`
- `isLocked`
- `languages`
- `labels`
- `topics`

Downstream scripts primarily use `name`, `mainLanguage`, `defaultBranch`, `stargazers`, `isFork`, and `isArchived`, while retaining all original columns.

---

## Alternative Stage 1 Input: SEART CSV Exports

Instead of querying GitHub directly, place SEART CSV files under:

```text
data/seart_csvs/
```

Stage 2 recursively reads every `.csv` file under that directory. Repository identifiers are auto-detected from:

- `full_name`
- `repo`
- `repository`
- `name`
- `owner` + `name`
- `org` + `repo_name`
- `repo_owner` + `repo_name`
- `html_url`
- `url`

Repository strings are normalized to `owner/repo`, `.git` suffixes are removed, GitHub URLs are parsed, and duplicate repositories across CSVs are collapsed.

---

## Stage 2: Scan Repositories For SKILL.md

Script:

- `src/extract_skill_repos_tree.py` (recommended)
- `src/extract_skill_repos.py` (legacy Code Search alternative)

Primary outputs:

- `outputs/skill_md_scan_results.csv`
- `outputs/skill_md_scan_results_found.csv`
- `outputs/skill_md_scan_results_not_found.csv`
- `outputs/skill_md_scan_results_errors.csv`
- `outputs/skill_md_scan_results_filtered.csv`

Default command:

```sh
uv run python src/extract_skill_repos_tree.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results.csv \
  --resume \
  --concurrency 4 \
  --cache-dir outputs/cache/tree_scan \
  --fallback walk-tree
```

Useful variants:

```sh
# Smoke-test the scan on a limited number of repositories.
uv run python src/extract_skill_repos_tree.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results_smoke.csv \
  --max-repos 250 \
  --resume \
  --log-level DEBUG

# Search for a different exact filename.
uv run python src/extract_skill_repos_tree.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/agents_md_scan_results.csv \
  --match-name AGENTS.md

# Disable cache reads and writes.
uv run python src/extract_skill_repos_tree.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results_uncached.csv \
  --cache-mode off

# Legacy Code Search path, retained for method comparison.
uv run python src/extract_skill_repos.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results_code_search.csv \
  --resume
```

Stage 2 scans the full source population. It does not apply star, fork, archived, or name filters. The only pre-scan exclusion is `--blacklist`, which skips listed repositories before result rows are written.

### Stage 2 REST Calls

For every repository that is not already scanned, not blacklisted, and not satisfied from cache, the recommended tree-first scanner calls:

```text
GET /repos/{owner}/{repo}/commits/{default_branch_or_HEAD}
GET /repos/{owner}/{repo}/git/trees/{commit_sha}?recursive=1
```

The recursive tree response contains blob paths, blob SHAs, and sizes. Stage 2 therefore detects all of the following locally without downloading blobs:

- `SKILL.md`
- `CLAUDE.md`
- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.cursorrules.md`
- `.instructions.md`
- `GEMINI.md`
- `README`
- `CONTRIBUTING`
- `SECURITY`
- `CODE_OF_CONDUCT`

If the recursive response has `truncated=true`, GitHub may have omitted paths. With the default `--fallback walk-tree`, the scanner switches to non-recursive tree walking:

```text
GET /repos/{owner}/{repo}/git/trees/{commit_sha}
GET /repos/{owner}/{repo}/git/trees/{subtree_sha}
```

Passing `--fallback none` records a truncated recursive response as an error row (`error_message=tree_truncated`) rather than returning a false not-found result. The `acf_ref` for found repositories is the pinned commit SHA when available, otherwise the default branch or `HEAD`.

The legacy `src/extract_skill_repos.py` path calls:

```text
GET /repos/{owner}/{repo}/community/profile
GET /search/code?q=repo:{owner}/{repo} filename:{match_name}&per_page=100
GET /repos/{owner}/{repo}/commits/{default_branch_or_HEAD}
GET /repos/{owner}/{repo}/contents/{matched_skill_path}?ref={acf_ref}
GET /repos/{owner}/{repo}/contents/{acf_path}?ref={acf_ref}
```

### Stage 2 Request Count

Let:

- `N` = repositories scanned
- `F` = repositories where `SKILL.md` is found
- `C` = repositories satisfied from tree cache
- `T` = repositories where the recursive tree was truncated
- `S_t` = non-recursive subtree calls needed for truncated repository `t`

Recommended tree-first path:

```text
Code search requests = 0
Core REST requests = (N - C) commit-resolution calls
                   + (N - C) recursive tree calls
                   + sum(S_t for truncated repos using --fallback walk-tree)
```

Legacy Code Search path:

```text
Code search requests = N
Core REST requests = N community-profile calls + (F * 8)
```

The tree-first path moves Stage 2 off GitHub Code Search, whose `GET /search/code` endpoint is limited to 10 requests/minute/token and is prone to secondary endpoint pressure on large runs.

### Stage 2 Tree Cache

`src/extract_skill_repos_tree.py` stores cached tree responses under `--cache-dir` when `--cache-mode read-write` is enabled. Cache keys include:

- `repo`
- resolved commit SHA or scan ref
- tree endpoint mode (`tree_recursive` or `tree_walk`)

Each cache file stores tree entries plus metadata such as `repo`, `ref`, response `etag` when supplied, `fetched_at_utc`, `truncated`, and `scan_method`. Use `--cache-mode read-only` to require existing cache entries and avoid network tree calls, or `--cache-mode off` to ignore cache entirely.

The cache is intentionally keyed by commit SHA/ref rather than repository name alone. If a repository advances to a new commit, the scanner fetches and caches a separate tree instead of reusing stale path metadata.

### Stage 2 Output Columns

Stage 2 writes one row per repository to the main CSV, then splits rows into category CSVs. Important columns include:

- `repo`
- `source_csv`
- `found`
- `match_name`
- `match_path`
- `default_branch`
- `seart_default_branch`
- `commit_sha`
- `acf_ref`
- `match_url`
- `match_sha`
- `match_size_bytes`
- `scan_method`
- `http_status`
- `error_type`
- `error_message`
- `acf_error_type`
- `acf_error_message`
- `scanned_at_utc`
- `stars`
- `fork`
- `archived`
- `has_README`
- `has_CONTRIBUTING`
- `has_SECURITY`
- `has_CODE_OF_CONDUCT`
- `has_CLAUDE`
- `has_AGENTS`
- `has_COPILOT`
- `has_CURSORRULES_MD`
- `has_INSTRUCTIONS_MD`
- `has_GEMINI`

The original SEART columns are appended after the scanner columns.

### Stage 2 Category Files

The split CSV paths are derived from `--out-csv`:

- `*_found.csv`
- `*_not_found.csv`
- `*_errors.csv`
- `*_filtered.csv`

In current code, `_filtered.csv` is reserved for rows with `error_type=filtered`; it is typically empty because blacklisted repositories are skipped before scan rows are emitted.

---

## Stage 2.5: Filter Active, Non-Fork Repositories

Script:

- `utils/filter_active_repos.py`

Command:

```sh
uv run python utils/filter_active_repos.py \
  outputs/skill_md_scan_results_found.csv \
  -o outputs/skill_md_scan_results_found_filtered.csv
```

This step keeps only rows where:

- `isArchived` is false
- `isFork` is false

The script prints:

- total input rows
- rows removed by `isArchived=True`
- rows removed by `isFork=True`
- kept rows
- filtered repository names

The filtered output is commonly copied or used as:

```text
data/skill_only_scan/skill_repositories.csv
```

Request count:

```text
0 GitHub API requests
```

This is a local CSV preprocessing step.

---

## Stage 3: Extract Full Skill Artifacts

Script:

- `src/generate_dataset.py`

Primary outputs:

- `outputs/full_skills_instances.csv`
- `outputs/raw_data/<Language>/<owner>__<repo>/`
- `outputs/processing_failures.tsv`
- `outputs/name_filtered_repos.tsv`

Committed/archived dataset copy:

- `data/skill_files/full_skills.csv`
- Zenodo `raw_data/` archive

Recommended command:

```sh
uv run python src/generate_dataset.py \
  --found-csv outputs/skill_md_scan_results_found_filtered.csv \
  --out-csv outputs/full_skills_instances.csv \
  --raw-data-dir outputs/raw_data \
  --resume \
  --concurrency 1
```

Equivalent command using the repository shortlist:

```sh
uv run python src/generate_dataset.py \
  --found-csv data/skill_only_scan/skill_repositories.csv \
  --out-csv outputs/full_skills_instances.csv \
  --raw-data-dir outputs/raw_data \
  --resume \
  --concurrency 1
```

Useful variants:

```sh
# Disable repo-name relevance filtering.
uv run python src/generate_dataset.py \
  --found-csv data/skill_only_scan/skill_repositories.csv \
  --out-csv outputs/full_skills_instances_no_name_filter.csv \
  --raw-data-dir outputs/raw_data_no_name_filter \
  --no-name-filter

# Add additional repo-name exclusion terms.
uv run python src/generate_dataset.py \
  --found-csv data/skill_only_scan/skill_repositories.csv \
  --out-csv outputs/full_skills_instances.csv \
  --raw-data-dir outputs/raw_data \
  --name-filter-words demo,template,starter
```

### Stage 3 Filtering

Before API retrieval, Stage 3 applies:

- `blacklist.txt`
- `relevance_terms.txt`
- optional `--name-filter-words`

The name filter is on by default. Use `--no-name-filter` to disable it. Filtered repositories are logged to:

```text
outputs/name_filtered_repos.tsv
outputs/name_filtered_repos_counts.json
```

### Stage 3 REST Calls

For each repository to process, Stage 3 fetches a recursive git tree:

```text
GET /repos/{owner}/{repo}/git/trees/{commit_sha_or_branch}?recursive=1
```

Then, for each file to download, it fetches the blob:

```text
GET /repos/{owner}/{repo}/git/blobs/{blob_sha}
```

The tree endpoint provides all blob paths and SHAs. Blob requests are only made for files that belong to a detected skill folder and for ACF files copied into the local `ACF/` directory.

### Stage 3 Request Count

Let:

- `R` = repositories processed after blacklist/name filtering
- `B` = total blobs downloaded across all skill folders and ACF files

Approximate core REST requests:

```text
R recursive tree requests + B blob requests
```

If a repository already has successful `metadata.json` and `--resume` is enabled, it may be skipped without API calls. If `metadata.json` records `skill_count: 0`, it is not treated as a successful terminal state; the repository is retried.

### Stage 3 Local Layout

Downloaded data is written as:

```text
outputs/raw_data/<Language>/<owner>__<repo>/<skill-folder>/SKILL.md
outputs/raw_data/<Language>/<owner>__<repo>/<skill-folder>/references/...
outputs/raw_data/<Language>/<owner>__<repo>/<skill-folder>/assets/...
outputs/raw_data/<Language>/<owner>__<repo>/<skill-folder>/scripts/...
outputs/raw_data/<Language>/<owner>__<repo>/ACF/<acf-file>
outputs/raw_data/<Language>/<owner>__<repo>/metadata.json
```

For root-level `SKILL.md` files, the local folder is:

```text
outputs/raw_data/<Language>/<owner>__<repo>/root/
```

Path components are sanitized for Windows filesystem compatibility.

### Stage 3 Output Rows

`outputs/full_skills_instances.csv` has one row per `SKILL.md` instance, not one row per repository. Important columns include:

- `repo`
- `default_branch`
- `stars`
- `fork`
- `archived`
- `html_url`
- `skill_path`
- `skill_parent_folder`
- `total_files`
- `has_references`
- `references_file_count`
- `has_assets`
- `assets_file_count`
- `has_scripts`
- `scripts_file_count`
- `has_other`
- `other_file_count`
- `scanned_at_utc`
- maintainer-readiness flags
- ACF flags
- original SEART columns

Failures that produce no dataset rows are recorded in:

```text
outputs/processing_failures.tsv
```

Failure categories include:

- `tree_fetch_failed`
- `tree_truncated`
- `zero_skills_found`
- `exception`

---

## Optional Enrichment: Contributor Counts

Script:

- `src/enrich_scan_contributors.py`

Command:

```sh
uv run python src/enrich_scan_contributors.py \
  --scan-csv outputs/skill_md_scan_results.csv \
  --out-csv outputs/skill_md_scan_results_with_contributors.csv \
  --resume \
  --concurrency 1
```

REST call:

```text
GET /repos/{owner}/{repo}/contributors?per_page=1&anon=1
```

Request count:

```text
repositories_missing_contributor_count
```

The script parses the pagination `Link` header to infer the count and writes checkpoints every 100 completed repositories.

---

## Optional Enrichment: Repository Metadata And READMEs

Script:

- `src/fetch_repo_metadata_readmes.py`

Default command:

```sh
uv run python src/fetch_repo_metadata_readmes.py \
  --input-csv outputs/full_skills_instances.csv \
  --out-csv outputs/repo_metadata_readmes/repo_metadata.csv \
  --readme-dir outputs/repo_metadata_readmes/readmes \
  --resume
```

By default, this script keeps only rows where `mainLanguage` is Python. To collect all languages:

```sh
uv run python src/fetch_repo_metadata_readmes.py \
  --input-csv outputs/full_skills_instances.csv \
  --out-csv outputs/repo_metadata_readmes/repo_metadata.csv \
  --readme-dir outputs/repo_metadata_readmes/readmes \
  --all-languages \
  --resume
```

REST calls per repository:

```text
GET /repos/{owner}/{repo}
GET /repos/{owner}/{repo}/readme
```

Request count:

```text
repositories_selected * 2 core REST calls
```

Outputs:

- `outputs/repo_metadata_readmes/repo_metadata.csv`
- `outputs/repo_metadata_readmes/readmes/<owner>__<repo>.<ext>`

---

## Optional Enrichment: Extended ACF Backfill

Script:

- `src/enrich_extended_acf_columns.py`

Command:

```sh
uv run python src/enrich_extended_acf_columns.py \
  --input-known data/skill_only_scan/skill_repositories.csv \
  --merge-into outputs/skill_md_scan_results_with_contributors.csv \
  --out-skill-only outputs/skill_md_scan_results_skill_only_new_acfs.csv \
  --out-merged outputs/skill_md_scan_results_with_contributors_extended.csv
```

This is mainly a legacy backfill. Current Stage 2 already checks:

- `CLAUDE.md`
- `AGENTS.md`
- `.github/copilot-instructions.md`
- `.cursorrules.md`
- `.instructions.md`
- `GEMINI.md`

The backfill checks only:

```text
GET /repos/{owner}/{repo}/contents/.cursorrules.md?ref={ref}
GET /repos/{owner}/{repo}/contents/.instructions.md?ref={ref}
GET /repos/{owner}/{repo}/contents/GEMINI.md?ref={ref}
```

Request count:

```text
found_repositories * 3 core REST calls
```

---

## End-To-End Command Sequence

The following commands recreate the main collection path with local outputs:

```sh
# 1. Build the GitHub repository population.
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --resume

# 2. Scan the population for SKILL.md.
uv run python src/extract_skill_repos_tree.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results.csv \
  --resume \
  --concurrency 4 \
  --cache-dir outputs/cache/tree_scan \
  --fallback walk-tree

# 3. Keep active, non-fork repositories from the found set.
uv run python utils/filter_active_repos.py \
  outputs/skill_md_scan_results_found.csv \
  -o data/skill_only_scan/skill_repositories.csv

# 4. Download SKILL.md parent folders and write the per-instance dataset.
uv run python src/generate_dataset.py \
  --found-csv data/skill_only_scan/skill_repositories.csv \
  --out-csv outputs/full_skills_instances.csv \
  --raw-data-dir outputs/raw_data \
  --resume \
  --concurrency 1
```

Legacy Stage 2 alternative:

```sh
uv run python src/extract_skill_repos.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results_code_search.csv \
  --resume \
  --concurrency 4
```

Optional enrichment:

```sh
# Contributor counts for RQ1 contributor-related plots.
uv run python src/enrich_scan_contributors.py \
  --scan-csv outputs/skill_md_scan_results.csv \
  --out-csv outputs/skill_md_scan_results_with_contributors.csv \
  --resume

# Metadata and README corpus.
uv run python src/fetch_repo_metadata_readmes.py \
  --input-csv outputs/full_skills_instances.csv \
  --out-csv outputs/repo_metadata_readmes/repo_metadata.csv \
  --readme-dir outputs/repo_metadata_readmes/readmes \
  --resume
```

---

## Request Count Summary

Use these formulas to estimate API usage before running a collection job.

| Stage | Search requests | Core REST requests |
|---|---:|---:|
| Stage 1 search | Up to `language_license_combinations * 10`, plus subdivision probes | 0 |
| Stage 1 enrichment | 0 | Up to `repos_needing_enrichment * 5` |
| Stage 2 scan, tree-first | 0 | `(repos_scanned - cache_hits) * 2 + fallback_subtree_calls` |
| Stage 2 scan, legacy Code Search | `repos_scanned` | `repos_scanned + found_repos * 8` |
| Stage 2.5 filter | 0 | 0 |
| Stage 3 extraction | 0 | `repos_processed + blobs_downloaded` |
| Contributor enrichment | 0 | `repos_missing_contributors` |
| Metadata + READMEs | 0 | `repos_selected * 2` |
| Extended ACF backfill | 0 | `found_repos * 3` |

For the default Stage 1 query grid:

```text
10 languages * 4 licenses = 40 combinations
40 combinations * up to 10 pages = roughly 400 repository-search page requests
```

For Stage 2:

```text
Tree-first:
N repositories scanned = 0 code-search requests
N repositories scanned minus cache hits = commit-resolution calls + recursive tree calls
T truncated repositories = additional non-recursive subtree calls when --fallback walk-tree is enabled

Legacy Code Search:
N repositories scanned = N code-search requests
N repositories scanned = N community-profile core requests
F found repositories = F * 8 additional core requests
```

For Stage 3:

```text
R processed repositories = R recursive tree requests
B downloaded blobs = B blob requests
```

---

## Reproducibility Notes

The collection process records or preserves the following reproducibility anchors:

- Stage 1 uses `--pushed-since` and `--end-date` to define a closed repository population window.
- Stage 1 writes per-language/license CSVs in addition to the combined CSV.
- Stage 2 records `commit_sha` for found repositories.
- Stage 2 records `acf_ref`, usually the pinned commit SHA.
- Stage 3 prefers `commit_sha` over branch names when retrieving repository trees.
- Stage 3 writes `metadata.json` under each downloaded repository folder.
- All long-running collection stages support `--resume`.
- Stage 2 validates output schema before resuming to avoid appending incompatible rows.
- Stage 3 retries zero-skill metadata rather than treating it as a successful terminal state.

For archival replication, the repository includes:

- `data/seart_csvs/`
- `data/skill_only_scan/skill_repositories.csv`
- `data/skill_files/full_skills.csv`

The full raw skill-folder tree is available in the Zenodo archive linked from `README.md`.

---

## File Reference Index

Core collection scripts:

- `src/search_github_repos.py`
- `src/extract_skill_repos_tree.py`
- `src/extract_skill_repos.py`
- `utils/filter_active_repos.py`
- `src/generate_dataset.py`

Optional enrichment scripts:

- `src/enrich_scan_contributors.py`
- `src/fetch_repo_metadata_readmes.py`
- `src/enrich_extended_acf_columns.py`

Shared support modules:

- `src/github_client/client.py`
- `src/github_client/token_pool.py`
- `src/github_client/__init__.py`
- `src/filters.py`

Primary data outputs:

- `data/seart_csvs/github_search_results.csv`
- `outputs/skill_md_scan_results.csv`
- `outputs/skill_md_scan_results_found.csv`
- `data/skill_only_scan/skill_repositories.csv`
- `outputs/full_skills_instances.csv`
- `data/skill_files/full_skills.csv`
- `outputs/raw_data/`

Audit and failure logs:

- `outputs/skill_md_scan_results_errors.csv`
- `outputs/processing_failures.tsv`
- `outputs/name_filtered_repos.tsv`
- `outputs/name_filtered_repos_counts.json`
