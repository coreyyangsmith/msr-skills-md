# msr-skills-md

Mine GitHub repositories for `SKILL.md` files. Given a list of repositories (from SEART CSV exports or scraped directly from the GitHub API), the pipeline scans each repository via the GitHub Code Search API and writes a results CSV recording whether the target file was found, plus metadata about each repo.

Designed for read-only, resumable, rate-limit-aware bulk scanning over large repository sets.

Stage 2 records the exact commit SHA observed when a repository is matched, and stage 3 reuses that pinned ref by default so the two outputs stay comparable even if the default branch moves later.

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

Place your SEART CSV exports in `data/seart_csvs/`, then jump straight to the repository scan step below.

### Option 2: Starting from the GitHub API (no SEART required)

Use `search_github_repos.py` to build the initial repository list directly from the GitHub Search API. This produces a SEART-compatible CSV that feeds into the same pipeline:

**Step 1 — Scrape repositories from GitHub:**

```sh
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --resume
```

Default criteria applied:
- 10 or more stars
- MIT, Apache 2.0, BSD-3-Clause, or BSD-2-Clause license
- TypeScript, Python, C#, Go, C++, JavaScript, Java, C, Rust or PHP
- Pushed since 2025-10-16
- (Optional) end date

The output CSV is written to `data/seart_csvs/github_search_results.csv` and can be used immediately as the `--seart-dir` input for Step 2.

Average runtime: ~360 API calls across 36 language/license combinations, at 30 req/min per token — approximately 12 minutes with one token.

---


**Step 2 — Scan for SKILL.md:**
```sh
uv run python src/extract_skill_repos.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results.csv \
  --resume

uv run python src/extract_skill_repos.py --seart-dir data/seart_csvs --out-csv outputs/skill_md_scan_results.csv --resume
```

Average runtime is 3.65 repositories/minute/token

The shared repo-name filter is enabled by default here so stage 2 and stage 3 use the same inclusion rules. Pass `--no-name-filter` to disable the built-in list, or `--name-filter-words foo,bar` to add extra words.

Then ensure non-archived and non-forked repositories are properly filtered
uv run python utils/filter_active_repos.py outputs/skill_md_scan_results_found.csv -o outputs/skill_md_scan_results_found_filtered.csv

**Step 3 — Download skill folders and compute metrics for found repos:**

```sh
uv run python src/generate_dataset.py \
  --found-csv outputs/skill_md_scan_results_found.csv \
  --out-csv outputs/full_skills_instances.csv \
  --raw-data-dir outputs/raw_data \
  --resume
```

Average runtime is 14 repos/minute (not sure if rate limits get hit or network througput is the limiting factor)

Stage 3 writes `outputs/processing_failures.tsv` by default so repos missing from `full_skills_instances.csv` can be distinguished as `tree_fetch_failed`, `tree_truncated`, `zero_skills_found`, or `exception`.

**Optional Step 3.5 — Enrich the scan CSV with contributor counts (needed for the contributor-count figure):**

```sh
uv run python src/enrich_scan_contributors.py \
  --scan-csv outputs/skill_md_scan_results.csv \
  --out-csv outputs/skill_md_scan_results_with_contributors.csv \
  --resume
```

**Optional Step 3.6 — Fetch GitHub repo metadata and READMEs:**

```sh
uv run python src/fetch_repo_metadata_readmes.py \
  --input-csv outputs/full_skills_instances.csv \
  --out-csv outputs/repo_metadata_readmes/repo_metadata.csv \
  --readme-dir outputs/repo_metadata_readmes/readmes \
  --resume
```

By default this only processes repositories whose `mainLanguage` is `Python`.
It writes one row per unique Python repository in the input CSV and saves each
repository README to `--readme-dir` using `owner__repo` filenames. Pass
`--all-languages` only when intentionally collecting every language.

**Step 3.7 — (Optional) Enrich the scan CSV with extended ACF columns**

If `outputs/skill_md_scan_results_with_contributors.csv` only has `has_CLAUDE`, `has_AGENTS`, and `has_COPILOT`, you can add `has_CURSORRULES_MD`, `has_INSTRUCTIONS_MD`, and `has_GEMINI` using the GitHub Contents API only (no code search), pinned to each repo’s `commit_sha` / `acf_ref` from `data/skill_only_scan/known_skill_repos.csv`:

```sh
uv run python src/enrich_extended_acf_columns.py
```

This writes `outputs/skill_md_scan_results_skill_only_new_acfs.csv` and merges into `outputs/skill_md_scan_results_with_contributors_extended.csv`. Use the SKILL-only file as `--acf-scan-csv` for ACF-specific RQ1 figures, or the merged extended file as `--scan-csv` when you want one full-corpus input with all six ACF columns.

**Step 4 — Run RQ1 prevalence and adoption analysis:**

```sh
uv run python src/rq1/analyze_metadata.py \
  --scan-csv outputs/skill_md_scan_results_with_contributors.csv \
  --acf-scan-csv outputs/skill_md_scan_results_skill_only_new_acfs.csv \
  --instances-csv outputs/full_skills_instances.csv \
  --out-dir outputs/rq1
```

For ACF figures, `--acf-scan-csv outputs/skill_md_scan_results_skill_only_new_acfs.csv` is sufficient because those figures analyze repositories that already contain `SKILL.md`. For non-ACF prevalence figures, keep `--scan-csv` pointed at the full scan population, or pass `outputs/skill_md_scan_results_with_contributors_extended.csv` as `--scan-csv` if you want a single full-corpus file with the extended ACF columns included.

If contributor enrichment is skipped, the RQ1 wrapper still runs and writes a note file explaining that the contributor-count figure could not be generated. The wrapper always requires `--instances-csv` (e.g. `outputs/full_skills_instances.csv`) so instance-level figures use every row in that file; blacklist/name filters apply to the scan CSV only, not to the instances export.

> **Note on filename convention**: Matching is exact on the basename. `SKILL.md` matches, while `skill.md`, `SKILL.MD`, and filenames that merely contain `skill.md` do not. Pass `--match-name SKILLS.md` to search for the plural form instead.

---

## RQ2 — Content analysis

> **[Placeholder]** RQ2 analysis scripts and instructions will be added here once the labeling phase is complete.

---

## RQ3 — Manual labeling sample preparation

RQ3 requires a stratified random sample of `SKILL.md` files to be manually labeled by two annotators. The three scripts below handle (1) generating per-language metadata summaries from the raw data, (2) drawing a reproducible random sample per language, and (3) splitting that sample into labeling buckets with a shared overlap set for inter-rater agreement.

### Step 1 — Generate per-language metadata summaries

Walks `outputs/raw_data/` (whose immediate children are language folders) and writes one `<language>_summary.json` per language to `outputs/rq3/`.

```sh
uv run python src/rq3/retrieve_language_metadata.py \
  --root outputs/raw_data \
  --out-dir outputs/rq3

uv run python src/rq3/retrieve_language_metadata.py --root outputs/raw_data --out-dir outputs/rq3
```

### Step 2 — Draw a random language sample

Randomly samples `SKILL.md` files from a language subfolder of `raw_data` and copies them — preserving the original relative path structure — into `outputs/rq3/language_sample/<Language>/`. Run once per language you want to include.

```sh
# Python
uv run python src/rq3/generate_language_sample.py --root outputs/raw_data/Python --n 370 --seed 42 --out-dir outputs/rq3/language_sample/Python

# TypeScript
uv run python src/rq3/generate_language_sample.py --root outputs/raw_data/TypeScript --n 372 --seed 42 --out-dir outputs/rq3/language_sample/Typescript
```

`--seed` ensures the sample is reproducible across machines. Omit it to draw a fresh random sample. If `--n` exceeds the corpus size, all available files are used and a warning is logged.

### Step 3 — Split sample into labeling buckets

Distributes the sampled files into three subfolders under `outputs/rq3/labeling_samples/<Language>/`:

| Subfolder | Contents |
|---|---|
| `both/` | Shared overlap set — seen by **both** labelers (used to compute inter-rater agreement) |
| `A/` | Items assigned exclusively to labeler A |
| `B/` | Items assigned exclusively to labeler B |

Each file appears in exactly one bucket. The split is done without replacement across all three buckets.

```sh
# Python
uv run python src/rq3/generate_labeling_samples.py --root outputs/rq3/language_sample/Python --both 56 --A 157 --B 157 --out-dir outputs/rq3/labeling_samples/Python --seed 42

# TypeScript
uv run python src/rq3/generate_labeling_samples.py --root outputs/rq3/language_sample/Typescript --both 56 --A 158 --B 158 --out-dir outputs/rq3/labeling_samples/Typescript --seed 42
```

The `--both + --A + --B` total must not exceed the number of files in `--root`. Adjust the counts to match your desired sample size and overlap ratio.

### RQ3 module structure

```
src/rq3/
  retrieve_language_metadata.py   # Step 1: per-language JSON summaries from raw_data
  generate_language_sample.py     # Step 2: random per-language sample from raw_data
  generate_labeling_samples.py    # Step 3: split sample into both/A/B labeling buckets

outputs/rq3/
  <Language>_summary.json         # per-language metadata summary (Step 1)
  language_sample/                # sampled SKILL.md files, mirroring raw_data paths (Step 2)
  labeling_samples/               # split into both/, A/, B/ per language (Step 3)
```

---

## CLI reference

### `search_github_repos.py`

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

**Rate limit note:** `/search/repositories` allows **30 requests/minute** per authenticated token and **10 requests/minute** unauthenticated (separate from the 10 req/min `/search/code` limit). With `per_page=100` and up to 10 pages per query, 40 combinations require ~400 requests at minimum — about 14 minutes with one token.

**Per-combo CSVs:** In addition to the combined `--out-csv`, one CSV per (language, license) pair is written alongside it using the naming convention `{base}_{language}_{license}.csv` (e.g. `github_search_results_typescript_mit.csv`). These files contain the same SEART-compatible schema and can be used as independent inputs to `extract_skill_repos.py`.

**1,000-result cap:** Each query returns at most 1,000 results. The script uses a three-level strategy to stay under the cap without missing repos:

1. **Full date range, no star subdivision** — paginate directly if total < 1,000.
2. **Static star brackets** (16 predefined ranges) over the full date range — paginate directly if total < 1,000.
3. **Recursive time-window subdivision** per bracket — when a bracket still exceeds 1,000 results the query window is split repeatedly:
   - Weekly window → individual days
   - Single day → 12-hour halves
   - 12-hour half → 6-hour quarters
   - 6-hour quarter → binary bisection of the star range

   Only when a single star value within a 6-hour window still returns ≥ 1,000 results is the cap accepted (with a warning). This situation is extremely unlikely in practice.

The end date is frozen at startup (defaulting to today when `--end-date` is omitted) so that every query uses a closed `pushed:start..end` window and reruns are reproducible. The first-page API call at each level doubles as a total-count probe, so no extra requests are wasted.

---

### `extract_skill_repos.py`

| Flag | Default | Description |
|---|---|---|
| `--seart-dir PATH` | *(required)* | Directory containing SEART CSV exports (searched recursively) |
| `--out-csv PATH` | *(required)* | Output results CSV path |
| `--shortlist-csv PATH` | *(empty)* | Optional second CSV containing only `found=true` rows |
| `--match-name NAME` | `SKILL.md` | Filename to search for via code search |
| `--min-stars N` | `0` | Skip repos with fewer than N stars (read from SEART data) |
| `--disallow-forks` | off | Skip forked repositories (read from SEART data) |
| `--disallow-archived` | off | Skip archived repositories (read from SEART data) |
| `--name-filter-words WORDS` | *(empty)* | Comma-separated extra repo-name filter words added to the shared built-in list |
| `--no-name-filter` | off | Disable the shared built-in repo-name filter |
| `--max-repos N` | `0` (no limit) | Process at most N repositories |
| `--blacklist PATH` | `blacklist.txt` | Path to a blacklist file (`owner/repo` per line, `#` comments supported) |
| `--resume` | off | Skip repos already present in `--out-csv` |
| `--concurrency N` | `4` | Number of parallel worker threads |
| `--github-token TOKEN` | *(env)* | Single GitHub token; overrides env vars |
| `--github-tokens TOKENS` | *(env)* | Comma-separated GitHub tokens for multi-token rotation |
| `--log-level LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

### `generate_dataset.py`

| Flag | Default | Description |
|---|---|---|
| `--found-csv PATH` | *(required)* | Input CSV from `extract_skill_repos.py`, typically `*_found.csv` |
| `--out-csv PATH` | *(required)* | Output per-skill dataset CSV |
| `--raw-data-dir PATH` | *(required)* | Root directory for downloaded skill folders |
| `--match-name NAME` | `SKILL.md` | Exact basename to match in the git tree |
| `--blacklist PATH` | `blacklist.txt` | Path to a blacklist file (`owner/repo` per line) |
| `--name-filter-words WORDS` | *(empty)* | Comma-separated extra repo-name filter words added to the shared built-in list |
| `--no-name-filter` | off | Disable the shared built-in repo-name filter |
| `--name-filter-log PATH` | `<out dir>/name_filtered_repos.tsv` | TSV recording repos skipped by the name filter |
| `--failures-log PATH` | `<out dir>/processing_failures.tsv` | TSV recording repos that produced no dataset rows because of tree or processing failures |
| `--resume` | off | Skip repos already present in `--out-csv` or with successful metadata.json |
| `--concurrency N` | `1` | Number of parallel worker threads |
| `--github-token TOKEN` | *(env)* | Single GitHub token; overrides env vars |
| `--github-tokens TOKENS` | *(env)* | Comma-separated GitHub tokens for multi-token rotation |
| `--log-level LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

Stage 3 prefers the `commit_sha` column from stage 2 when it is present. Older found CSVs without that column still work, but they fall back to `default_branch`, which is less stable for cross-run comparison.

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
| `commit_sha` | Commit SHA pinned at the scanned branch tip for use by stage 3 |
| `match_url` | HTML URL to the file on GitHub |
| `match_sha` | Git blob SHA of the matched file |
| `match_size_bytes` | File size in bytes (empty — not returned by code search API) |
| `scan_method` | Always `code_search` |
| `http_status` | HTTP status code from the API call that determined the final scan outcome |
| `error_type` | `none`, `auth`, `rate_limited`, `network`, `filtered`, or `other` |
| `error_message` | Short error detail (never contains secrets) |
| `scanned_at_utc` | ISO 8601 UTC timestamp of when this repo was scanned |
| `stars` | Star count from SEART data |
| `fork` | `true` or `false`, from SEART data |
| `archived` | `true` or `false`, from SEART data |
| `has_README` | `1` if GitHub Community Profile reports a recognized README for the repo |
| `has_CONTRIBUTING` | `1` if GitHub Community Profile reports a recognized contributing guide |
| `has_SECURITY` | `1` if GitHub Community Profile reports a recognized security policy |
| `has_CODE_OF_CONDUCT` | `1` if GitHub Community Profile reports a recognized code of conduct |
| `has_CLAUDE` | `1` if `CLAUDE.md` found (checked only for `found=true` repos) |
| `has_AGENTS` | `1` if `AGENTS.md` found (checked only for `found=true` repos) |
| `has_COPILOT` | `1` if `.github/copilot-instructions.md` found (checked only for `found=true` repos) |
| `has_CURSORRULES_MD` | `1` if `.cursorrules.md` found (checked only for `found=true` repos) |
| `has_INSTRUCTIONS_MD` | `1` if `.instructions.md` found (checked only for `found=true` repos) |
| `has_GEMINI` | `1` if `GEMINI.md` found (checked only for `found=true` repos) |

Followed by all original SEART columns (`id`, `mainLanguage`, `stargazers`, `topics`, `languages`, etc.).

---

## Resume workflow

Scans over large repo sets can be interrupted and resumed without re-scanning already-processed repositories:

1. Run with `--resume` on the first invocation (safe even on a fresh run).
2. If interrupted, re-run the exact same command.
3. Repos already present in `--out-csv` are skipped; new rows are appended.

The shortlist CSV is regenerated from the full results file at the end of each run.

If `--resume` is used against an older output CSV whose header does not match the current schema, the script now exits with a clear schema-mismatch error instead of appending incompatible rows. Start with a fresh output file when new columns are added.

For stage 3, repos are only treated as successfully processed when they produce at least one skill row. A prior `metadata.json` with `skill_count: 0` is retried instead of becoming a permanent false negative.

---

## Scan strategy

Each repository costs **two API calls** in the common case (no SKILL.md found):

1. **Community Profile** — `GET /repos/{owner}/{repo}/community/profile`. Extracts repo-level maintainer-readiness flags (`README`, `CONTRIBUTING`, `SECURITY`, `CODE_OF_CONDUCT`) for every scanned repo.
2. **Code Search** — `GET /search/code?q=repo:{owner}/{repo}+filename:{match-name}`. Finds the file anywhere in the repository tree.
3. **ACF checks** (found repos only) — Six `GET /repos/.../contents/{path}` calls to check for `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, `.cursorrules.md`, `.instructions.md`, and `GEMINI.md`. Only runs for repos where SKILL.md was confirmed found.

Repo metadata (`default_branch`, `stars`, `fork`, `archived`) is read directly from SEART CSV data — no separate metadata API call is made.

### API rate limits

The Code Search API (`/search/code`) has its own rate limit of **10 requests/minute per authenticated token** — separate from both the 5,000/hr core limit and the 30 req/min limit for other search endpoints. The Community Profile and ACF checks use the core API.

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
  search_github_repos.py     # Step 1 (optional): scrape repo list from GitHub API
  extract_skill_repos.py     # Step 2: scan repos for SKILL.md via code search
  generate_dataset.py        # Step 3: download skill folders, compute file metrics
  enrich_scan_contributors.py  # Optional Step 3.5: populate contributor counts in the scan CSV
  fetch_repo_metadata_readmes.py # Optional Step 3.6: fetch repo metadata and READMEs
  rq1/
    analyze_metadata.py      # Wrapper for scan-based RQ1 figures/tables
    skill_file_distribution.py  # Wrapper for skill-file distribution outputs
    common.py                # Shared RQ1 data loading, plotting, and helper utilities
    fig*.py / table*.py      # One script per RQ1 artifact (figure/table pair where applicable)
  github_client/
    __init__.py              # public re-exports
    token_pool.py            # TokenBucket, TokenPool, load_tokens_from_env
    client.py                # GitHubClient (HTTP + pool integration)

outputs/
  skill_md_scan_results.csv        # all scanned repos (Step 2 output)
  skill_md_scan_results_found.csv  # repos where SKILL.md was found
  skill_md_scan_results_not_found.csv
  skill_md_scan_results_errors.csv
  processing_failures.tsv          # stage-3 repos with no dataset rows and why
  name_filtered_repos.tsv          # stage-3 repos skipped by the shared name filter
  full_skills_instances.csv        # per-repo skill metrics (Step 3 output)
  raw_data/                        # downloaded skill folder contents (Step 3)
  rq1/                             # figures and tables (Step 4 output)
```
