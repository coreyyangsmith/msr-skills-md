# RQ3-Informed Screening Methodology Update

## Methodology paragraph

We treated repository screening as a reproducible rule-development step rather than as a change to the study population. The initial corpus was screened with repository-name heuristics, metadata inspection, and an explicit blacklist. During the RQ3 manual coding process, sampled `SKILL.md` artifacts also exposed false positives and borderline cases, including skill hubs, curated skill collections, templates, examples, and personal configuration repositories. We used those qualitative labels as an internal audit set for the screening procedure: RQ3 labels informed a revised rule set with hard exclusions, manual-review flags, and keep overrides for repositories with strong software-project signals. The revised screening rules were then re-applied to the full mined corpus before the final RQ1 and RQ2 analyses. Thus, RQ1 remains repository-scoped over the screened full repository frame, RQ2 remains artifact-scoped over retained `SKILL.md` artifacts, and RQ3 remains a manually coded subset used for qualitative analysis and screening validation.

## Threats to validity paragraph

Repository-name heuristics are an imperfect proxy for repository relevance. To reduce construct-validity risk, we used the manually coded RQ3 sample to audit the initial heuristic, identify recurring false-positive categories, and refine the screening criteria before re-applying them to the full mined corpus. The final rules separate hard exclusions from manual-review cases and allow strong software-project signals to override noisy name terms. Even with this refinement, some in-scope and out-of-scope repositories may remain imperfectly separated, especially for repositories that mix reusable agent-skill collections with application code. We therefore release the screening rules, audit sample, decision table, and unresolved-review queue so the filtering process is reproducible and its uncertainty is explicit.

## Screening flow

1. Mine candidate repositories and scan them for `SKILL.md`.
2. Apply the v1 repository-name heuristic and blacklist as the historical baseline.
3. Use RQ3 manual labels to audit v1 false positives, false negatives, and noisy keywords.
4. Build the v2 rule set with `keep`, `exclude`, and `review` outcomes.
5. Apply v2 to the full mined corpus, not just the RQ3 sample.
6. Resolve rows in `outputs/screening/manual_review_borderline.csv` before final reporting.
7. Regenerate RQ1 from the screened full repository frame.
8. Regenerate RQ2 from retained artifacts in the screened repository frame.
9. Keep RQ3 as the qualitative manually coded subset.

## Reproducible commands

Generate screening audit outputs and v2 decisions:

```sh
uv run python src/generate_screening_outputs.py
```

After manually adjudicating review rows, save a CSV such as `outputs/screening/manual_decisions.csv` with `repo,decision,primary_reason`, then regenerate the full decision file with overrides:

```sh
uv run python src/generate_screening_outputs.py \
  --manual-decisions outputs/screening/manual_decisions.csv
```

Regenerate the stage-3 artifact corpus without the historical hard name filter, writing to separate v2 outputs:

```sh
uv run python src/generate_dataset.py \
  --found-csv outputs/skill_md_scan_results_found.csv \
  --out-csv outputs/full_skills_instances_v2.csv \
  --raw-data-dir outputs/raw_data_v2 \
  --no-name-filter \
  --resume
```

Run final RQ1 after all `review` rows in `outputs/screening/manual_review_borderline.csv` have been adjudicated:

```sh
uv run python src/rq1/analyze_metadata.py \
  --scan-csv outputs/skill_md_scan_results_with_contributors.csv \
  --instances-csv outputs/full_skills_instances_v2.csv \
  --screening-decisions outputs/screening/full_corpus_screening_decisions.csv \
  --screening-mode final \
  --out-dir outputs/rq1_v2
```

Collect final RQ2 documents from the v2 raw-data mirror:

```sh
uv run python src/rq2/collect_skill_documents.py \
  --raw-data-dir outputs/raw_data_v2 \
  --out-jsonl outputs/rq2/skill_documents_v2.jsonl \
  --out-stats-json outputs/rq2/skill_documents_stats_v2.json \
  --screening-decisions outputs/screening/full_corpus_screening_decisions.csv \
  --screening-mode final
```
