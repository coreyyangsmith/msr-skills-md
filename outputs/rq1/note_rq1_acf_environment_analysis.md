# RQ1 ACF Environment Analysis

## Data Availability
- Current scan data can support co-occurrence analysis among tracked ACFs inside confirmed `SKILL.md` repositories.
- Current scan data cannot support a clean estimate of whether developers in a given environment prefer `SKILL.md`, because tracked ACF checks were only executed for `found=true` repositories.
- The local `outputs/raw_data` mirror also lines up with the SKILL.md-positive subset rather than the full scanned population, so it cannot backfill the missing negative cases for a preference comparison.

## Overall Findings on Tracked ACFs within SKILL.md Repositories
- `CLAUDE.md` appears in `1367` repos (43.40% of SKILL.md repos).
- `AGENTS.md` appears in `1164` repos (36.95% of SKILL.md repos).
- `copilot-instructions.md` appears in `322` repos (10.22% of SKILL.md repos).
- `GEMINI.md` appears in `92` repos (2.92% of SKILL.md repos).
- `.cursorrules.md` appears in `0` repos (0.00% of SKILL.md repos).
- `.instructions.md` appears in `0` repos (0.00% of SKILL.md repos).

## How Often Multiple ACFs Appear
- At least one tracked ACF appears in `2016` repos (64.00% of SKILL.md repos).
- Multiple tracked ACFs (2+) appear in `782` repos (24.83% of SKILL.md repos).
- All tracked ACFs appear together in `0` repos (0.00% of SKILL.md repos).

## Pairwise Co-occurrence
Strongest pairwise overlaps by Jaccard:
- `CLAUDE.md` + `AGENTS.md`: intersection `659`, jaccard `0.3520`
- `AGENTS.md` + `copilot-instructions.md`: intersection `154`, jaccard `0.1156`
- `CLAUDE.md` + `copilot-instructions.md`: intersection `138`, jaccard `0.0890`

Strongest pairwise associations by lift:
- `copilot-instructions.md` -> `GEMINI.md`: lift `2.2330`, P(B|A) `0.0652`
- `AGENTS.md` -> `GEMINI.md`: lift `1.6767`, P(B|A) `0.0490`
- `CLAUDE.md` -> `GEMINI.md`: lift `1.5780`, P(B|A) `0.0461`

## Combination Usage
Most common tracked-artifact combinations:
- `None of the tracked artifacts`: `1134` repos (36.00%)
- `CLAUDE.md`: `653` repos (20.73%)
- `CLAUDE.md + AGENTS.md`: `531` repos (16.86%)
- `AGENTS.md`: `439` repos (13.94%)
- `copilot-instructions.md`: `121` repos (3.84%)

## Language-Level Pattern Differences
Highest shares of SKILL.md repos with any tracked ACF:
- `C#`: `74.36%` (87/117)
- `Rust`: `71.43%` (220/308)
- `C`: `71.43%` (15/21)

Highest shares of SKILL.md repos with multiple tracked ACFs:
- `Rust`: `28.57%` (88/308)
- `Go`: `27.12%` (83/306)
- `TypeScript`: `26.31%` (312/1186)
