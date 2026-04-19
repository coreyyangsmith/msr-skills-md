# RQ3 Processed Label Analysis

## Agreement
- Latest Python Both pair: `2026-04-02_CY_Labels_Both_Python vs 2026-04-06_MV_Labels_Both_Python`
- Average kappa across collapsed labels: `0.5992`
- Change vs earliest Python Both pair: `+0.2630` (0.3362 -> 0.5992)

Lowest-agreement labels in the latest pair:
- `negative-examples`: kappa `0.4118` (supports `2` vs `7`)
- `descriptive`: kappa `0.4517` (supports `19` vs `26`)
- `commands`: kappa `0.4737` (supports `10` vs `14`)
- `Requirements`: kappa `0.4862` (supports `3` vs `1`)
- `instructive`: kappa `0.5575` (supports `20` vs `17`)

Highest-agreement labels in the latest pair:
- `DevOps`: kappa `0.7804`
- `reference`: kappa `0.7674`
- `filter`: kappa `0.7132`
- `Software Design`: kappa `0.7083`
- `Documentation`: kappa `0.6500`

## Filtering
- `2026-04-06_CY_Labels_A_Python`: `53.21%` filtered (83/156 docs)
- `2026-04-02_CY_Labels_Both_Python`: `48.21%` filtered (27/56 docs)
- `2026-03-31_MV_Labels_Both_Python`: `46.43%` filtered (26/56 docs)
- `2026-04-06_MV_Labels_Both_Python`: `44.64%` filtered (25/56 docs)
- `2026-03-29_CY_Labels_Both_TS`: `42.86%` filtered (24/56 docs)
- `2026-04-06_MV_Labels_B_Python`: `38.46%` filtered (60/156 docs)
- `2026-03-28_CY_Labels_Both_Python`: `35.71%` filtered (20/56 docs)

Latest Python Both pair filter-source counts:
- `2026-04-02_CY_Labels_Both_Python`: `{'agent-skill': 22, 'outside-scope': 4, 'wrong-language': 1}`
- `2026-04-06_MV_Labels_Both_Python`: `{'agent-skill': 21, 'outside-scope': 3, 'wrong-language': 2}`

## Latest Pair Patterns
- `2026-04-02_CY_Labels_Both_Python` retained docs are led by `instructive, descriptive, reference, Software Testing, commands`.
- `2026-04-06_MV_Labels_Both_Python` retained docs are led by `descriptive, instructive, commands, reference, Code Generation`.
- Strongest SDLC stage in `2026-04-02_CY_Labels_Both_Python`: `Software Testing`.
- Strongest SDLC stage in `2026-04-06_MV_Labels_Both_Python`: `Code Generation`.
