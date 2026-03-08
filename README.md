# msr-skills-md

Mine GitHub repositories for `SKILL.md` files. Given a list of repositories (from SEART CSV exports or scraped directly from the GitHub API), the pipeline scans each repository via the GitHub Code Search API and writes a results CSV recording whether the target file was found, plus metadata about each repo.

Designed for read-only, resumable, rate-limit-aware bulk scanning over large repository sets.

See [`.cursor/skills/msr/SKILL.md`](.cursor/skills/msr/SKILL.md) for the full design specification.

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python project manager)
- Python 3.10 or later (managed automatically by uv)
- One or more GitHub personal access tokens (strongly recommended to avoid rate limits)

### Setting tokens via `.env`

Create a `.env` file in the repo root (see `.env.example`). Multi-line JSON arrays are supported:

```
GH_TOKENS=[
    "ghp_token1",
    "ghp_token2",
    "ghp_token3"
]
```

Or as a comma-separated string on a single line:

```
GH_TOKENS=ghp_token1,ghp_token2,ghp_token3
```

### Setting tokens via environment variable

```sh
export GH_TOKENS=ghp_token1,ghp_token2,ghp_token3   # macOS/Linux
$env:GH_TOKENS = "ghp_token1,ghp_token2,ghp_token3" # PowerShell
```

### Token priority resolution order

1. `--github-tokens` CLI flag (comma-separated)
2. `--github-token` CLI flag (single token)
3. `GH_TOKENS` environment variable or `.env` file
4. Unauthenticated (10 search req/min — not usable for bulk scans)

> **Note:** The scanner uses the GitHub Code Search API, which has a separate rate limit of **10 requests/minute per authenticated token** (not the 5,000/hr core limit). With 3 tokens that gives ~30 searches/minute sustained throughput. Multiple tokens are strongly recommended.

---

## Installation

```sh
git clone https://github.com/your-org/msr-skills-md.git
cd msr-skills-md
uv sync
```

This creates a virtual environment and installs all dependencies from `uv.lock`.

---

## Quick start

### Option 1: Starting from SEART CSV exports

Place your SEART CSV exports in `data/seart_csvs/`, then jump straight to **Step A** below.

### Option 2: Starting from the GitHub API (no SEART required)

Use `A_github_search.py` to build the initial repository list directly from the GitHub Search API. This produces a SEART-compatible CSV that feeds into the same pipeline:

**Step A — Scrape repositories from GitHub:**

```sh
uv run python src/A_github_search.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --resume
```

uv run python src/A_github_search.py --out-csv data/seart_csvs/github_search_results.csv --resume

Default criteria applied:
- 10 or more stars
- MIT, Apache 2.0, BSD-3-Clause, or BSD-2-Clause license
- TypeScript, Python, C#, Go, C++, JavaScript, Java, C, Rust or PHP
- Pushed since 2025-10-16

The output CSV is written to `data/seart_csvs/github_search_results.csv` and can be used immediately as the `--seart-dir` input for Step A.

Average runtime: ~360 API calls across 36 language/license combinations, at 30 req/min per token — approximately 12 minutes with one token.

---

**Step B — Scan for SKILL.md:**

```sh
uv run python src/B_extract_skill_repos.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results.csv \
  --resume
```

uv run python src/B_extract_skill_repos.py --seart-dir data/seart_csvs --out-csv outputs/skill_md_scan_results.csv --resume

Average runtime is 3.65 repositories/minute/token

Then ensure non-archived and non-forked repositories are properly filtered
uv run python utils/filter_active_repos.py outputs/skill_md_scan_results_found.csv -o outputs/skill_md_scan_results_found_filtered.csv

**Step C — Download skill folders and compute metrics for found repos:**

```sh
uv run python src/C_generate_dataset.py \
  --found-csv outputs/skill_md_scan_results_found.csv \
  --out-csv outputs/full_skills_instances.csv \
  --raw-data-dir outputs/raw_data \
  --resume
```

uv run python src/C_generate_dataset.py --found-csv outputs/skill_md_scan_results_found.csv --out-csv outputs/full_skills_instances.csv --raw-data-dir outputs/raw_data --resume

Average runtime is 14 repos/minute (not sure if rate limits get hit or network througput is the limiting factor)

**Step C — Run RQ1 prevalence and adoption analysis:**

```sh
uv run python src/rq1/C_analyze_metadata.py \
  --scan-csv outputs/skill_md_scan_results.csv \
  --instances-csv outputs/full_skills_instances.csv \
  --out-dir outputs/rq1
```

> **Note on filename convention**: The script defaults to searching for `SKILL.md`. Pass `--match-name SKILLS.md` to search for the plural form instead.

---

## CLI reference

### `A_github_search.py`

Scrapes GitHub repositories via `GET /search/repositories` and writes a SEART-compatible CSV.

| Flag | Default | Description |
|---|---|---|
| `--out-csv PATH` | `data/seart_csvs/github_search_results.csv` | Output CSV path |
| `--min-stars N` | `10` | Minimum star count |
| `--pushed-since DATE` | `2025-10-16` | Only repos pushed on or after `YYYY-MM-DD` |
| `--languages LANG ...` | TypeScript Python C# Go C++ JavaScript Java C PHP | Languages to query (space-separated) |
| `--licenses LICENSE ...` | `mit apache-2.0 bsd-3-clause bsd-2-clause` | License SPDX keys (space-separated) |
| `--resume` | off | Append to existing `--out-csv`, skipping already-written repos |
| `--github-token TOKEN` | *(env)* | Single GitHub PAT; overrides env vars |
| `--github-tokens TOKENS` | *(env)* | Comma-separated GitHub PATs for multi-token rotation |
| `--log-level LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

**Rate limit note:** `/search/repositories` allows **30 requests/minute** per authenticated token (separate from the 10 req/min `/search/code` limit). With `per_page=100` and up to 10 pages per query, 36 combinations require ~360 requests — about 12 minutes with one token.

**Per-combo CSVs:** In addition to the combined `--out-csv`, one CSV per (language, license) pair is written alongside it using the naming convention `{base}_{language}_{license}.csv` (e.g. `github_search_results_typescript_mit.csv`). These files contain the same SEART-compatible schema and can be used as independent inputs to `B_extract_skill_repos.py`.

**1,000-result cap:** Each query returns at most 1,000 results. When a (language, license) pair exceeds this, the script automatically bisects the star range in half and recurses into each half. Bisection continues until every sub-range returns < 1,000 results, down to single star-count values if necessary. The first-page API call doubles as a total-count probe, so no extra requests are wasted.

---

### `B_extract_skill_repos.py`

| Flag | Default | Description |
|---|---|---|
| `--seart-dir PATH` | *(required)* | Directory containing SEART CSV exports (searched recursively) |
| `--out-csv PATH` | *(required)* | Output results CSV path |
| `--shortlist-csv PATH` | *(empty)* | Optional second CSV containing only `found=true` rows |
| `--match-name NAME` | `SKILL.md` | Filename to search for via code search |
| `--min-stars N` | `0` | Skip repos with fewer than N stars (read from SEART data) |
| `--disallow-forks` | off | Skip forked repositories (read from SEART data) |
| `--disallow-archived` | off | Skip archived repositories (read from SEART data) |
| `--max-repos N` | `0` (no limit) | Process at most N repositories |
| `--blacklist PATH` | `blacklist.txt` | Path to a blacklist file (`owner/repo` per line, `#` comments supported) |
| `--resume` | off | Skip repos already present in `--out-csv` |
| `--concurrency N` | `4` | Number of parallel worker threads |
| `--github-token TOKEN` | *(env)* | Single GitHub token; overrides env vars |
| `--github-tokens TOKENS` | *(env)* | Comma-separated GitHub tokens for multi-token rotation |
| `--log-level LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## SEART CSV format

The script auto-detects repository identifiers from these column patterns (in priority order):

| Pattern | Example columns |
|---|---|
| Direct `owner/repo` string | `full_name`, `repo`, `repository` |
| Owner + name pair | `owner`+`name`, `org`+`repo_name`, `repo_owner`+`repo_name` |
| URL | `html_url`, `url` (extracts `owner/repo` from GitHub URLs) |

Repositories are deduplicated across all input CSVs. If a repo appears in more than one file, `source_csv` is set to `MULTIPLE`.

---

## Output CSV schema

`skill_md_scan_results.csv` (and the category-split `_found`, `_not_found`, `_errors` variants) share these columns:

| Column | Description |
|---|---|
| `repo` | `owner/repo` canonical identifier |
| `source_csv` | Originating SEART filename, or `MULTIPLE` |
| `found` | `true` or `false` |
| `match_name` | Filename searched for (e.g. `SKILL.md`) |
| `match_path` | Repo-relative path of the matched file (e.g. `/skills/foo/SKILL.md`) |
| `default_branch` | Default branch, sourced from SEART data |
| `ref_scanned` | Branch/ref used for ACF checks (`HEAD` if SEART branch unknown) |
| `match_url` | HTML URL to the file on GitHub |
| `match_sha` | Git blob SHA of the matched file |
| `match_size_bytes` | File size in bytes (empty — not returned by code search API) |
| `scan_method` | Always `code_search` |
| `http_status` | HTTP status code from the search API call |
| `error_type` | `none`, `auth`, `rate_limited`, `network`, `filtered`, or `other` |
| `error_message` | Short error detail (never contains secrets) |
| `scanned_at_utc` | ISO 8601 UTC timestamp of when this repo was scanned |
| `stars` | Star count from SEART data |
| `fork` | `true` or `false`, from SEART data |
| `archived` | `true` or `false`, from SEART data |
| `has_CLAUDE` | `1` if `CLAUDE.md` found (checked only for `found=true` repos) |
| `has_AGENTS` | `1` if `AGENTS.md` found (checked only for `found=true` repos) |
| `has_COPILOT` | `1` if `.github/copilot-instructions.md` found (checked only for `found=true` repos) |

Followed by all original SEART columns (`id`, `mainLanguage`, `stargazers`, `topics`, `languages`, etc.).

---

## Resume workflow

Scans over large repo sets can be interrupted and resumed without re-scanning already-processed repositories:

1. Run with `--resume` on the first invocation (safe even on a fresh run).
2. If interrupted, re-run the exact same command.
3. Repos already present in `--out-csv` are skipped; new rows are appended.

The shortlist CSV is regenerated from the full results file at the end of each run.

---

## Scan strategy

Each repository costs **one API call** in the common case (no SKILL.md found):

1. **Code Search** — `GET /search/code?q=repo:{owner}/{repo}+filename:{match-name}`. Finds the file anywhere in the repository tree. This is the only call made for the ~98% of repos where SKILL.md is absent.
2. **ACF checks** (found repos only) — Three `GET /repos/.../contents/{path}` calls to check for `CLAUDE.md`, `AGENTS.md`, and `.github/copilot-instructions.md`. Only runs for repos where SKILL.md was confirmed found.

Repo metadata (`default_branch`, `stars`, `fork`, `archived`) is read directly from SEART CSV data — no separate metadata API call is made.

### API rate limits

The Code Search API (`/search/code`) has its own rate limit of **10 requests/minute per authenticated token** — separate from both the 5,000/hr core limit and the 30 req/min limit for other search endpoints. The ACF checks use the core API.

| Tokens | Code-search throughput | Effective repos/hr |
|---|---|---|
| 1 | 10 req/min | ~600 |
| 3 | 30 req/min | ~1,800 |

### Rate limit handling

Rate limiting is handled automatically by the `github_client` module:

- Each token's remaining quota is tracked from `X-RateLimit-Remaining` and `X-RateLimit-Reset` response headers.
- On each request, the token with the highest remaining quota is selected.
- When a token is exhausted, the pool immediately rotates to the next available token.
- When all tokens are exhausted, the pool sleeps until the earliest reset time (plus a 2-second buffer) and resumes automatically — the scan never aborts due to rate limiting.

### Module structure

```
src/
  A_github_search.py         # Step 0 (optional): scrape repo list from GitHub API
  B_extract_skill_repos.py   # Step B: scan repos for SKILL.md via code search
  C_generate_dataset.py      # Step C: download skill folders, compute file metrics
  rq1/
    C_analyze_metadata.py    # Step C: RQ1 prevalence & adoption analysis (figures + tables)
  github_client/
    __init__.py              # public re-exports
    token_pool.py            # TokenBucket, TokenPool, load_tokens_from_env
    client.py                # GitHubClient (HTTP + pool integration)

outputs/
  skill_md_scan_results.csv        # all scanned repos (Step A output)
  skill_md_scan_results_found.csv  # repos where SKILL.md was found
  skill_md_scan_results_not_found.csv
  skill_md_scan_results_errors.csv
  full_skills_instances.csv        # per-repo skill metrics (Step B output)
  raw_data/                        # downloaded skill folder contents (Step B)
  rq1/                             # figures and tables (Step C output)
```
