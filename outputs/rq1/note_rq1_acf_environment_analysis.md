# RQ1 ACF Environment Analysis

## Data Availability
- Current scan data can support co-occurrence analysis among tracked ACFs inside confirmed `SKILL.md` repositories.
- Current scan data cannot support a clean estimate of whether developers in a given environment prefer `SKILL.md`, because tracked ACF checks were only executed for `found=true` repositories.
- The local `outputs/raw_data` mirror also lines up with the SKILL.md-positive subset rather than the full scanned population, so it cannot backfill the missing negative cases for a preference comparison.

## Overall Findings on Tracked ACFs within SKILL.md Repositories
- `CLAUDE.md` appears in `1528` repos (43.64% of SKILL.md repos).
- `AGENTS.md` appears in `1288` repos (36.79% of SKILL.md repos).
- `copilot-instructions.md` appears in `355` repos (10.14% of SKILL.md repos).
- `GEMINI.md` appears in `100` repos (2.86% of SKILL.md repos).

## How Often Multiple ACFs Appear
- At least one tracked ACF appears in `2250` repos (64.27% of SKILL.md repos).
- Multiple tracked ACFs (2+) appear in `860` repos (24.56% of SKILL.md repos).
- All tracked ACFs appear together in `16` repos (0.46% of SKILL.md repos).

## Pairwise Co-occurrence
Strongest pairwise overlaps by Jaccard:
- `CLAUDE.md` + `AGENTS.md`: intersection `729`, jaccard `0.3493`
- `AGENTS.md` + `copilot-instructions.md`: intersection `165`, jaccard `0.1116`
- `CLAUDE.md` + `copilot-instructions.md`: intersection `150`, jaccard `0.0866`

Strongest pairwise associations by lift:
- `copilot-instructions.md` -> `GEMINI.md`: lift `2.0710`, P(B|A) `0.0592`
- `AGENTS.md` -> `GEMINI.md`: lift `1.7396`, P(B|A) `0.0497`
- `CLAUDE.md` -> `GEMINI.md`: lift `1.5809`, P(B|A) `0.0452`

## Combination Usage
Most common tracked-artifact combinations:
- `None of the tracked artifacts`: `1251` repos (35.73%)
- `CLAUDE.md`: `740` repos (21.14%)
- `CLAUDE.md + AGENTS.md`: `587` repos (16.77%)
- `AGENTS.md`: `489` repos (13.97%)
- `copilot-instructions.md`: `139` repos (3.97%)

## Language-Level Pattern Differences
Highest shares of SKILL.md repos with any tracked ACF:
- `C#`: `75.40%` (95/126)
- `C`: `73.91%` (17/23)
- `C++`: `72.41%` (42/58)

Highest shares of SKILL.md repos with multiple tracked ACFs:
- `Rust`: `28.74%` (98/341)
- `Go`: `27.00%` (91/337)
- `TypeScript`: `26.21%` (346/1320)
