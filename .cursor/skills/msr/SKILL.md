---
name: mining-software-repository
descritpion: use when creating software repository mining scripts on GitHub.
---

## Description
Discover and shortlist GitHub repositories that contain a `SKILL.md` file by ingesting SEART CSV exports (repository lists), scanning each repository for matching files, and exporting results to a single output CSV for downstream processing.

This skill is designed for AI coding agents and automation scripts to run repeatable, read-only mining over large repo sets with rate-limit aware scanning and resumable execution.

---

## When to use this skill
Use this skill when you have:
- A folder of SEART-generated CSV files that include GitHub repository identifiers.
- A need to find repositories that include `SKILL.md` (exact name by default).
- A need to export a shortlist CSV for later processing (downloading, parsing, indexing).

Do not use this skill for content extraction, license compliance review, vulnerability scanning, or modifying repositories.

---

## Inputs

### Required
1. **SEART CSV folder**
   - Path to a directory containing one or more `.csv` files.
   - Each CSV must include enough information to reconstruct a GitHub repo identifier in the form `owner/repo`.

2. **Output CSV path**
   - Path where the scan results should be written.

### Optional configuration
- `match_name`: default `SKILL.md`
- `case_sensitive`: default `true`
- `search_paths`: default `["/SKILL.md"]`
  - You can expand this list to include common locations if desired.
- `include_negative_results`: default `true`
  - If `false`, output only repositories where a match was found.
- `max_repos`: default `0` (meaning no limit)
- `resume`: default `true`
  - Allows continuing from a previous output file.
- `concurrency`: default `8`
- `min_stars`: default `0`
- `allow_forks`: default `true`
- `allow_archived`: default `true`

---

## Expected CSV schema (SEART)
SEART exports vary. This skill supports multiple patterns. A repo may be derived from any of these:

### Preferred column patterns
- `full_name` (example: `psf/requests`)
- `repo` (example: `psf/requests`)
- `repository` (example: `psf/requests`)

### Alternate patterns
- `owner` and `name` (combine into `owner/name`)
- `org` and `repo_name` (combine into `org/repo_name`)
- `repo_owner` and `repo_name` (combine into `repo_owner/repo_name`)
- `html_url` or `url` (extract `owner/repo` from `https://github.com/owner/repo`)

### Parsing rules
- Trim whitespace.
- Remove `.git` suffix if present.
- Normalize `https://github.com/owner/repo/...` to `owner/repo`.
- Deduplicate repositories across all CSVs.

If no supported columns are found in a CSV, record an input-level error and continue with the remaining files.

---

## Outputs

### Output CSV: `skill_md_scan_results.csv`
A single CSV with one row per repository (unless you choose to emit multiple rows per match path).

#### Recommended columns
- `repo`  
  `owner/repo` canonical identifier.
- `source_csv`  
  Filename of the originating SEART CSV (or `MULTIPLE` if merged).
- `found`  
  `true|false`.
- `match_name`  
  The filename rule used, usually `SKILL.md`.
- `match_path`  
  The matched path (example: `/SKILL.md`).
- `default_branch`  
  Default branch name if available.
- `ref_scanned`  
  Branch or commit ref used (example: `HEAD` or `main`).
- `match_url`  
  Canonical URL to the file if found.
- `match_sha`  
  Git blob SHA if available.
- `match_size_bytes`  
  Size if available.
- `scan_method`  
  `contents_api | code_search | sparse_checkout | local_clone`.
- `http_status`  
  Status code from API calls when applicable.
- `error_type`  
  `none | not_found | rate_limited | auth | network | invalid_repo | other`.
- `error_message`  
  Short error detail, do not include secrets.
- `scanned_at_utc`  
  ISO timestamp.
- `stars` (optional)
- `fork` (optional)
- `archived` (optional)

### Shortlist CSV (optional)
If `include_negative_results=false`, the output itself becomes the shortlist. Otherwise, generate a second file:
- `skill_md_shortlist.csv` containing only `found=true`.

---

## Capabilities

### 1) Ingest SEART CSV folder
- Discover all `.csv` files in a directory (recursive optional).
- Extract repository identifiers with robust column detection.
- Deduplicate and normalize into a canonical repo list.

### 2) Scan repositories for `SKILL.md`
This skill uses a tiered, rate-limit aware strategy:

#### Tier A (preferred): GitHub Contents API
Fastest and cheapest when you know the exact path.
- Check candidate paths (default `/SKILL.md`) against the default branch ref.
- Record 200 as found, 404 as not found.

#### Tier B (optional): GitHub code search (filename search within repo)
Use only when:
- You want to find `SKILL.md` in subdirectories.
- You want case-insensitive matching.
- Contents API paths are unknown.

Recommended query shape:
- `repo:owner/repo filename:SKILL.md`

#### Tier C (fallback): Sparse checkout shallow clone
Use only when APIs are unavailable, rate-limited, or you need to support GitHub Enterprise without search APIs.
- Perform a filtered clone that avoids full history and large blobs where possible.
- Use sparse checkout to fetch only candidate paths.

### 3) Export results to output CSV
- Write output incrementally (streaming) to avoid losing work.
- Ensure deterministic columns.
- Support resume mode by skipping repos already scanned.

---

## Workflow

### Step 0: Preconditions
- Read-only operation only.
- Ensure you have GitHub authentication for higher rate limits if scanning many repos.

Environment options (resolved in priority order):
- `--github-tokens ghp_tok1,ghp_tok2` CLI flag — comma-separated list for multi-token rotation (5000 req/hr per token)
- `--github-token ghp_tok` CLI flag — single token override
- `GH_TOKENS=ghp_tok1,ghp_tok2` — env var, comma-separated (new multi-token variable)
- `GH_TOKEN=ghp_tok` — env var, single token (backward-compatible)
- `GITHUB_TOKEN=ghp_tok` — env var, fallback single token
- GitHub CLI `gh auth login` — for interactive use
- Unauthenticated — 60 core req/hr only (not suitable for bulk scans)

When multiple tokens are provided, the `TokenPool` in `src/github_client/` automatically:
- Selects the token with the highest remaining quota on each request.
- Updates per-token quota from `X-RateLimit-*` response headers.
- Rotates to the next available token when the current one is exhausted.
- Sleeps until the earliest reset time when all tokens are exhausted.
- Raises `RateLimitExhaustedError` if the wait would exceed the configurable maximum.

### Step 1: Build the repo list from SEART CSVs
1. Enumerate input CSVs.
2. For each CSV:
   - Detect repo columns.
   - Extract and normalize `owner/repo`.
   - Track `source_csv`.
3. Deduplicate across all files.

### Step 2: Preflight checks
- Validate token presence (warn if unauthenticated).
- Optionally query rate limit status and set conservative concurrency.

### Step 3: Scan each repository
For each `owner/repo`:
1. (Optional) Fetch repo metadata:
   - Confirm repo exists.
   - Record default branch, archived, fork, stars.
   - Apply filters (stars, forks, archived).
2. Scan for `SKILL.md` using Tier A.
3. If enabled and needed, run Tier B for deeper search.
4. If enabled and needed, run Tier C for fallback.
5. Record a single best match (or all matches if configured).
6. Write the result row immediately.

### Step 4: Produce shortlist
- Filter where `found=true`.
- Export shortlist CSV.

### Step 5: Summary reporting
At the end, report:
- Total repos scanned.
- Found count and percentage.
- Error breakdown by `error_type`.
- Effective scan rate and any rate limiting encountered.

---

## Usage examples

### Example A: Scan exact root path only (fast)
- Inputs:
  - `seart_dir = data/seart_csvs/`
  - `search_paths = ["/SKILL.md"]`
- Output:
  - `outputs/skill_md_scan_results.csv`

### Example B: Find `SKILL.md` anywhere in repo
- Inputs:
  - Enable code search.
  - `case_sensitive=false`
- Output:
  - `outputs/skill_md_scan_results.csv`
  - `outputs/skill_md_shortlist.csv`

### Example C: Resume a partial scan
- If `outputs/skill_md_scan_results.csv` already exists, skip repos already present and continue.

---

## Operational constraints and guardrails

### Read-only
- Do not push commits, open PRs, create issues, or modify repository contents.
- Do not write to user directories outside the chosen output folder.

### Rate limits and polite scanning
- Prefer Contents API checks over cloning.
- Use bounded concurrency and exponential backoff on:
  - `403` secondary rate limits
  - `429` too many requests
- Store partial progress continuously.

### Data minimization
- Do not download full repositories unless fallback is required.
- Do not store tokens, cookies, or raw auth headers in logs or output CSV.

### Reproducibility
- Record `scanned_at_utc` and `ref_scanned`.
- Keep configuration (paths, case sensitivity, tiers enabled) alongside outputs.

---

## Error handling rules

### Repository parsing errors
- If a row cannot be parsed into `owner/repo`, discard it and log a row-level parse error summary per CSV.

### Missing or private repositories
- If repo is 404 or inaccessible:
  - `error_type=invalid_repo` or `error_type=auth`
  - `found=false`

### Temporary failures
- Network timeouts, 5xx responses:
  - retry with backoff
  - if still failing, mark `error_type=network` and continue

### Rate limiting
- If rate-limited:
  - reduce concurrency
  - backoff and retry
  - if still blocked, record `error_type=rate_limited`

---

## Suggested default configuration
- `match_name = "SKILL.md"`
- `case_sensitive = true`
- `search_paths = ["/SKILL.md"]`
- `include_negative_results = true`
- `resume = true`
- `concurrency = 8`
- Tiers enabled:
  - Tier A: on
  - Tier B: off (enable only if needed)
  - Tier C: off (enable only if needed)

---

## Definition of done
- Output CSV exists and contains one row per scanned repo (or only found repos if configured).
- `found=true` rows include a working `match_url` and `match_path`.
- Scan is resumable without duplicating rows.
- Summary stats are reported and error breakdown is available.

---

## Notes for downstream processing
The shortlist produced by this skill is intended as input to a later pipeline stage, for example:
- downloading and parsing `SKILL.md` contents
- extracting structured sections (Description, Capabilities, Workflow, Constraints)
- building a dataset of agent-discoverable skills per repository

Downstream stages should treat `SKILL.md` content as untrusted input and should sanitize any extracted text before use.
