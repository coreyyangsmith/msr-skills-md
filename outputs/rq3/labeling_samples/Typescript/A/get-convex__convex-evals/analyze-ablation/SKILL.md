---
name: analyze-ablation
description: Analyze guideline ablation experiment results to determine which guideline sections are essential, marginal, or dispensable. Use when the user asks to analyze ablation results, interpret guideline compaction data, or wants to know which guidelines to keep for AGENTS.md.
---

# Analyze Ablation Results

## When to use

- User says "analyze the ablation results" or "analyze ablation for <model>"
- User wants to know which guideline sections to keep or remove
- User asks about guideline compaction or AGENTS.md token budget
- After a guideline ablation experiment has been run (via GitHub Action or locally)

## Step 1: Find available results

List the `ablation/results/` directory to see which models have results:

```bash
ls ablation/results/
```

If the directory is empty or doesn't exist, the user needs to either:
1. Run the ablation locally: `bun run scripts/runAblation.ts --model <model>`
2. Or download results from a GitHub Actions run:
   ```bash
   # List recent ablation workflow runs
   gh run list --workflow=ablation_experiment.yml --limit=5
   # Download the artifact
   gh run download <run-id> -n ablation-<model>-<run-id> -D ablation/results/
   ```

## Step 2: Read the summary JSON

For the requested model, read the latest JSON file from `ablation/results/<model>/`.
The file contains:

- `model`: The model name
- `timestamp`: When the experiment ran
- `baseline`: Overall pass/fail counts and per-eval results with the full guideline set
- `sections`: Array of per-section ablation results, each with:
  - `name`: Section name (e.g. "function_guidelines", "query_guidelines")
  - `tokensInSection`: How many tokens this section costs
  - `verdict`: "ESSENTIAL" (2+ regressions), "MARGINAL" (1 regression), "DISPENSABLE" (0 regressions)
  - `regressions`: Eval names that flipped from pass to fail when this section was removed
  - `improvements`: Eval names that flipped from fail to pass when removed (guidelines confusing the model)
  - `score`: Pass/fail counts for this ablation variant

## Step 3: Present the classification table

Present a summary table showing:

| Section | Verdict | Regressions | Improvements | Tokens | Score |
|---------|---------|-------------|--------------|--------|-------|

Sort by verdict: ESSENTIAL first, then MARGINAL, then DISPENSABLE.

## Step 4: Detailed analysis

For each ESSENTIAL and MARGINAL section:
- List the specific evals that regressed
- Check if the regressed evals are related to the section topic (e.g. query_guidelines causes query eval regressions — expected)
- Flag any surprising regressions (section removal caused failures in unrelated evals)

For any section with improvements:
- These are cases where the guideline was actively confusing the model
- Flag these as candidates for rewording even if the section is kept

## Step 5: Cross-model comparison (if multiple models have results)

If `ablation/results/` has results for multiple models:
- Compare verdicts across models
- A section ESSENTIAL in ALL models is definitely essential
- A section ESSENTIAL in some models should still be kept (conservative approach)
- A section DISPENSABLE in ALL models is safe to remove
- Flag any sections with conflicting verdicts across models

## Step 6: Token budget summary

Calculate:
- **Current full guidelines**: Total tokens (from baseline)
- **Essential sections only**: Sum of tokens for ESSENTIAL sections
- **Essential + Marginal**: Sum of tokens for ESSENTIAL and MARGINAL sections
- **Savings**: How many tokens saved by removing DISPENSABLE (and optionally MARGINAL) sections

## Step 7: Recommend next steps

Based on the results, recommend one of:

1. **Ready to build AGENTS.md**: If the classification is clear and token savings are meaningful, suggest building the compact guideline set and running a validation run.

2. **Subsection ablation needed**: If `function_guidelines` is ESSENTIAL (likely — it's the largest section at ~2400 tokens), suggest a follow-up ablation of its 8 subsections to find further savings.

3. **Cross-model validation needed**: If only one model has been tested, suggest running ablation on 1-2 additional models for confidence.

4. **Results are noisy**: If many sections show exactly 1 regression (MARGINAL), the run-to-run variance may be too high. Suggest re-running or using a different model.

Present findings to the user and ask which direction they want to go. Do NOT make any code changes until asked.

## Reference: Guideline sections

The 10 top-level sections in `runner/models/guidelines.ts` are:

1. `function_guidelines` — Function syntax, HTTP endpoints, validators, registration, calling conventions, function references, API design, pagination
2. `validator_guidelines` — v.bigint deprecation, v.record usage
3. `schema_guidelines` — Schema location, system fields, index naming, index field ordering
4. `typescript_guidelines` — Id types, Record types, strict typing, as const, Array/Record patterns, @types/node
5. `full_text_search_guidelines` — Search index query syntax
6. `query_guidelines` — No filter, no .delete(), .unique(), async iteration, ordering
7. `mutation_guidelines` — ctx.db.replace vs ctx.db.patch
8. `action_guidelines` — "use node", no ctx.db, action syntax
9. `scheduling_guidelines` — Cron syntax, FunctionReference usage, crons.ts patterns
10. `file_storage_guidelines` — Storage API, getUrl, system table queries, Blob handling
