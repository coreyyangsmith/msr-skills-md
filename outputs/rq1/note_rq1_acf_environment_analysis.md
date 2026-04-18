# RQ1 ACF Environment Analysis

## Data Availability
- Current scan data can support co-occurrence analysis among tracked ACFs inside confirmed `SKILL.md` repositories.
- Current scan data cannot support a clean estimate of whether developers in a given environment prefer `SKILL.md`, because tracked ACF checks were only executed for `found=true` repositories.
- `.cursorrules.md` is not available as a structured column in the current scan CSV, so answering questions about that artifact requires a new scan/enrichment pass.
- The local `outputs/raw_data` mirror also lines up with the SKILL.md-positive subset rather than the full scanned population, so it cannot backfill the missing negative cases for a preference comparison.

## Overall Findings on Tracked ACFs within SKILL.md Repositories
- `CLAUDE.md` appears in `1586` repos (41.56% of SKILL.md repos).
- `AGENTS.md` appears in `1324` repos (34.70% of SKILL.md repos).
- `copilot-instructions.md` appears in `375` repos (9.83% of SKILL.md repos).

## How Often Multiple ACFs Appear
- At least one tracked ACF appears in `2349` repos (61.56% of SKILL.md repos).
- Multiple tracked ACFs (2+) appear in `842` repos (22.06% of SKILL.md repos).
- All tracked ACFs appear together in `94` repos (2.46% of SKILL.md repos).

## Pairwise Co-occurrence
Strongest pairwise overlaps by Jaccard:
- `CLAUDE.md` + `AGENTS.md`: intersection `725`, jaccard `0.3318`
- `AGENTS.md` + `copilot-instructions.md`: intersection `160`, jaccard `0.1040`
- `CLAUDE.md` + `copilot-instructions.md`: intersection `145`, jaccard `0.0798`

Strongest pairwise associations by lift:
- `CLAUDE.md` -> `AGENTS.md`: lift `1.3175`, P(B|A) `0.4571`
- `AGENTS.md` -> `copilot-instructions.md`: lift `1.2297`, P(B|A) `0.1208`
- `CLAUDE.md` -> `copilot-instructions.md`: lift `0.9303`, P(B|A) `0.0914`

## Combination Usage
Most common tracked-artifact combinations:
- `None of the tracked artifacts`: `1467` repos (38.44%)
- `CLAUDE.md`: `810` repos (21.23%)
- `CLAUDE.md + AGENTS.md`: `631` repos (16.54%)
- `AGENTS.md`: `533` repos (13.97%)
- `copilot-instructions.md`: `164` repos (4.30%)

## Language-Level Pattern Differences
Highest shares of SKILL.md repos with any tracked ACF:
- `C#`: `75.76%` (100/132)
- `C`: `69.57%` (16/23)
- `Rust`: `69.08%` (248/359)

Highest shares of SKILL.md repos with multiple tracked ACFs:
- `Rust`: `26.74%` (96/359)
- `Go`: `24.32%` (89/366)
- `TypeScript`: `23.87%` (339/1420)
