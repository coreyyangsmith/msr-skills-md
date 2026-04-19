# RQ1 ACF Environment Analysis

## Data Availability
- Current scan data can support co-occurrence analysis among tracked ACFs inside confirmed `SKILL.md` repositories.
- Current scan data cannot support a clean estimate of whether developers in a given environment prefer `SKILL.md`, because tracked ACF checks were only executed for `found=true` repositories.
- The local `outputs/raw_data` mirror also lines up with the SKILL.md-positive subset rather than the full scanned population, so it cannot backfill the missing negative cases for a preference comparison.

## Overall Findings on Tracked ACFs within SKILL.md Repositories
- `CLAUDE.md` appears in `1514` repos (43.53% of SKILL.md repos).
- `AGENTS.md` appears in `1281` repos (36.83% of SKILL.md repos).
- `copilot-instructions.md` appears in `354` repos (10.18% of SKILL.md repos).
- `GEMINI.md` appears in `99` repos (2.85% of SKILL.md repos).

## How Often Multiple ACFs Appear
- At least one tracked ACF appears in `2234` repos (64.23% of SKILL.md repos).
- Multiple tracked ACFs (2+) appear in `854` repos (24.55% of SKILL.md repos).
- All tracked ACFs appear together in `16` repos (0.46% of SKILL.md repos).

## Pairwise Co-occurrence
Strongest pairwise overlaps by Jaccard:
- `CLAUDE.md` + `AGENTS.md`: intersection `723`, jaccard `0.3489`
- `AGENTS.md` + `copilot-instructions.md`: intersection `165`, jaccard `0.1122`
- `CLAUDE.md` + `copilot-instructions.md`: intersection `150`, jaccard `0.0873`

Strongest pairwise associations by lift:
- `copilot-instructions.md` -> `GEMINI.md`: lift `2.0841`, P(B|A) `0.0593`
- `AGENTS.md` -> `GEMINI.md`: lift `1.7278`, P(B|A) `0.0492`
- `CLAUDE.md` -> `GEMINI.md`: lift `1.5779`, P(B|A) `0.0449`

## Combination Usage
Most common tracked-artifact combinations:
- `None of the tracked artifacts`: `1244` repos (35.77%)
- `CLAUDE.md`: `732` repos (21.05%)
- `CLAUDE.md + AGENTS.md`: `582` repos (16.73%)
- `AGENTS.md`: `488` repos (14.03%)
- `copilot-instructions.md`: `138` repos (3.97%)

## Language-Level Pattern Differences
Highest shares of SKILL.md repos with any tracked ACF:
- `C#`: `75.40%` (95/126)
- `C`: `73.91%` (17/23)
- `C++`: `71.93%` (41/57)

Highest shares of SKILL.md repos with multiple tracked ACFs:
- `Rust`: `28.40%` (96/338)
- `Go`: `27.25%` (91/334)
- `TypeScript`: `26.28%` (345/1313)
