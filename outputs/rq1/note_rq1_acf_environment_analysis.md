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
- `GEMINI.md` appears in `111` repos (2.91% of SKILL.md repos).
- `.cursorrules.md` appears in `0` repos (0.00% of SKILL.md repos).
- `.instructions.md` appears in `0` repos (0.00% of SKILL.md repos).

## How Often Multiple ACFs Appear
- At least one tracked ACF appears in `2376` repos (62.26% of SKILL.md repos).
- Multiple tracked ACFs (2+) appear in `860` repos (22.54% of SKILL.md repos).
- All tracked ACFs appear together in `0` repos (0.00% of SKILL.md repos).

## Pairwise Co-occurrence
Strongest pairwise overlaps by Jaccard:
- `CLAUDE.md` + `AGENTS.md`: intersection `725`, jaccard `0.3318`
- `AGENTS.md` + `copilot-instructions.md`: intersection `160`, jaccard `0.1040`
- `CLAUDE.md` + `copilot-instructions.md`: intersection `145`, jaccard `0.0798`

Strongest pairwise associations by lift:
- `copilot-instructions.md` -> `GEMINI.md`: lift `2.0169`, P(B|A) `0.0587`
- `AGENTS.md` -> `GEMINI.md`: lift `1.7657`, P(B|A) `0.0514`
- `CLAUDE.md` -> `GEMINI.md`: lift `1.6691`, P(B|A) `0.0485`

## Combination Usage
Most common tracked-artifact combinations:
- `None of the tracked artifacts`: `1440` repos (37.74%)
- `CLAUDE.md`: `798` repos (20.91%)
- `CLAUDE.md + AGENTS.md`: `586` repos (15.36%)
- `AGENTS.md`: `528` repos (13.84%)
- `copilot-instructions.md`: `163` repos (4.27%)

## Language-Level Pattern Differences
Highest shares of SKILL.md repos with any tracked ACF:
- `C#`: `75.76%` (100/132)
- `C`: `69.57%` (16/23)
- `Rust`: `69.08%` (248/359)

Highest shares of SKILL.md repos with multiple tracked ACFs:
- `Rust`: `27.30%` (98/359)
- `Go`: `24.59%` (90/366)
- `TypeScript`: `24.01%` (341/1420)
