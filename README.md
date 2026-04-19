# msr-skills-md

Mine GitHub repositories for `SKILL.md` files. Given a list of repositories (from SEART CSV exports or scraped directly from the GitHub API), the pipeline scans each repository via the GitHub Code Search API and writes a results CSV recording whether the target file was found, plus metadata about each repo.

Designed for read-only, resumable, rate-limit-aware bulk scanning over large repository sets.

Stage 2 records the exact commit SHA observed when a repository is matched, and stage 3 reuses that pinned ref by default so the two outputs stay comparable even if the default branch moves later.

See [`.cursor/skills/msr/SKILL.md`](.cursor/skills/msr/SKILL.md) for the full design specification.

---

## Dataset

The full replication package — including all extracted `SKILL.md` files and the skill folder contents for each matched repository — is archived on Zenodo:

> **[Zenodo record — DOI: 10.5281/zenodo.XXXXXXX]** *(placeholder — link will be updated on publication)*

The Zenodo archive contains:

- `outputs/raw_data/` — downloaded skill folder trees, one subdirectory per primary language, mirroring the layout written by Stage 3 (`generate_dataset.py`).
- `data/skill_files/full_skills.csv` — per-skill instance metrics CSV (Stage 3 output).
- `data/skill_only_scan/skill_repositories.csv` — the filtered shortlist of repositories confirmed to contain `SKILL.md`.
- `data/seart_csvs/` — the SEART-exported repository list used as the Stage 1 input.

If you only want to reproduce the RQ figures without re-running the data collection pipeline, download the Zenodo archive, place the `outputs/` and `data/` folders at the repository root, and jump directly to the [RQ reproduction steps](#rq1--prevalence-and-adoption-analysis).

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

## Data Processing Pipeline

The pipeline consists of four main stages. Each stage builds on the previous one and produces artifacts in `data/` or `outputs/`.

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

Use `search_github_repos.py` to build the initial repository list directly from the GitHub Search API. This produces a SEART-compatible CSV that feeds into the same pipeline as SEART exports:

```sh
uv run python src/search_github_repos.py \
  --out-csv data/seart_csvs/github_search_results.csv \
  --resume
```

Default criteria applied: ≥ 10 stars · MIT/Apache 2.0/BSD-3-Clause/BSD-2-Clause license · TypeScript, Python, C#, Go, C++, JavaScript, Java, C, Rust or PHP · pushed since 2025-10-16.

Average runtime: ~360 API calls across 36 language/license combinations, at 30 req/min per token — approximately 12 minutes with one token.

**Artifact produced:** `data/seart_csvs/github_search_results.csv` — one row per GitHub repository, with per-(language, license) split CSVs written alongside it.

---

### Stage 2 — Scan for SKILL.md

Scan every repository in the list for a `SKILL.md` file via the GitHub Code Search API, record community-profile flags, and pin the commit SHA for each match:

```sh
uv run python src/extract_skill_repos.py \
  --seart-dir data/seart_csvs \
  --out-csv outputs/skill_md_scan_results.csv \
  --resume
```

Average runtime: 3.65 repositories/minute/token.

The shared repo-name filter is enabled by default so stages 2 and 3 use the same inclusion rules. Pass `--no-name-filter` to disable it, or `--name-filter-words foo,bar` to append extra words.

**Artifacts produced:**

| File | Description |
|---|---|
| `outputs/skill_md_scan_results.csv` | All scanned repositories (one row per repo) |
| `outputs/skill_md_scan_results_found.csv` | Repos where `SKILL.md` was found |
| `outputs/skill_md_scan_results_not_found.csv` | Repos where `SKILL.md` was not found |
| `outputs/skill_md_scan_results_errors.csv` | Repos that produced scan errors |

---

### Stage 2.5 — Filter active repositories

Remove archived and forked repositories from the found set before downloading skill artifacts:

```sh
uv run python utils/filter_active_repos.py \
  outputs/skill_md_scan_results_found.csv \
  -o outputs/skill_md_scan_results_found_filtered.csv
```

**Artifact produced:** `outputs/skill_md_scan_results_found_filtered.csv` → used as `data/skill_only_scan/skill_repositories.csv` — the final shortlist of active, non-forked repositories confirmed to contain `SKILL.md`.

---

### Stage 3 — Extract full skill artifacts

Download the skill folder for each confirmed repository and compute per-skill file metrics:

```sh
uv run python src/generate_dataset.py \
  --found-csv outputs/skill_md_scan_results_found.csv \
  --out-csv outputs/full_skills_instances.csv \
  --raw-data-dir outputs/raw_data \
  --resume
```

Average runtime: ~14 repos/minute.

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
  --resume
```

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

---

**Step 3.7 — Enrich with extended ACF columns**

If `outputs/skill_md_scan_results_with_contributors.csv` only contains `has_CLAUDE`, `has_AGENTS`, and `has_COPILOT`, add `has_CURSORRULES_MD`, `has_INSTRUCTIONS_MD`, and `has_GEMINI` using the GitHub Contents API, pinned to each repo's commit SHA:

```sh
uv run python src/enrich_extended_acf_columns.py
```

**Artifacts produced:** `outputs/skill_md_scan_results_skill_only_new_acfs.csv` and the merged `outputs/skill_md_scan_results_with_contributors_extended.csv`.

---

## RQ1 — Prevalence and adoption analysis

**Step 4 — Run all RQ1 figures and tables:**

```sh
uv run python src/rq1/analyze_metadata.py \
  --scan-csv outputs/skill_md_scan_results_with_contributors.csv \
  --acf-scan-csv outputs/skill_md_scan_results_skill_only_new_acfs.csv \
  --instances-csv outputs/full_skills_instances.csv \
  --out-dir outputs/rq1
```

- `--scan-csv` drives all prevalence and ecosystem figures (full scan population).
- `--acf-scan-csv` drives all ACF co-occurrence figures (SKILL-only population).
- `--instances-csv` drives skill-file distribution and richness figures.
- If contributor enrichment was skipped, the wrapper still runs and writes a note file explaining that the contributor-count figure could not be generated.

**Artifacts produced in `outputs/rq1/`:**

| Artifact | Description |
|---|---|
| `fig1_prevalence_by_language.png` | SKILL.md prevalence rate by primary language |
| `fig2_prevalence_by_size_stars.png` | Prevalence by repository size and star count |
| `fig3_acf_cooccurrence.png` | ACF co-occurrence bar chart |
| `fig4_acf_pairwise_heatmap.png` | ACF pairwise Jaccard heatmap |
| `fig5_placement_patterns.png` | SKILL.md placement patterns within repos |
| `fig6_temporal_trend.png` / `fig6a_adoption_over_time.png` / `fig6b_prevalence_rate_over_time.png` | Adoption trend over time |
| `fig7_topic_analysis.png` | GitHub topic analysis |
| `fig8_skill_richness.png` | Skill richness (count of SKILL.md files per repo) |
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

**Step 1 — Collect SKILL.md documents:**

```sh
uv run python src/rq2/collect_skill_documents.py \
  --raw-data-dir outputs/raw_data \
  --out-jsonl outputs/rq2/skill_documents.jsonl \
  --out-stats-json outputs/rq2/skill_documents_stats.json
```

**Artifact produced:** `outputs/rq2/skill_documents.jsonl` (normalized SKILL.md content per document) and `outputs/rq2/skill_documents_stats.json` (corpus-level statistics).

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

**Artifacts produced in `outputs/rq2/`:**

| File | Description |
|---|---|
| `tfidf_sklearn_top_terms_global.csv` | Top global TF-IDF terms (unigrams + bigrams) |
| `tfidf_sklearn_top_terms_global_unigrams.csv` | Top global unigrams |
| `tfidf_sklearn_top_terms_global_bigrams.csv` | Top global bigrams |
| `tfidf_sklearn_top_terms_per_document.csv` | Top terms per SKILL.md document |
| `tfidf_sklearn_summary.json` | Corpus-level TF-IDF summary statistics |
| `skill_documents_stats.json` | Raw corpus statistics |
| `text_length_boxplots.png` | Text length distribution plots |

---

## RQ3 — Manual labeling and category analysis

RQ3 involves stratified random sampling, manual labeling by two annotators, inter-rater agreement computation, and analysis of structural and SDLC-task patterns in SKILL.md files.

### Step 1 — Generate per-language metadata summaries

Walks `outputs/raw_data/` and writes one `<Language>_summary.json` per language to `outputs/rq3/`:

```sh
uv run python src/rq3/retrieve_language_metadata.py \
  --root outputs/raw_data \
  --out-dir outputs/rq3
```

**Artifacts produced:** `outputs/rq3/<Language>_summary.json` for each language (C, C#, C++, Go, Java, JavaScript, PHP, Python, Rust, TypeScript).

---

### Step 2 — Draw a stratified random sample

Randomly samples `SKILL.md` files from a language subfolder of `raw_data` and copies them — preserving the original relative path structure — into `outputs/rq3/language_sample/<Language>/`. Run once per language:

```sh
# Python
uv run python src/rq3/generate_language_sample.py \
  --root outputs/raw_data/Python \
  --n 370 --seed 42 \
  --out-dir outputs/rq3/language_sample/Python

# TypeScript
uv run python src/rq3/generate_language_sample.py \
  --root outputs/raw_data/TypeScript \
  --n 372 --seed 42 \
  --out-dir outputs/rq3/language_sample/Typescript
```

`--seed` ensures the sample is reproducible across machines.

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
  --root outputs/rq3/language_sample/Typescript \
  --both 56 --A 158 --B 158 \
  --out-dir outputs/rq3/labeling_samples/Typescript \
  --seed 42
```

**Artifact produced:** `outputs/rq3/labeling_samples/<Language>/{both,A,B}/`

---

### Step 4 — Compute inter-rater agreement

Calculate per-label Cohen's kappa between two annotators on the shared `both` set:

```sh
uv run python src/rq3/calculate_agreement.py \
  outputs/rq3/results/2026-04-19_CY_Final_Labels_Both_Python.json \
  outputs/rq3/results/2026-04-19_MV_Final_Labels_Both_Python.json
```

**Artifact produced:** `outputs/rq3/results/kappa_<file_A>_vs_<file_B>.json`

---

### Step 5 — Process and merge label exports

Convert raw label exports from the annotation tool into a normalized format and compute aggregate statistics:

```sh
uv run python src/rq3/analyze_processed_labels.py \
  --input-dir outputs/rq3/results/processed
```

**Artifacts produced:** `outputs/rq3/results/processed_label_statistics.json` and `outputs/rq3/results/processed_label_statistics.md`

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

---

### Step 7 — Generate full Python dataset analysis

Combines all label buckets (both, A, B) and the full Python `Python_All.json` dataset for structural and SDLC-task analysis:

```sh
uv run python src/rq3/generate_python_all_analysis.py \
  --processed-dir outputs/rq3/results/processed \
  --out-dir outputs/rq3/analysis/python_all
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
| `table_python_all_repo_skill_counts.csv` | Per-repo skill count breakdown |
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

---

### RQ3 module structure

```
src/rq3/
  retrieve_language_metadata.py            # Step 1: per-language JSON summaries from raw_data
  generate_language_sample.py              # Step 2: random per-language sample from raw_data
  generate_labeling_samples.py             # Step 3: split sample into both/A/B labeling buckets
  calculate_agreement.py                   # Step 4: Cohen's kappa between two annotators
  analyze_processed_labels.py              # Step 5: aggregate statistics for processed exports
  generate_processed_analysis_plots.py     # Step 6: plots for the both/A/B labeling sets
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
  search_github_repos.py          # Stage 1: scrape repo list from GitHub API
  extract_skill_repos.py          # Stage 2: scan repos for SKILL.md via code search
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
  rq3/
    retrieve_language_metadata.py            # RQ3 Step 1: per-language summaries
    generate_language_sample.py              # RQ3 Step 2: stratified random sample
    generate_labeling_samples.py             # RQ3 Step 3: both/A/B bucket split
    calculate_agreement.py                   # RQ3 Step 4: Cohen's kappa
    analyze_processed_labels.py              # RQ3 Step 5: aggregate label statistics
    generate_processed_analysis_plots.py     # RQ3 Step 6: analysis plots (both/A/B set)
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
  processing_failures.tsv         # Stage 3: repos with no dataset rows and why
  name_filtered_repos.tsv         # Stage 3: repos skipped by the shared name filter
  full_skills_instances.csv       # Stage 3: per-repo skill metrics
  raw_data/                       # Stage 3: downloaded skill folder contents
  rq1/                            # RQ1 figures and tables
  rq2/                            # RQ2 content analysis outputs
  rq3/                            # RQ3 labeling, agreement, and analysis outputs
```
