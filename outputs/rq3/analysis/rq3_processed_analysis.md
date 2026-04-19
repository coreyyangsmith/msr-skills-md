# RQ3 Processed Label Analysis

## Agreement
- Latest Python Both pair: `CY 2026-04-19 Both Python vs MV 2026-04-19 Both Python`
- Average kappa across collapsed labels: `0.5633`
- Change vs earliest Python Both pair: `+0.2271` (0.3362 -> 0.5633)

Lowest-agreement labels in the latest pair:
- `Requirements`: kappa `0.0000` (supports `2` vs `0`)
- `negative-examples`: kappa `0.4091` (supports `2` vs `7`)
- `descriptive`: kappa `0.4601` (supports `16` vs `21`)
- `Documentation`: kappa `0.4851` (supports `1` vs `3`)
- `commands`: kappa `0.5282` (supports `11` vs `14`)

Highest-agreement labels in the latest pair:
- `DevOps`: kappa `0.7787`
- `reference`: kappa `0.7610`
- `Software Design`: kappa `0.7365`
- `filter`: kappa `0.7284`
- `Software Testing`: kappa `0.6541`

## Filtering
- `2026-04-19_MV_Relabels_B_Python`: `62.50%` filtered (5/8 docs)
- `2026-04-06_CY_Labels_A_Python`: `53.21%` filtered (83/156 docs)
- `CY 2026-04-19 A Python`: `50.99%` filtered (77/151 docs)
- `2026-04-02_CY_Labels_Both_Python`: `48.21%` filtered (27/56 docs)
- `2026-03-31_MV_Labels_Both_Python`: `46.43%` filtered (26/56 docs)
- `CY 2026-04-19 Both Python`: `46.15%` filtered (24/52 docs)
- `Python_All`: `44.85%` filtered (161/359 docs)
- `2026-04-06_MV_Labels_Both_Python`: `44.64%` filtered (25/56 docs)
- `MV 2026-04-19 Both Python`: `44.23%` filtered (23/52 docs)
- `2026-03-29_CY_Labels_Both_TS`: `42.86%` filtered (24/56 docs)
- `2026-04-06_MV_Labels_B_Python`: `38.46%` filtered (60/156 docs)
- `MV 2026-04-19 B Python`: `38.46%` filtered (60/156 docs)
- `2026-03-28_CY_Labels_Both_Python`: `35.71%` filtered (20/56 docs)
- `2026-04-19_CY_Relabels_Both_Python`: `33.33%` filtered (2/6 docs)
- `2026-04-19_CY_Relabels_A_Python`: `25.00%` filtered (3/12 docs)
- `2026-04-19-MV_Relabels_Both_Python`: `16.67%` filtered (1/6 docs)

Latest Python Both pair filter-source counts:
- `CY 2026-04-19 Both Python`: `{'agent-skill': 19, 'outside-scope': 3, 'wrong-language': 2}`
- `MV 2026-04-19 Both Python`: `{'agent-skill': 18, 'outside-scope': 3, 'wrong-language': 3}`

## Latest Pair Patterns
- `CY 2026-04-19 Both Python` retained docs are led by `instructive, descriptive, reference, Software Testing, commands`.
- `MV 2026-04-19 Both Python` retained docs are led by `descriptive, instructive, commands, reference, Code Generation`.
- Strongest SDLC stage in `CY 2026-04-19 Both Python`: `Software Testing`.
- Strongest SDLC stage in `MV 2026-04-19 Both Python`: `Code Generation`.
