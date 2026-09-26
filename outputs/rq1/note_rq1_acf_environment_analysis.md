# RQ1 ACF Environment Analysis

## Data Availability
- Current scan data can support co-occurrence analysis among tracked ACFs inside confirmed `SKILL.md` repositories.
- Current scan data cannot support a clean estimate of whether developers in a given environment prefer `SKILL.md`, because tracked ACF checks were only executed for `found=true` repositories.
- The local `outputs/raw_data` mirror also lines up with the SKILL.md-positive subset rather than the full scanned population, so it cannot backfill the missing negative cases for a preference comparison.

## Overall Findings on Tracked ACFs within SKILL.md Repositories
- `AGENTS.md` appears in `3888` repos (45.09% of SKILL.md repos).
- `CLAUDE.md` appears in `3806` repos (44.14% of SKILL.md repos).
- `copilot-instructions.md` appears in `626` repos (7.26% of SKILL.md repos).
- `GEMINI.md` appears in `338` repos (3.92% of SKILL.md repos).
- `.instructions.md` appears in `2` repos (0.02% of SKILL.md repos).

## How Often Multiple ACFs Appear
- At least one tracked ACF appears in `5610` repos (65.06% of SKILL.md repos).
- Multiple tracked ACFs (2+) appear in `2555` repos (29.63% of SKILL.md repos).
- All tracked ACFs appear together in `0` repos (0.00% of SKILL.md repos).

## Pairwise Co-occurrence
Strongest pairwise overlaps by Jaccard:
- `CLAUDE.md` + `AGENTS.md`: intersection `2299`, jaccard `0.4261`
- `copilot-instructions.md` + `GEMINI.md`: intersection `79`, jaccard `0.0893`
- `AGENTS.md` + `copilot-instructions.md`: intersection `369`, jaccard `0.0890`

Strongest pairwise associations by lift:
- `copilot-instructions.md` -> `GEMINI.md`: lift `3.2195`, P(B|A) `0.1262`
- `CLAUDE.md` -> `GEMINI.md`: lift `1.7227`, P(B|A) `0.0675`
- `AGENTS.md` -> `GEMINI.md`: lift `1.7192`, P(B|A) `0.0674`

## Combination Usage
Most common tracked-artifact combinations:
- `None of the tracked artifacts`: `3013` repos (34.94%)
- `CLAUDE.md + AGENTS.md`: `1881` repos (21.81%)
- `AGENTS.md`: `1445` repos (16.76%)
- `CLAUDE.md`: `1397` repos (16.20%)
- `CLAUDE.md + AGENTS.md + copilot-instructions.md`: `190` repos (2.20%)

## Language-Level Pattern Differences
Highest shares of SKILL.md repos with any tracked ACF:
- `TypeScript`: `73.23%` (3219/4396)
- `Python`: `56.56%` (2391/4227)

Highest shares of SKILL.md repos with multiple tracked ACFs:
- `TypeScript`: `34.39%` (1512/4396)
- `Python`: `24.67%` (1043/4227)
