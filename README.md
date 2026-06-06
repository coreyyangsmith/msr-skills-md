# msr-skills-md

Mine GitHub repositories for `SKILL.md` files. Given a list of repositories (from SEART CSV exports or scraped directly from the GitHub API), the recommended pipeline scans each repository with GitHub git-tree REST calls and writes a results CSV recording whether the target file was found, plus metadata about each repo.

Designed for read-only, resumable, rate-limit-aware bulk scanning over large repository sets.

Stage 2 records the exact commit SHA observed when a repository is matched, and stage 3 reuses that pinned ref by default so the two outputs stay comparable even if the default branch moves later.

See [`.cursor/skills/msr/SKILL.md`](.cursor/skills/msr/SKILL.md) for the full design specification.

---

## Dataset

The full replication package — including all extracted `SKILL.md` files and the skill folder contents for each matched repository — is archived on Zenodo:

* [https://zenodo.org/records/19654264](https://zenodo.org/records/19654264)

The Zenodo archive contains:

- `raw_data/` — downloaded skill folder trees, one subdirectory per primary language, mirroring the layout written by Stage 3 (`generate_dataset.py`).

Within this repository, we also include:
- `data/skill_files/full_skills.csv` — per-skill instance metrics CSV (Stage 3 output).
- `data/skill_only_scan/skill_repositories.csv` — the filtered shortlist of repositories confirmed to contain `SKILL.md`.
- `data/seart_csvs/` — the SEART-exported repository list used as the Stage 1 input.

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
4. Unauthenticated (low core/search limits — not usable for bulk scans)

> **Note:** The recommended tree-first scanner uses GitHub's core REST API limit rather than the separate Code Search bucket. The legacy Code Search scanner is still available for reproducing older runs, but it is constrained to **10 code-search requests/minute per authenticated token**.

---

## Installation

```sh
git clone https://github.com/your-org/msr-skills-md.git
cd msr-skills-md
uv sync
```

This creates a virtual environment and installs all dependencies from `uv.lock`.

---

## Data Processing Pipeline

The pipeline consists of four main stages plus optional enrichment steps. Stages 1-3 are the data scraping and preprocessing path that creates the repository population, locates `SKILL.md`, filters the matched repository set, downloads the skill artifacts, and prepares analysis-ready CSV/JSON files.

```
GitHub API / SEART CSVs
        │
        ▼
  Stage 1 — Source repository list
  data/seart_csvs/github_search_results.csv
        │
        ▼
  Stage 2 — Scan for SKILL.md
  outputs/skill_md_scan_results.csv
  outputs/skill_md_scan_results_found.csv
        │
        ▼
  Stage 2.5 — Filter active repositories
  data/skill_only_scan/skill_repositories.csv
        │
        ▼
  Stage 3 — Extract skill artifacts
  data/skill_files/full_skills.csv
  outputs/raw_data/<Language>/<owner>__<repo>/
```

---

### Stage 1 — Retrieve source repositories

Use `search_github_repos.py` to build the initial repository list directly from the GitHub Search API. This is the repository-population scraping step. It emits a SEART-compatible CSV, so the downstream scanner can also consume externally generated SEART exports without code changes.

```sh
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --resume
```

Default criteria applied: ≥ 10 stars · MIT/Apache 2.0/BSD-3-Clause/BSD-2-Clause license · TypeScript, Python, C#, Go, C++, JavaScript, Java, C, Rust or PHP · pushed since 2025-10-16.

What the script does:

- Queries `GET /search/repositories` for every language/license combination.
- Freezes `--end-date` at startup, defaulting to today's date, so every query uses a closed `pushed:start..end` window.
- Splits large queries by star bracket and then by time window so GitHub's 1,000-result search cap is less likely to truncate the population.
- Writes one combined CSV plus one per-language/license CSV alongside it.
- Runs a post-search enrichment phase by default to populate fields not present in repository search results (`commits`, `branches`, `releases`, `contributors`, `languages`, and `lastCommitSHA`).

Useful examples:

```sh
# Reproduce the default population search and enrichment.
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --resume

# Limit the crawl to selected languages/licenses.
uv run python src/search_github_repos.py \
  --languages Python TypeScript Rust \
  --licenses mit apache-2.0 \
  --min-stars 25 \
  --pushed-since 2025-10-16 \
  --end-date 2026-06-06 \
  --out-csv data/seart_csvs/github_search_results_subset.csv

# Scrape quickly and skip the slower per-repo enrichment phase.
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --skip-enrich

# Enrich an existing CSV without re-running GitHub repository search.
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --enrich-only \
  --enrich-concurrency 8
```

Important flags:

- `--out-csv PATH` controls the combined SEART-compatible output path.
- `--languages LANG ...` and `--licenses SPDX ...` define the query grid.
- `--min-stars N`, `--pushed-since YYYY-MM-DD`, and `--end-date YYYY-MM-DD` define the population window.
- `--resume` appends only repositories not already present in the combined CSV.
- `--skip-enrich` disables the per-repo metadata enrichment phase.
- `--enrich-only` expects `--out-csv` to already exist and only fills missing enrichment columns.
- `--enrich-concurrency N` controls enrichment worker threads.
- `--github-token TOKEN` and `--github-tokens TOKEN1,TOKEN2` override token discovery from the environment.

Average runtime: roughly 400 repository-search page requests across the default 40 language/license combinations at 30 repository-search requests/minute per token, plus the enrichment calls for rows that still have empty metadata fields.

**Artifact produced:** `data/seart_csvs/github_search_results.csv` — one row per GitHub repository, with per-(language, license) split CSVs written alongside it.

---

### Stage 2 — Scan for SKILL.md

Scan every repository in the Stage 1/SEART input for a `SKILL.md` file. The recommended scanner is now tree-first: it fetches one GitHub git tree per repository, locally detects `SKILL.md`, ACF files, and maintainer-readiness files, and preserves the same CSV schema used by the older Code Search scanner. This avoids the constrained GitHub Code Search bucket and better aligns the scan with pinned commit SHAs.

```sh
uv run python src/extract_skill_repos_tree.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results.csv \
  --resume \
  --concurrency 4 \
  --cache-dir outputs/cache/tree_scan \
  --fallback walk-tree
```

The legacy Code Search implementation remains available as `src/extract_skill_repos.py` and writes the same output schema.

What the script does for each repository:

- Recursively ingests every `.csv` under `--seart-dir`, auto-detecting repo identifiers from `name`, `full_name`, `repo`, `repository`, owner/name pairs, or GitHub URLs.
- Deduplicates repositories across input CSVs and records `source_csv` as `MULTIPLE` when needed.
- Resolves the default branch to a pinned `commit_sha`.
- Calls `GET /repos/{owner}/{repo}/git/trees/{commit_sha}?recursive=1` and scans returned blob paths locally.
- If GitHub marks the recursive response as truncated, falls back to non-recursive tree walking unless `--fallback none` is passed.
- Selects the shortest matching `SKILL.md` path, then lexicographic order for ties.
- Records `match_path`, `match_url`, `match_sha`, and `match_size_bytes` from tree metadata without downloading blobs.
- Detects companion agent-configuration-file flags: `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, `.cursorrules.md`, `.instructions.md`, and `GEMINI.md`.
- Infers `README`, `CONTRIBUTING`, `SECURITY`, and `CODE_OF_CONDUCT` flags from tree paths.
- Caches tree results by repo/ref/method under `--cache-dir` when `--cache-mode read-write` is enabled.
- Writes every result row immediately to the main CSV and to one category split file.

Useful examples:

```sh
# Recommended tree-first scan with resumable output and default filename SKILL.md.
uv run python src/extract_skill_repos_tree.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results.csv \
  --resume \
  --concurrency 4 \
  --cache-dir outputs/cache/tree_scan

# Smoke-test the scanner on the first 250 unique repos.
uv run python src/extract_skill_repos_tree.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results_smoke.csv \
  --max-repos 250 \
  --resume \
  --log-level DEBUG

# Search for another exact filename.
uv run python src/extract_skill_repos_tree.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/agents_md_scan_results.csv \
  --match-name AGENTS.md

# Disable cache reads/writes for a fresh API-only run.
uv run python src/extract_skill_repos_tree.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results.csv \
  --cache-mode off

# Legacy Code Search scanner, retained for comparison or reruns of older methods.
uv run python src/extract_skill_repos.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results_code_search.csv \
  --resume
```

Important flags:

- `--seart-dir PATH` points to the folder of source CSVs; it is searched recursively.
- `--out-csv PATH` is the comprehensive scan file and the resume anchor.
- `--match-name NAME` changes the exact basename detected in the tree.
- `--max-repos N` limits processing for dry runs; `0` means no limit.
- `--blacklist PATH` skips listed `owner/repo` entries.
- `--resume` skips repos already present in `--out-csv`; schema mismatches fail fast.
- `--concurrency N` controls scanning threads. Lower it if secondary rate limits appear.
- `--cache-dir PATH` stores tree response cache files.
- `--cache-mode {read-write,read-only,off}` controls cache use.
- `--fallback {walk-tree,none}` controls truncated recursive tree handling.
- `--include-negative-results` is accepted for compatibility, but the script always writes all rows to the main CSV for complete resume support.

**Artifacts produced:**

| File | Description |
|---|---|
| `outputs/skill_md_scan_results.csv` | All scanned repositories (one row per repo) |
| `outputs/skill_md_scan_results_found.csv` | Repos where `SKILL.md` was found |
| `outputs/skill_md_scan_results_not_found.csv` | Repos where `SKILL.md` was not found |
| `outputs/skill_md_scan_results_errors.csv` | Repos that produced scan errors |
| `outputs/skill_md_scan_results_filtered.csv` | Reserved category split for `error_type=filtered`; currently usually empty because blacklist entries are skipped before scan rows are written |

---

### Stage 2.5 — Filter active repositories

Remove archived and forked repositories from the found set before downloading skill artifacts. The script requires `isArchived` and `isFork` columns from the carried-through SEART data and prints counts plus the filtered repo names for auditability:

```sh
uv run python utils/filter_active_repos.py \
  outputs/skill_md_scan_results_found.csv \
  -o outputs/skill_md_scan_results_found_filtered.csv
```

**Artifact produced:** `outputs/skill_md_scan_results_found_filtered.csv` → used as `data/skill_only_scan/skill_repositories.csv` — the final shortlist of active, non-forked repositories confirmed to contain `SKILL.md`.

---

### Stage 3 — Extract full skill artifacts

Download the skill folder for each confirmed repository and compute per-skill file metrics. This is both a scraping step and a preprocessing step: it re-fetches the pinned repository tree, finds every `SKILL.md` instance, downloads the containing skill folder, downloads ACF files into an `ACF/` subfolder, and writes one dataset row per skill instance.

```sh
uv run python src/generate_dataset.py \
  --found-csv outputs/skill_md_scan_results_found_filtered.csv \
  --out-csv outputs/full_skills_instances.csv \
  --raw-data-dir outputs/raw_data \
  --resume
```

Average runtime: ~14 repos/minute.

What the script does:

- Deduplicates the found CSV by `repo`, so each repository tree is fetched once even if multiple scan rows exist.
- Prefers `commit_sha` from Stage 2, falling back to `default_branch` for older inputs.
- Calls `GET /repos/{owner}/{repo}/git/trees/{ref}?recursive=1` and treats truncated trees as retryable failures.
- Finds all exact-case `SKILL.md` blobs, groups files by the skill parent folder, and computes `references/`, `assets/`, `scripts/`, and `other` file counts.
- Writes raw files under `outputs/raw_data/<Language>/<owner>__<repo>/<skill-folder>/`.
- Uses `root/` as the local folder name for root-level skills and sanitizes path components for Windows compatibility.
- Writes `metadata.json` only after at least one skill is found, so zero-skill false negatives are retried on later `--resume` runs.
- Applies the blacklist and relevance/name filters before processing unless `--no-name-filter` is passed.

Useful examples:

```sh
# Recommended input after active-repo filtering.
uv run python src/generate_dataset.py \
  --found-csv outputs/skill_md_scan_results_found_filtered.csv \
  --out-csv outputs/full_skills_instances.csv \
  --raw-data-dir outputs/raw_data \
  --resume \
  --concurrency 1

# Disable the repo-name relevance filter, but still honor blacklist.txt.
uv run python src/generate_dataset.py \
  --found-csv outputs/skill_md_scan_results_found_filtered.csv \
  --out-csv outputs/full_skills_instances_no_name_filter.csv \
  --raw-data-dir outputs/raw_data_no_name_filter \
  --no-name-filter

# Add extra exclusion words on top of relevance_terms.txt.
uv run python src/generate_dataset.py \
  --found-csv outputs/skill_md_scan_results_found_filtered.csv \
  --out-csv outputs/full_skills_instances.csv \
  --raw-data-dir outputs/raw_data \
  --name-filter-words demo,template,starter
```

Important flags:

- `--found-csv PATH` is the found-repository input, usually the Stage 2.5 filtered CSV.
- `--out-csv PATH` receives one row per downloaded `SKILL.md` instance.
- `--raw-data-dir PATH` receives downloaded skill folders and per-repo `metadata.json`.
- `--match-name NAME` changes the exact basename used to find skill files in the tree.
- `--blacklist PATH` excludes listed repositories.
- `--relevance-terms PATH` supplies repo-name exclusion terms; defaults to `relevance_terms.txt`.
- `--name-filter-words WORDS` appends comma-separated exclusion terms.
- `--no-name-filter` disables relevance/name filtering.
- `--name-filter-log PATH` and `--failures-log PATH` override the audit log paths.
- `--resume` skips repos already present in `--out-csv` or successfully represented by `metadata.json`.
- `--concurrency N` controls tree/blob worker threads; the default is conservative (`1`).

Stage 3 writes `outputs/processing_failures.tsv` so repos missing from `full_skills_instances.csv` can be distinguished as `tree_fetch_failed`, `tree_truncated`, `zero_skills_found`, or `exception`.

**Artifacts produced:**

| File/Directory | Description |
|---|---|
| `data/skill_files/full_skills.csv` | Per-skill instance metrics (one row per `SKILL.md` found) |
| `outputs/raw_data/<Language>/<owner>__<repo>/` | Downloaded skill folder trees, one subdirectory per matched repository |
| `outputs/processing_failures.tsv` | Repos that produced no dataset rows and the reason |
| `outputs/name_filtered_repos.tsv` | Repos skipped by the shared name filter |

> **Full dataset on Zenodo:** The `outputs/raw_data/` tree and `data/skill_files/full_skills.csv` are large. The complete archive is available at the [Zenodo record](#dataset) above.

---

### Optional enrichment steps

**Step 3.5 — Enrich with contributor counts** (required for contributor-count figures in RQ1):

```sh
uv run python src/enrich_scan_contributors.py \
  --scan-csv outputs/skill_md_scan_results.csv \
  --out-csv outputs/skill_md_scan_results_with_contributors.csv \
  --resume \
  --concurrency 1
```

This script reads a scan CSV, fetches `/contributors?per_page=1&anon=1` for rows whose `contributors` value is missing, estimates the contributor count from the pagination `Link` header, and writes checkpoints every 100 completed rows. Use `--max-repos N` for a dry run, `--concurrency N` to control worker threads, and `--github-tokens` to override environment tokens.

**Artifact produced:** `outputs/skill_md_scan_results_with_contributors.csv`

---

**Step 3.6 — Fetch GitHub repo metadata and READMEs** (Python repositories only by default):

```sh
uv run python src/fetch_repo_metadata_readmes.py \
  --input-csv outputs/full_skills_instances.csv \
  --out-csv outputs/repo_metadata_readmes/repo_metadata.csv \
  --readme-dir outputs/repo_metadata_readmes/readmes \
  --resume
```

Pass `--all-languages` to collect metadata for every language. **Artifact produced:** `outputs/repo_metadata_readmes/repo_metadata.csv` and per-repo README files under `outputs/repo_metadata_readmes/readmes/`.

Useful flags: `--repo-column`, `--language-column`, and `--language` select rows from the input CSV; `--resume` skips repos with successful metadata rows; `--max-repos` limits pending work; `--concurrency` controls GitHub fetch workers.

---

**Step 3.7 — Enrich with extended ACF columns**

If `outputs/skill_md_scan_results_with_contributors.csv` only contains `has_CLAUDE`, `has_AGENTS`, and `has_COPILOT`, add `has_CURSORRULES_MD`, `has_INSTRUCTIONS_MD`, and `has_GEMINI` using the GitHub Contents API, pinned to each repo's commit SHA:

```sh
uv run python src/enrich_extended_acf_columns.py
```

By default this reads `data/skill_only_scan/known_skill_repos.csv`, checks `.cursorrules.md`, `.instructions.md`, and `GEMINI.md` at each repo's pinned `acf_ref`/`commit_sha`, and merges those flags into `outputs/skill_md_scan_results_with_contributors.csv`. If that legacy input file is not present, pass `--input-known data/skill_only_scan/skill_repositories.csv` or another found-repo CSV with refs. Useful flags: `--input-known`, `--merge-into`, `--out-skill-only`, `--out-merged`, `--concurrency`, and `--dedupe-only`.

**Artifacts produced:** `outputs/skill_md_scan_results_skill_only_new_acfs.csv` and the merged `outputs/skill_md_scan_results_with_contributors_extended.csv`.

---

## RQ1 — Prevalence and adoption analysis

RQ1 asks how prevalent `SKILL.md` is across the sampled repository population and how adoption varies by language, repository scale, age, visibility, maintainer-readiness signals, and co-occurring agent configuration files (ACFs). The main wrapper is `src/rq1/analyze_metadata.py`; individual `src/rq1/fig*.py` and `src/rq1/table*.py` modules generate one artifact family each, while `src/rq1/common.py` handles shared CSV loading, filtering, plotting style, and missing-data notes.

**Step 4 — Build the RQ1 prevalence baseline (full population × SKILL.md found flag):**

```sh
uv run python utils/build_rq1_scan_baseline_skill.py \
  --population-csv data/data_after_relevance_filter/data_after_filter.csv \
  --skill-csv data/skill_only_scan/skill_repositories.csv \
  --out-csv outputs/rq1/rq1_scan_relevance_baseline_x_skill_only.csv
```

This merges the full relevance-filtered population (denominator, ~157 k repos) with the SKILL.md-found shortlist (numerator, ~3 500 repos) into a single CSV where `found=True/False` drives all prevalence rate calculations.

**Step 5 — Run all RQ1 figures and tables:**

```sh
uv run python src/rq1/analyze_metadata.py \
  --scan-csv outputs/rq1/rq1_scan_relevance_baseline_x_skill_only.csv \
  --acf-scan-csv data/skill_only_scan/skill_repositories.csv \
  --instances-csv data/skill_files/full_skills.csv \
  --out-dir outputs/rq1 \
  --format png \
  --dpi 300
```

- `--scan-csv` is the full-population baseline and drives all prevalence and ecosystem figures.
- `--acf-scan-csv` is the SKILL-only shortlist and drives all ACF co-occurrence figures.
- `--instances-csv` drives skill-file distribution and richness figures.
- `--blacklist`, `--relevance-terms`, `--name-filter-words`, and `--no-name-filter` mirror the preprocessing filters for analysis inputs.
- `--screening-decisions` and `--screening-mode {provisional,final}` optionally apply repo-level manual screening decisions before plotting.
- `--format {png,pdf,svg}` and `--dpi N` control figure output.
- If contributor enrichment was skipped, the wrapper still runs and writes a note file explaining that the contributor-count figure could not be generated.

Code/file map:

- `src/rq1/analyze_metadata.py` orchestrates all RQ1 plots and tables.
- `src/rq1/common.py` normalizes booleans/numerics/dates, aggregates skill instances to repos, merges scan metadata, applies blacklist/name/screening filters, and writes missing-data notes.
- `src/rq1/fig1_prevalence_by_language.py` through `fig14_presence_by_project_age.py` cover prevalence, placement, temporal, topic, richness, license, maturity, contributor, size, and age views.
- `src/rq1/acf_environment_analysis.py`, `fig21_scale_visibility_collaboration_age.py`, and `fig22_acf_intersections_language_heatmap.py` cover the extended ACF/ecosystem analyses.
- `src/rq1/skill_file_distribution.py` is a smaller wrapper for skill-file-count tables/figures.

**Artifacts produced in `outputs/rq1/`:**

| Artifact | Description |
|---|---|
| `fig1_prevalence_by_language.png` | SKILL.md prevalence rate by primary language |
| `fig2_prevalence_by_size_stars.png` | Prevalence by repository size and star count |
| `fig3_acf_cooccurrence.png` | ACF co-occurrence bar chart |
| `fig4_acf_pairwise_heatmap.png` | ACF pairwise Jaccard heatmap |
| `fig5_placement_patterns.png` | SKILL.md placement patterns within repos |
| `fig6a_adoption_over_time.png` / `fig6b_prevalence_rate_over_time.png` | Adoption trend over time |
| `fig7_topic_analysis.png` | GitHub topic analysis |
| `fig8_skill_richness.png` | Skill richness (count of SKILL.md files per repo) |
| `fig8b_stars_vs_skill_count.png` | Relationship between stars and number of skill files |
| `fig9_license_distribution.png` | License distribution |
| `fig10_language_ecosystem.png` | Language ecosystem breakdown |
| `fig11_project_maturity.png` / `fig11_skill_files_per_repo.png` | Project maturity and skill-file distribution |
| `fig12_presence_by_contributor_count.png` | Presence rate by contributor count |
| `fig13_presence_by_project_size.png` | Presence rate by project size |
| `fig14_presence_by_project_age.png` | Presence rate by project age |
| `fig15_acf_prevalence_by_language.png` | ACF prevalence broken down by language |
| `fig16_acf_pairwise_jaccard_heatmap.png` | ACF pairwise Jaccard (extended ACF set) |
| `fig17_acf_conditional_probability_heatmap.png` | ACF conditional probability heatmap |
| `fig18_acf_combination_distribution.png` | ACF combination distribution |
| `fig19_acf_count_distribution.png` | Distribution of ACF count per repo |
| `fig20_acf_any_multi_by_language.png` | Any/multiple ACF presence by language |
| `fig21_scale_visibility_collaboration_age.png` | Scale, visibility, collaboration, and age analysis |
| `fig22_acf_intersections_language_heatmap.png` | ACF intersection language heatmap |
| `table*.csv` | Corresponding summary tables for each figure |

---

## RQ2 — Content analysis

RQ2 asks what `SKILL.md` files contain and what terms characterize their declared names/descriptions. It starts from the Stage 3 `raw_data` tree, normalizes each `SKILL.md` into JSONL, computes corpus statistics, then runs TF-IDF over frontmatter `name` and `description` fields.

**Step 1 — Collect SKILL.md documents:**

```sh
uv run python src/rq2/collect_skill_documents.py \
  --raw-data-dir outputs/raw_data \
  --out-jsonl outputs/rq2/skill_documents.jsonl \
  --out-stats-json outputs/rq2/skill_documents_stats.json
```

**Artifact produced:** `outputs/rq2/skill_documents.jsonl` (normalized SKILL.md content per document) and `outputs/rq2/skill_documents_stats.json` (corpus-level statistics).

`src/rq2/collect_skill_documents.py` records language, repo folder, relative path, raw text, Markdown structure metrics, code-block counts, file/URL references, and reference-type summaries. Use `--raw-data-dir`, `--out-jsonl`, `--out-stats-json`, and `--log-level` to control inputs and outputs.

---

**Step 2 — Run TF-IDF analysis:**

```sh
uv run python src/rq2/analyze_tfidf_sklearn.py \
  --input outputs/rq2/skill_documents.jsonl \
  --out-global outputs/rq2/tfidf_sklearn_top_terms_global.csv \
  --out-global-unigrams outputs/rq2/tfidf_sklearn_top_terms_global_unigrams.csv \
  --out-global-bigrams outputs/rq2/tfidf_sklearn_top_terms_global_bigrams.csv \
  --out-per-doc outputs/rq2/tfidf_sklearn_top_terms_per_document.csv \
  --out-summary outputs/rq2/tfidf_sklearn_summary.json
```

`src/rq2/analyze_tfidf_sklearn.py` extracts frontmatter `name` and `description`, lowercases text, removes English plus project-specific stopwords, builds unigram/bigram TF-IDF features, and writes global and per-document ranked terms. Useful tuning flags are `--max-features`, `--min-df`, `--max-df`, `--top-k-global`, and `--top-k-per-doc`.

**Step 3 — Plot TF-IDF top terms:**

```sh
uv run python src/rq2/create_diagrams.py \
  --unigrams-csv outputs/rq2/tfidf_sklearn_top_terms_global_unigrams.csv \
  --bigrams-csv outputs/rq2/tfidf_sklearn_top_terms_global_bigrams.csv \
  --out-combined-image outputs/rq2/top10_tfidf_unigrams_bigrams_combined.png
```

Use `--top-k N` to change the number of terms plotted, `--skip-separate` to write only the combined chart, and `--out-unigrams-image` / `--out-bigrams-image` to override the separate bar-chart paths.

**Artifacts produced in `outputs/rq2/`:**

| File | Description |
|---|---|
| `tfidf_sklearn_top_terms_global.csv` | Top global TF-IDF terms (unigrams + bigrams) |
| `tfidf_sklearn_top_terms_global_unigrams.csv` | Top global unigrams |
| `tfidf_sklearn_top_terms_global_bigrams.csv` | Top global bigrams |
| `tfidf_sklearn_top_terms_per_document.csv` | Top terms per SKILL.md document |
| `tfidf_sklearn_summary.json` | Corpus-level TF-IDF summary statistics |
| `skill_documents_stats.json` | Raw corpus statistics |
| `top10_unigrams_tfidf_barh.png` | Horizontal bar chart of top unigram TF-IDF terms |
| `top10_bigrams_tfidf_barh.png` | Horizontal bar chart of top bigram TF-IDF terms |
| `top10_tfidf_unigrams_bigrams_combined.png` | Two-panel unigram/bigram TF-IDF chart |

---

## RQ3 — Manual labeling and category analysis

RQ3 involves reproducible random sampling, manual labeling by two annotators, inter-rater agreement computation, and analysis of structural and SDLC-task patterns in SKILL.md files.

At a high level, RQ3 uses `src/rq3/retrieve_language_metadata.py`, `generate_language_sample.py`, and `generate_labeling_samples.py` to construct the labeling sample; `calculate_agreement.py`, `process_label_exports.py`, and `analyze_processed_labels.py` to normalize and summarize manual labels; and `generate_processed_analysis_plots.py`, `build_python_all_dataset.py`, `generate_python_all_analysis.py`, and `fig1_prevalence_panels.py` to produce figures and tables.

### Step 1 — Generate per-language metadata summaries

Walks `outputs/raw_data/` and writes one `<Language>_summary.json` per language to `outputs/rq3/`:

```sh
uv run python src/rq3/retrieve_language_metadata.py \
  --root outputs/raw_data \
  --out-dir outputs/rq3
```

**Artifacts produced:** `outputs/rq3/<Language>_summary.json` for each language (C, C#, C++, Go, Java, JavaScript, PHP, Python, Rust, TypeScript).

---

### Step 2 — Draw a reproducible random sample

Randomly samples `SKILL.md` files from a language subfolder of `raw_data` and copies them — preserving the original relative path structure — into `outputs/rq3/language_sample/<Language>/`. Run once per language:

```sh
# Python
uv run python src/rq3/generate_language_sample.py \
  --root outputs/raw_data/Python \
  --n 370 --seed 42 \
  --allowed-repos-csv data/data_after_relevance_filter/data_after_filter.csv \
  --allowed-main-language Python \
  --clean-out-dir \
  --out-dir outputs/rq3/language_sample/Python

# TypeScript
uv run python src/rq3/generate_language_sample.py \
  --root outputs/raw_data/TypeScript \
  --n 372 --seed 42 \
  --out-dir outputs/rq3/language_sample/TypeScript
```

`--seed` ensures the sample is reproducible across machines.

Useful flags: `--allowed-repos-csv` restricts sampled files to repos listed in a SEART-style CSV, `--allowed-main-language` filters that CSV by `mainLanguage`, and `--clean-out-dir` removes stale copies before writing.

**Artifact produced:** `outputs/rq3/language_sample/<Language>/` — sampled SKILL.md files mirroring raw_data paths.

---

### Step 3 — Split sample into labeling buckets

Distributes the sampled files into three subfolders under `outputs/rq3/labeling_samples/<Language>/`:

| Subfolder | Contents |
|---|---|
| `both/` | Shared overlap set — seen by **both** labelers (used to compute inter-rater agreement) |
| `A/` | Items assigned exclusively to labeler A |
| `B/` | Items assigned exclusively to labeler B |

```sh
# Python
uv run python src/rq3/generate_labeling_samples.py \
  --root outputs/rq3/language_sample/Python \
  --both 56 --A 157 --B 157 \
  --out-dir outputs/rq3/labeling_samples/Python \
  --seed 42

# TypeScript
uv run python src/rq3/generate_labeling_samples.py \
  --root outputs/rq3/language_sample/TypeScript \
  --both 56 --A 158 --B 158 \
  --out-dir outputs/rq3/labeling_samples/TypeScript \
  --seed 42
```

**Artifact produced:** `outputs/rq3/labeling_samples/<Language>/{both,A,B}/`

---

### Step 4 — Compute inter-rater agreement

Calculate per-label Cohen's kappa between two annotators on the shared `both` set:

```sh
uv run python src/rq3/calculate_agreement.py \
  outputs/rq3/results/2026-04-19_CY_Final_Labels_Both_Python.json \
  outputs/rq3/results/2026-04-19_MV_Final_Labels_Both_Python.json \
  --output outputs/rq3/results/processed/kappa_CY_vs_MV_Both_Python.json
```

**Artifact produced:** `outputs/rq3/results/processed/kappa_<comparison>.json`. If `--output` is omitted, `calculate_agreement.py` writes next to the first input file; copy or rerun with `--output` so Step 6 can find `kappa_*.json` in `outputs/rq3/results/processed/`.

---

### Step 5 — Process and merge label exports

Convert raw label exports from the annotation tool into a normalized format and compute aggregate statistics:

```sh
uv run python src/rq3/process_label_exports.py \
  --results-dir outputs/rq3/results \
  --output-dir outputs/rq3/results/processed
```

`process_label_exports.py` normalizes label names and collapses out-of-scope, wrong-language, and agent-skill exclusions to a single filter label so downstream analysis treats filtered documents consistently.

```sh
uv run python src/rq3/analyze_processed_labels.py \
  --input-dir outputs/rq3/results/processed
```

**Artifacts produced:** `outputs/rq3/results/processed/processed_label_statistics.json` and `outputs/rq3/results/processed/processed_label_statistics.md`

---

### Step 6 — Generate RQ3 analysis plots (both/A/B labeling set)

```sh
uv run python src/rq3/generate_processed_analysis_plots.py \
  --processed-dir outputs/rq3/results/processed \
  --out-dir outputs/rq3/analysis
```

**Artifacts produced in `outputs/rq3/analysis/`:**

| File | Description |
|---|---|
| `fig_rq3_agreement_latest_python_both.png` | Inter-rater agreement overview |
| `fig_rq3_agreement_python_both_pairs.png` | Per-pair agreement comparison |
| `fig_rq3_filter_sources_latest_python_both.png` | Sources of filtered (excluded) documents |
| `fig_rq3_instruction_distribution_latest_python_both.png` | Instruction-type distribution |
| `fig_rq3_instruction_stage_heatmap_latest_python_both.png` | Instruction type × SDLC stage co-occurrence |
| `fig_rq3_retained_vs_filtered.png` | Retained vs. filtered document counts |
| `fig_rq3_sdlc_stage_distribution_latest_python_both.png` | SDLC stage distribution |
| `table_rq3_*.csv` | Corresponding summary tables |
| `rq3_processed_analysis.md` | Narrative analysis brief |

---

### Step 7 — Generate full Python dataset analysis

Build the combined processed Python dataset, then generate structural and SDLC-task analysis:

```sh
uv run python src/rq3/build_python_all_dataset.py \
  --processed-dir outputs/rq3/results/processed \
  --a-file 2026-04-19_CY_Final_Labels_A_Python.json \
  --b-file 2026-04-19_MV_Final_Labels_B_Python.json \
  --both-file 2026-04-19_CY_Final_Labels_Both_Python.json
```

Then run:

```sh
uv run python src/rq3/generate_python_all_analysis.py \
  --processed-dir outputs/rq3/results/processed \
  --out-dir outputs/rq3/analysis/python_all
```

For the per-repo skill-count breakdown listed below, run the separate helper:

```sh
uv run python src/rq3/extract_python_all_repo_skill_counts.py \
  --python-all outputs/rq3/results/processed/Python_All.json \
  --raw-results-dir outputs/rq3/results \
  --instances-csv outputs/full_skills_instances.csv \
  --out-csv outputs/rq3/analysis/python_all/table_python_all_repo_skill_counts.csv
```

**Artifacts produced in `outputs/rq3/analysis/python_all/`:**

| File | Description |
|---|---|
| `fig_rq3_python_all_sdlc_tasks.png` | SDLC task distribution across all Python SKILL.md files |
| `fig_rq3_python_all_sdlc_tasks_comparison.png` | SDLC task comparison (both vs. full set) |
| `fig_rq3_python_all_structural_patterns.png` | Structural pattern distribution |
| `fig_rq3_python_all_structural_patterns_comparison.png` | Structural pattern comparison (both vs. full set) |
| `fig_rq3_python_all_filter_sources.png` | Filter source breakdown |
| `fig_rq3_python_all_retained_vs_filtered.png` | Retained vs. filtered counts |
| `fig_rq3_python_all_instruction_stage_heatmap.png` | Instruction type × SDLC stage heatmap |
| `table_rq3_python_all_sdlc_tasks.csv` | SDLC task frequency table |
| `table_rq3_python_all_structural_patterns.csv` | Structural pattern frequency table |
| `table_rq3_python_all_instruction_stage_matrix.csv` | Instruction × SDLC co-occurrence matrix |
| `table_rq3_python_all_source_summary.csv` | Source file summary |
| `table_python_all_repo_skill_counts.csv` | Per-repo skill count breakdown from `extract_python_all_repo_skill_counts.py` |
| `rq3_python_all_analysis.md` | Narrative analysis brief |

---

### Step 8 — Generate RQ3 Figure 1 (two-panel prevalence chart)

```sh
uv run python src/rq3/fig1_prevalence_panels.py \
  --sdlc-table outputs/rq3/analysis/python_all/table_rq3_python_all_sdlc_tasks.csv \
  --structural-table outputs/rq3/analysis/python_all/table_rq3_python_all_structural_patterns.csv \
  --out outputs/rq3/analysis/fig1.png
```

**Artifact produced:** `outputs/rq3/analysis/fig1.png`

This final figure is a compact two-panel chart for paper/report use: panel (a) plots Python All SDLC task prevalence, and panel (b) plots structural instruction-pattern prevalence.

---

### RQ3 module structure

```
src/rq3/
  retrieve_language_metadata.py            # Step 1: per-language JSON summaries from raw_data
  generate_language_sample.py              # Step 2: random per-language sample from raw_data
  generate_labeling_samples.py             # Step 3: split sample into both/A/B labeling buckets
  calculate_agreement.py                   # Step 4: Cohen's kappa between two annotators
  process_label_exports.py                 # Step 5: normalize/collapse raw label exports
  analyze_processed_labels.py              # Step 5: aggregate statistics for processed exports
  generate_processed_analysis_plots.py     # Step 6: plots for the both/A/B labeling sets
  build_python_all_dataset.py              # Step 7: merge processed A/B/Both exports into Python_All
  generate_python_all_analysis.py          # Step 7: full Python dataset structural/SDLC analysis
  fig1_prevalence_panels.py                # Step 8: two-panel RQ3 figure 1

outputs/rq3/
  <Language>_summary.json                  # per-language metadata summary (Step 1)
  language_sample/                         # sampled SKILL.md files, mirroring raw_data paths (Step 2)
  labeling_samples/                        # split into both/, A/, B/ per language (Step 3)
  results/                                 # raw and processed label exports; kappa JSONs
  results/processed/                       # normalized label exports (input to Steps 5-7)
  analysis/                                # figures and tables (Steps 6-8)
  analysis/python_all/                     # full Python dataset analysis (Step 7)
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
| `--end-date DATE` | today | Only repos pushed on or before `YYYY-MM-DD`; freezes the crawl horizon |
| `--languages LANG ...` | TypeScript Python C# Go C++ JavaScript Java C PHP Rust | Languages to query (space-separated) |
| `--licenses LICENSE ...` | `mit apache-2.0 bsd-3-clause bsd-2-clause` | License SPDX keys (space-separated) |
| `--resume` | off | Append to existing `--out-csv`, skipping already-written repos |
| `--github-token TOKEN` | *(env)* | Single GitHub PAT; overrides env vars |
| `--github-tokens TOKENS` | *(env)* | Comma-separated GitHub PATs for multi-token rotation |
| `--log-level LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `--skip-enrich` | off | Skip the post-search per-repo enrichment phase |
| `--enrich-only` | off | Do not search; fill missing enrichment fields in an existing `--out-csv` |
| `--enrich-concurrency N` | `4` | Worker threads for enrichment API calls |

**Rate limit note:** `/search/repositories` allows **30 requests/minute** per authenticated token and **10 requests/minute** unauthenticated (separate from the 10 req/min `/search/code` limit). With `per_page=100` and up to 10 pages per query, 40 combinations require ~400 requests at minimum — about 14 minutes with one token.

**Per-combo CSVs:** In addition to the combined `--out-csv`, one CSV per (language, license) pair is written alongside it using the naming convention `{base}_{language}_{license}.csv` (e.g. `github_search_results_typescript_mit.csv`). These files contain the same SEART-compatible schema and can be used as independent inputs to either Stage 2 scanner.

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

### `extract_skill_repos_tree.py`

Recommended Stage 2 scanner. It preserves the `extract_skill_repos.py` output schema while using git-tree REST calls instead of Code Search.

| Flag | Default | Description |
|---|---|---|
| `--seart-dir PATH` | *(required)* | Directory containing SEART CSV exports (searched recursively) |
| `--out-csv PATH` | *(required)* | Output results CSV path |
| `--shortlist-csv PATH` | *(empty)* | Optional second CSV containing only `found=true` rows |
| `--match-name NAME` | `SKILL.md` | Exact basename to detect in git tree paths |
| `--max-repos N` | `0` (no limit) | Process at most N repositories |
| `--blacklist PATH` | `blacklist.txt` | Path to a blacklist file (`owner/repo` per line, `#` comments supported) |
| `--resume` | off | Skip repos already present in `--out-csv`; validates existing headers first |
| `--include-negative-results` | off | Compatibility no-op; all rows are always written to `--out-csv` |
| `--concurrency N` | `4` | Number of parallel worker threads |
| `--github-token TOKEN` | *(env)* | Single GitHub token; overrides env vars |
| `--github-tokens TOKENS` | *(env)* | Comma-separated GitHub tokens for multi-token rotation |
| `--cache-dir PATH` | `outputs/cache/tree_scan` | Directory for cached tree responses |
| `--cache-mode MODE` | `read-write` | Cache behavior: `read-write`, `read-only`, or `off` |
| `--fallback MODE` | `walk-tree` | Truncated recursive tree behavior: `walk-tree` or `none` |
| `--log-level LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

Tree-first request model:

- Common case: one commit-resolution core call plus one recursive tree core call per repo.
- `truncated=true` fallback: additional non-recursive tree calls for each walked subtree.
- Code Search calls: zero.
- Stage 3 remains compatible with the produced `*_found.csv` and may still refetch trees unless it is optimized separately.

---

### `extract_skill_repos.py`

Legacy Stage 2 scanner retained for reproducing older Code Search based runs.

| Flag | Default | Description |
|---|---|---|
| `--seart-dir PATH` | *(required)* | Directory containing SEART CSV exports (searched recursively) |
| `--out-csv PATH` | *(required)* | Output results CSV path |
| `--shortlist-csv PATH` | *(empty)* | Optional second CSV containing only `found=true` rows |
| `--match-name NAME` | `SKILL.md` | Filename to search for via code search |
| `--max-repos N` | `0` (no limit) | Process at most N repositories |
| `--blacklist PATH` | `blacklist.txt` | Path to a blacklist file (`owner/repo` per line, `#` comments supported) |
| `--resume` | off | Skip repos already present in `--out-csv` |
| `--include-negative-results` | off | Compatibility no-op; all rows are always written to `--out-csv` |
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
| `--relevance-terms PATH` | `relevance_terms.txt` | Repo-name exclusion terms used by the relevance/name filter |
| `--name-filter-words WORDS` | *(empty)* | Comma-separated extra repo-name filter words added to the shared built-in list |
| `--no-name-filter` | off | Disable the relevance/name filter (blacklist still applies) |
| `--name-filter-log PATH` | `<out dir>/name_filtered_repos.tsv` | TSV recording repos skipped by the name filter |
| `--failures-log PATH` | `<out dir>/processing_failures.tsv` | TSV recording repos that produced no dataset rows because of tree or processing failures |
| `--resume` | off | Skip repos already present in `--out-csv` or with successful metadata.json |
| `--concurrency N` | `1` | Number of parallel worker threads |
| `--github-token TOKEN` | *(env)* | Single GitHub token; overrides env vars |
| `--github-tokens TOKENS` | *(env)* | Comma-separated GitHub tokens for multi-token rotation |
| `--log-level LEVEL` | `INFO` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

Stage 3 prefers the `commit_sha` column from stage 2 when it is present. Older found CSVs without that column still work, but they fall back to `default_branch`, which is less stable for cross-run comparison.

### `enrich_scan_contributors.py`

| Flag | Default | Description |
|---|---|---|
| `--scan-csv PATH` | *(required)* | Scan CSV to enrich |
| `--out-csv PATH` | `<scan>_with_contributors.csv` | Output CSV path |
| `--resume` | off | Reuse contributor counts already present in `--out-csv` |
| `--concurrency N` | `1` | Worker threads |
| `--max-repos N` | `0` (no limit) | Process at most N missing rows |
| `--github-token TOKEN` | *(env)* | Single GitHub token override |
| `--github-tokens TOKENS` | *(env)* | Comma-separated GitHub token override |
| `--log-level LEVEL` | `INFO` | Logging verbosity |

### `fetch_repo_metadata_readmes.py`

| Flag | Default | Description |
|---|---|---|
| `--input-csv PATH` | `outputs/full_skills_instances.csv` | CSV containing repositories |
| `--repo-column NAME` | `repo` | Column with `owner/repo` identifiers |
| `--language-column NAME` | `mainLanguage` | Column used for language filtering |
| `--language LANG` | `Python` | Language retained unless `--all-languages` is passed |
| `--all-languages` | off | Disable Python-only filtering |
| `--out-csv PATH` | `outputs/repo_metadata_readmes/repo_metadata.csv` | Metadata output CSV |
| `--readme-dir PATH` | `outputs/repo_metadata_readmes/readmes` | README text output directory |
| `--resume` | off | Skip repos already fetched successfully |
| `--concurrency N` | `4` | Worker threads |
| `--max-repos N` | `0` (no limit) | Limit pending repos |
| `--github-token TOKEN` / `--github-tokens TOKENS` | *(env)* | GitHub token overrides |
| `--log-level LEVEL` | `INFO` | Logging verbosity |

### `enrich_extended_acf_columns.py`

| Flag | Default | Description |
|---|---|---|
| `--input-known PATH` | `data/skill_only_scan/known_skill_repos.csv` | Skill-only input with found repos and refs; pass `data/skill_only_scan/skill_repositories.csv` if the legacy default is absent |
| `--merge-into PATH` | `outputs/skill_md_scan_results_with_contributors.csv` | Full scan CSV to merge into |
| `--out-skill-only PATH` | `outputs/skill_md_scan_results_skill_only_new_acfs.csv` | Enriched skill-only scan output |
| `--out-merged PATH` | `outputs/skill_md_scan_results_with_contributors_extended.csv` | Full merged output |
| `--github-token TOKEN` / `--github-tokens TOKENS` | *(env)* | GitHub token overrides |
| `--concurrency N` | `16` | Contents API workers |
| `--dedupe-only` | off | Deduplicate existing `--out-skill-only` without GitHub API calls |
| `--log-level LEVEL` | `INFO` | Logging verbosity |

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

`skill_md_scan_results.csv` (and the category-split `_found`, `_not_found`, `_errors`, `_filtered` variants) share these columns:

| Column | Description |
|---|---|
| `repo` | `owner/repo` canonical identifier |
| `source_csv` | Originating SEART filename, or `MULTIPLE` |
| `found` | `true` or `false` |
| `match_name` | Filename searched for (e.g. `SKILL.md`) |
| `match_path` | Repo-relative path of the matched file (e.g. `/skills/foo/SKILL.md`) |
| `default_branch` | Default branch, sourced from SEART data |
| `seart_default_branch` | Branch hint from SEART data, or `HEAD` when unknown |
| `commit_sha` | Commit SHA pinned at the scanned branch tip for use by stage 3 |
| `acf_ref` | Actual ref used for ACF Contents API checks, usually `commit_sha` |
| `match_url` | HTML URL to the file on GitHub |
| `match_sha` | Git blob SHA of the matched file |
| `match_size_bytes` | File size in bytes when fetched from the Contents API |
| `scan_method` | Always `code_search` |
| `http_status` | HTTP status code from the API call that determined the final scan outcome |
| `error_type` | `none`, `auth`, `rate_limited`, `network`, `invalid_repo`, `not_found`, reserved `filtered`, or `other` |
| `error_message` | Short error detail (never contains secrets) |
| `acf_error_type` | Error type from ACF-only Contents API checks, separate from primary scan status |
| `acf_error_message` | Short ACF error detail |
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

The recommended `src/extract_skill_repos_tree.py` scanner uses only core REST API calls and does not call Code Search.

Each repository costs **two core REST calls** in the common case:

1. **Commit resolution** — `GET /repos/{owner}/{repo}/commits/{default_branch_or_HEAD}` pins the scan to a commit SHA.
2. **Recursive git tree** — `GET /repos/{owner}/{repo}/git/trees/{commit_sha}?recursive=1`. Local path scanning finds `SKILL.md`, ACF files, and maintainer-readiness files from returned blob metadata.

Repo metadata (`default_branch`, `stars`, `fork`, `archived`) is read directly from SEART CSV data — no separate metadata API call is made.

If GitHub returns `truncated=true` for the recursive tree, the scanner records fallback usage as `scan_method=tree_walk` and walks non-recursive trees with:

```text
GET /repos/{owner}/{repo}/git/trees/{tree_sha}
```

Passing `--fallback none` records truncated trees as errors instead of risking false negatives. The legacy `src/extract_skill_repos.py` scanner still uses `GET /search/code` plus Community Profile and contents calls for older-method reruns.

### API rate limits

The tree-first scanner uses the core REST API limit, typically **5,000 requests/hour per authenticated token**, and avoids the separate **10 requests/minute/token** Code Search limit. The older `extract_skill_repos.py` path still uses that Code Search bucket.

| Tokens | Core REST quota | Approx. tree-first repos/hr before fallback/cache |
|---|---:|---:|
| 1 | 5,000 req/hr | ~2,500 repos/hr |
| 3 | 15,000 req/hr | ~7,500 repos/hr |

These estimates assume two core calls per uncached repository: commit resolution plus recursive tree. Cache hits reduce calls; truncated-tree fallback increases calls for those repositories. The legacy Code Search scanner remains capped by the separate 10 req/min/token Code Search bucket.

### Rate limit handling

Rate limiting is handled automatically by the `github_client` module:

- Each token's remaining quota is tracked from `X-RateLimit-Remaining` and `X-RateLimit-Reset` response headers.
- On each request, the token with the highest remaining quota is selected.
- When a token is exhausted, the pool immediately rotates to the next available token.
- When all tokens are exhausted, the pool sleeps until the earliest reset time (plus a 2-second buffer) and resumes automatically — the scan never aborts due to rate limiting.

### Module structure

```
src/
  search_github_repos.py          # Stage 1: scrape repo list from GitHub API
  extract_skill_repos_tree.py     # Stage 2: scan repos for SKILL.md via git trees
  extract_skill_repos.py          # Legacy Stage 2: scan repos via code search
  generate_dataset.py             # Stage 3: download skill folders, compute file metrics
  enrich_scan_contributors.py     # Optional Step 3.5: populate contributor counts in the scan CSV
  fetch_repo_metadata_readmes.py  # Optional Step 3.6: fetch repo metadata and READMEs
  enrich_extended_acf_columns.py  # Optional Step 3.7: add extended ACF columns
  rq1/
    analyze_metadata.py           # Wrapper: run all RQ1 figures and tables
    skill_file_distribution.py    # Wrapper: skill-file distribution outputs
    common.py                     # Shared RQ1 data loading, plotting, and helper utilities
    fig*.py / table*.py           # One script per RQ1 artifact (figure/table pair where applicable)
  rq2/
    collect_skill_documents.py    # RQ2 Step 1: collect and normalize SKILL.md documents
    analyze_tfidf_sklearn.py      # RQ2 Step 2: TF-IDF analysis on frontmatter
    create_diagrams.py            # RQ2 Step 3: TF-IDF unigram/bigram charts
  rq3/
    retrieve_language_metadata.py            # RQ3 Step 1: per-language summaries
    generate_language_sample.py              # RQ3 Step 2: reproducible random sample
    generate_labeling_samples.py             # RQ3 Step 3: both/A/B bucket split
    calculate_agreement.py                   # RQ3 Step 4: Cohen's kappa
    process_label_exports.py                 # RQ3 Step 5: normalize/collapse raw label exports
    analyze_processed_labels.py              # RQ3 Step 5: aggregate label statistics
    generate_processed_analysis_plots.py     # RQ3 Step 6: analysis plots (both/A/B set)
    build_python_all_dataset.py              # RQ3 Step 7: merge processed A/B/Both exports
    generate_python_all_analysis.py          # RQ3 Step 7: full Python dataset analysis
    fig1_prevalence_panels.py                # RQ3 Step 8: two-panel figure 1
  github_client/
    __init__.py                   # public re-exports
    token_pool.py                 # TokenBucket, TokenPool, load_tokens_from_env
    client.py                     # GitHubClient (HTTP + pool integration)

data/
  seart_csvs/                     # Stage 1 output: per-language/license CSVs + combined CSV
  skill_only_scan/
    skill_repositories.csv        # Stage 2.5 output: active non-forked repos with SKILL.md
  skill_files/
    full_skills.csv               # Stage 3 output: per-skill instance metrics

outputs/
  skill_md_scan_results.csv       # Stage 2: all scanned repos
  skill_md_scan_results_found.csv # Stage 2: repos where SKILL.md was found
  skill_md_scan_results_not_found.csv
  skill_md_scan_results_errors.csv
  skill_md_scan_results_filtered.csv
  processing_failures.tsv         # Stage 3: repos with no dataset rows and why
  name_filtered_repos.tsv         # Stage 3: repos skipped by the shared name filter
  full_skills_instances.csv       # Stage 3: per-skill instance metrics
  raw_data/                       # Stage 3: downloaded skill folder contents
  rq1/                            # RQ1 figures and tables
  rq2/                            # RQ2 content analysis outputs
  rq3/                            # RQ3 labeling, agreement, and analysis outputs
```
