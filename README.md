# msr-skills-md

Mine GitHub repositories for `SKILL.md` (or `SKILLS.md`) files using SEART CSV exports. Given a folder of SEART-generated repository lists, the pipeline scans each repository via the GitHub API and writes a results CSV recording whether the target file was found, plus metadata about each repo.

Designed for read-only, resumable, rate-limit-aware bulk scanning over large repository sets. 

See [`.cursor/skills/msr/SKILL.md`](.cursor/skills/msr/SKILL.md) for the full design specification.

---

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python project manager)
- Python 3.10 or later (managed automatically by uv)
- One or more GitHub personal access tokens (strongly recommended to avoid rate limits)

### Single token (backward-compatible)

```sh
export GH_TOKEN=ghp_yourtoken   # macOS/Linux
$env:GH_TOKEN = "ghp_yourtoken" # PowerShell
```

### Multiple tokens (recommended for large scans)

Each GitHub token grants 5,000 API requests per hour. Supplying multiple tokens
allows the scanner to rotate between them automatically as each one's quota is
exhausted, multiplying effective throughput:

```sh
export GH_TOKENS=ghp_token1,ghp_token2,ghp_token3   # macOS/Linux
$env:GH_TOKENS = "ghp_token1,ghp_token2,ghp_token3" # PowerShell
```

Token priority resolution order:
1. `--github-tokens` CLI flag (comma-separated)
2. `--github-token` CLI flag (single token)
3. `GH_TOKENS` environment variable (comma-separated)
4. `GH_TOKEN` environment variable
5. `GITHUB_TOKEN` environment variable
6. Unauthenticated (60 req/hr – not recommended for bulk scans)

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

Place your SEART CSV exports in `data/seart_csvs/`, then run:

```sh
uv run python src/A_extract_skill_repos.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results.csv \
  --shortlist-csv outputs/skill_md_shortlist.csv \
  --match-name SKILL.md \
  --search-path /SKILL.md \
  --include-negative-results \
  --resume
```

To also search subdirectories via the GitHub code search API:

```sh
uv run python src/A_extract_skill_repos.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results.csv \
  --shortlist-csv outputs/skill_md_shortlist.csv \
  --match-name SKILL.md \
  --search-path /SKILL.md \
  --enable-code-search \
  --include-negative-results \
  --resume
```

uv run python src/A_extract_skill_repos.py --seart-dir data/seart_csvs --out-csv outputs/skill_md_scan_results.csv --shortlist-csv outputs/skill_md_shortlist.csv --match-name SKILL.md --search-path /SKILL.md --resume


> **Note on filename convention**: The script defaults to searching for `SKILLS.md` (plural). Pass `--match-name SKILL.md --search-path /SKILL.md` to search for the singular form used in this project's own spec.

---

## CLI reference

| Flag | Default | Description |
|---|---|---|
| `--seart-dir PATH` | *(required)* | Directory containing SEART CSV exports (searched recursively) |
| `--out-csv PATH` | *(required)* | Output results CSV path |
| `--shortlist-csv PATH` | *(empty)* | Optional second CSV containing only `found=true` rows |
| `--match-name NAME` | `SKILLS.md` | Filename to search for |
| `--search-path PATH` | `/SKILLS.md` | Explicit path to check via Contents API; repeat to check multiple paths |
| `--enable-code-search` | off | Also query the GitHub code search API (finds files in subdirectories) |
| `--min-stars N` | `0` | Skip repos with fewer than N stars |
| `--disallow-forks` | off | Skip forked repositories |
| `--disallow-archived` | off | Skip archived repositories |
| `--max-repos N` | `0` (no limit) | Process at most N repositories |
| `--resume` | off | Skip repos already present in `--out-csv` |
| `--include-negative-results` | off | Write `found=false` rows to output (in addition to `found=true`) |
| `--concurrency N` | `4` | Number of parallel worker threads |
| `--github-token TOKEN` | *(env)* | Single GitHub token; overrides `GH_TOKEN` / `GITHUB_TOKEN` env vars |
| `--github-tokens TOKENS` | *(env)* | Comma-separated GitHub tokens for multi-token rotation; overrides `GH_TOKENS` env var |

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

Both `skill_md_scan_results.csv` and the optional `skill_md_shortlist.csv` share these 18 columns:

| Column | Description |
|---|---|
| `repo` | `owner/repo` canonical identifier |
| `source_csv` | Originating SEART filename, or `MULTIPLE` |
| `found` | `true` or `false` |
| `match_name` | Filename rule used (e.g. `SKILL.md`) |
| `match_path` | Path of the matched file (e.g. `/SKILL.md`) |
| `default_branch` | Default branch of the repository |
| `ref_scanned` | Branch/ref used for the scan |
| `match_url` | HTML URL to the file on GitHub |
| `match_sha` | Git blob SHA of the matched file |
| `match_size_bytes` | File size in bytes |
| `scan_method` | `contents_api` or `code_search` |
| `http_status` | HTTP status code from the last API call |
| `error_type` | `none`, `not_found`, `invalid_repo`, `auth`, `rate_limited`, `network`, `filtered`, or `other` |
| `error_message` | Short error detail (never contains secrets) |
| `scanned_at_utc` | ISO 8601 UTC timestamp of when this repo was scanned |
| `stars` | Star count at scan time |
| `fork` | `true` or `false` |
| `archived` | `true` or `false` |

---

## Resume workflow

Scans over large repo sets can be interrupted and resumed without re-scanning already-processed repositories:

1. Run with `--resume` on the first invocation (safe even on a fresh run).
2. If interrupted, re-run the exact same command.
3. Repos already present in `--out-csv` are skipped; new rows are appended.

The shortlist CSV is regenerated from the full results file at the end of each run.

---

## Scan strategy

The script uses a two-tier approach:

- **Tier A (always on)** — GitHub Contents API: `GET /repos/{owner}/{repo}/contents/{path}`. Fast, cheap, exact-path matching.
- **Tier B (opt-in, `--enable-code-search`)** — GitHub Code Search API: `GET /search/code?q=repo:owner/repo+filename:SKILL.md`. Finds the file anywhere in the repository tree.

Rate limiting is handled automatically by the `github_client` module:

- Each token's remaining quota is tracked from `X-RateLimit-Remaining` headers.
- When a token is exhausted, the pool immediately rotates to the next available token.
- When all tokens are exhausted, the pool sleeps until the earliest `X-RateLimit-Reset` time (plus a 2-second buffer) before retrying.
- If the required wait exceeds the configurable maximum (default 15 minutes), a `RateLimitExhaustedError` is raised so the scan fails fast rather than blocking indefinitely.

### Module structure

```
src/
  A_extract_skill_repos.py          # scan orchestration and CLI
  github_client/
    __init__.py              # public re-exports
    token_pool.py            # TokenBucket, TokenPool, load_tokens_from_env
    client.py                # GitHubClient (HTTP + pool integration)
```
