# Processed RQ3 Label Statistics

Processed vs filtered comparisons are document-level, not repo-level.

## Overview
| File | Docs | Retained | Filtered | Filtered % | Any SDLC | Any Instruction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-09-19_PY_FINAL.json | 382 | 181 | 201 | 52.62 | 180 | 181 |
| 2026-09-19_TS_FINAL.json | 381 | 265 | 116 | 30.45 | 265 | 264 |
| Python_All.json | 382 | 181 | 201 | 52.62 | 180 | 181 |
| TypeScript_All.json | 381 | 265 | 116 | 30.45 | 265 | 264 |

## 2026-09-19_PY_FINAL.json

- Dataset root: `FINAL`
- Total documents: 382
- Retained documents: 181 (47.38%)
- Filtered documents: 201 (52.62%)
- Avg labels / doc: 4.686
- Avg labels / retained doc: 8.779
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 133, 'filter-out': 21, 'outside-scope': 0, 'wrong-language': 47}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| purpose | 179 | 98.90 |
| action-directive | 176 | 97.24 |
| decision-rule | 175 | 96.69 |
| activation | 166 | 91.71 |
| workflow | 163 | 90.06 |
| reference | 141 | 77.90 |
| positive-example | 102 | 56.35 |
| exclusion | 76 | 41.99 |
| Testing | 66 | 36.46 |
| Code Implementation | 63 | 34.81 |
| Maintenance | 60 | 33.15 |
| Program Analysis | 47 | 25.97 |
| DevOps | 46 | 25.41 |
| Documentation | 38 | 20.99 |
| negative-example | 34 | 18.78 |
| Debugging | 21 | 11.60 |
| Software Design | 19 | 10.50 |
| Requirements | 17 | 9.39 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 201 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| purpose | 179 | 46.86 |
| activation | 166 | 43.46 |
| exclusion | 76 | 19.90 |
| workflow | 163 | 42.67 |
| decision-rule | 175 | 45.81 |
| action-directive | 176 | 46.07 |
| positive-example | 102 | 26.70 |
| negative-example | 34 | 8.90 |
| reference | 141 | 36.91 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Requirements | 17 | 9.39 |
| Software Design | 19 | 10.50 |
| Code Implementation | 63 | 34.81 |
| Program Analysis | 47 | 25.97 |
| Testing | 66 | 36.46 |
| Debugging | 21 | 11.60 |
| Maintenance | 60 | 33.15 |
| DevOps | 46 | 25.41 |
| Documentation | 38 | 20.99 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| purpose | Requirements | 17 |
| purpose | Software Design | 19 |
| purpose | Code Implementation | 62 |
| purpose | Program Analysis | 47 |
| purpose | Testing | 66 |
| purpose | Debugging | 21 |
| purpose | Maintenance | 59 |
| purpose | DevOps | 46 |
| purpose | Documentation | 38 |
| activation | Requirements | 17 |
| activation | Software Design | 19 |
| activation | Code Implementation | 60 |
| activation | Program Analysis | 42 |
| activation | Testing | 59 |
| activation | Debugging | 21 |
| activation | Maintenance | 53 |
| activation | DevOps | 39 |
| activation | Documentation | 35 |
| exclusion | Requirements | 10 |
| exclusion | Software Design | 10 |
| exclusion | Code Implementation | 23 |
| exclusion | Program Analysis | 21 |
| exclusion | Testing | 26 |
| exclusion | Debugging | 11 |
| exclusion | Maintenance | 25 |
| exclusion | DevOps | 20 |
| exclusion | Documentation | 18 |
| workflow | Requirements | 17 |
| workflow | Software Design | 18 |
| workflow | Code Implementation | 54 |
| workflow | Program Analysis | 46 |
| workflow | Testing | 62 |
| workflow | Debugging | 19 |
| workflow | Maintenance | 53 |
| workflow | DevOps | 41 |
| workflow | Documentation | 38 |
| decision-rule | Requirements | 17 |
| decision-rule | Software Design | 19 |
| decision-rule | Code Implementation | 60 |
| decision-rule | Program Analysis | 46 |
| decision-rule | Testing | 65 |
| decision-rule | Debugging | 21 |
| decision-rule | Maintenance | 60 |
| decision-rule | DevOps | 45 |
| decision-rule | Documentation | 36 |
| action-directive | Requirements | 17 |
| action-directive | Software Design | 19 |
| action-directive | Code Implementation | 59 |
| action-directive | Program Analysis | 46 |
| action-directive | Testing | 65 |
| action-directive | Debugging | 21 |
| action-directive | Maintenance | 59 |
| action-directive | DevOps | 46 |
| action-directive | Documentation | 37 |
| positive-example | Requirements | 11 |
| positive-example | Software Design | 13 |
| positive-example | Code Implementation | 44 |
| positive-example | Program Analysis | 25 |
| positive-example | Testing | 38 |
| positive-example | Debugging | 9 |
| positive-example | Maintenance | 32 |
| positive-example | DevOps | 19 |
| positive-example | Documentation | 25 |
| negative-example | Requirements | 3 |
| negative-example | Software Design | 8 |
| negative-example | Code Implementation | 13 |
| negative-example | Program Analysis | 8 |
| negative-example | Testing | 11 |
| negative-example | Debugging | 1 |
| negative-example | Maintenance | 15 |
| negative-example | DevOps | 7 |
| negative-example | Documentation | 6 |
| reference | Requirements | 13 |
| reference | Software Design | 16 |
| reference | Code Implementation | 56 |
| reference | Program Analysis | 37 |
| reference | Testing | 53 |
| reference | Debugging | 18 |
| reference | Maintenance | 46 |
| reference | DevOps | 35 |
| reference | Documentation | 32 |

## 2026-09-19_TS_FINAL.json

- Dataset root: `FINAL`
- Total documents: 381
- Retained documents: 265 (69.55%)
- Filtered documents: 116 (30.45%)
- Avg labels / doc: 6.312
- Avg labels / retained doc: 8.638
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 72, 'filter-out': 18, 'outside-scope': 0, 'wrong-language': 26}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| purpose | 264 | 99.62 |
| decision-rule | 249 | 93.96 |
| action-directive | 247 | 93.21 |
| activation | 240 | 90.57 |
| positive-example | 194 | 73.21 |
| workflow | 188 | 70.94 |
| reference | 182 | 68.68 |
| Code Implementation | 137 | 51.70 |
| negative-example | 83 | 31.32 |
| exclusion | 80 | 30.19 |
| Testing | 76 | 28.68 |
| Maintenance | 65 | 24.53 |
| Program Analysis | 65 | 24.53 |
| Software Design | 57 | 21.51 |
| Documentation | 54 | 20.38 |
| DevOps | 44 | 16.60 |
| Debugging | 43 | 16.23 |
| Requirements | 21 | 7.92 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 116 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| purpose | 264 | 69.29 |
| activation | 240 | 62.99 |
| exclusion | 80 | 21.00 |
| workflow | 188 | 49.34 |
| decision-rule | 249 | 65.35 |
| action-directive | 247 | 64.83 |
| positive-example | 194 | 50.92 |
| negative-example | 83 | 21.78 |
| reference | 182 | 47.77 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Requirements | 21 | 7.92 |
| Software Design | 57 | 21.51 |
| Code Implementation | 137 | 51.70 |
| Program Analysis | 65 | 24.53 |
| Testing | 76 | 28.68 |
| Debugging | 43 | 16.23 |
| Maintenance | 65 | 24.53 |
| DevOps | 44 | 16.60 |
| Documentation | 54 | 20.38 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| purpose | Requirements | 21 |
| purpose | Software Design | 57 |
| purpose | Code Implementation | 136 |
| purpose | Program Analysis | 65 |
| purpose | Testing | 76 |
| purpose | Debugging | 43 |
| purpose | Maintenance | 65 |
| purpose | DevOps | 44 |
| purpose | Documentation | 54 |
| activation | Requirements | 18 |
| activation | Software Design | 52 |
| activation | Code Implementation | 125 |
| activation | Program Analysis | 60 |
| activation | Testing | 69 |
| activation | Debugging | 40 |
| activation | Maintenance | 61 |
| activation | DevOps | 42 |
| activation | Documentation | 51 |
| exclusion | Requirements | 9 |
| exclusion | Software Design | 18 |
| exclusion | Code Implementation | 43 |
| exclusion | Program Analysis | 20 |
| exclusion | Testing | 27 |
| exclusion | Debugging | 18 |
| exclusion | Maintenance | 19 |
| exclusion | DevOps | 15 |
| exclusion | Documentation | 17 |
| workflow | Requirements | 19 |
| workflow | Software Design | 42 |
| workflow | Code Implementation | 84 |
| workflow | Program Analysis | 53 |
| workflow | Testing | 67 |
| workflow | Debugging | 32 |
| workflow | Maintenance | 46 |
| workflow | DevOps | 40 |
| workflow | Documentation | 50 |
| decision-rule | Requirements | 20 |
| decision-rule | Software Design | 55 |
| decision-rule | Code Implementation | 126 |
| decision-rule | Program Analysis | 65 |
| decision-rule | Testing | 75 |
| decision-rule | Debugging | 42 |
| decision-rule | Maintenance | 62 |
| decision-rule | DevOps | 42 |
| decision-rule | Documentation | 53 |
| action-directive | Requirements | 21 |
| action-directive | Software Design | 55 |
| action-directive | Code Implementation | 126 |
| action-directive | Program Analysis | 64 |
| action-directive | Testing | 75 |
| action-directive | Debugging | 41 |
| action-directive | Maintenance | 59 |
| action-directive | DevOps | 42 |
| action-directive | Documentation | 51 |
| positive-example | Requirements | 19 |
| positive-example | Software Design | 40 |
| positive-example | Code Implementation | 102 |
| positive-example | Program Analysis | 53 |
| positive-example | Testing | 62 |
| positive-example | Debugging | 35 |
| positive-example | Maintenance | 45 |
| positive-example | DevOps | 33 |
| positive-example | Documentation | 38 |
| negative-example | Requirements | 6 |
| negative-example | Software Design | 17 |
| negative-example | Code Implementation | 40 |
| negative-example | Program Analysis | 24 |
| negative-example | Testing | 29 |
| negative-example | Debugging | 15 |
| negative-example | Maintenance | 23 |
| negative-example | DevOps | 13 |
| negative-example | Documentation | 17 |
| reference | Requirements | 13 |
| reference | Software Design | 44 |
| reference | Code Implementation | 94 |
| reference | Program Analysis | 47 |
| reference | Testing | 52 |
| reference | Debugging | 32 |
| reference | Maintenance | 51 |
| reference | DevOps | 31 |
| reference | Documentation | 37 |

## Python_All.json

- Dataset root: `Python_All`
- Total documents: 382
- Retained documents: 181 (47.38%)
- Filtered documents: 201 (52.62%)
- Avg labels / doc: 4.686
- Avg labels / retained doc: 8.779
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 133, 'filter-out': 21, 'outside-scope': 0, 'wrong-language': 47}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| purpose | 179 | 98.90 |
| action-directive | 176 | 97.24 |
| decision-rule | 175 | 96.69 |
| activation | 166 | 91.71 |
| workflow | 163 | 90.06 |
| reference | 141 | 77.90 |
| positive-example | 102 | 56.35 |
| exclusion | 76 | 41.99 |
| Testing | 66 | 36.46 |
| Code Implementation | 63 | 34.81 |
| Maintenance | 60 | 33.15 |
| Program Analysis | 47 | 25.97 |
| DevOps | 46 | 25.41 |
| Documentation | 38 | 20.99 |
| negative-example | 34 | 18.78 |
| Debugging | 21 | 11.60 |
| Software Design | 19 | 10.50 |
| Requirements | 17 | 9.39 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 201 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| purpose | 179 | 46.86 |
| activation | 166 | 43.46 |
| exclusion | 76 | 19.90 |
| workflow | 163 | 42.67 |
| decision-rule | 175 | 45.81 |
| action-directive | 176 | 46.07 |
| positive-example | 102 | 26.70 |
| negative-example | 34 | 8.90 |
| reference | 141 | 36.91 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Requirements | 17 | 9.39 |
| Software Design | 19 | 10.50 |
| Code Implementation | 63 | 34.81 |
| Program Analysis | 47 | 25.97 |
| Testing | 66 | 36.46 |
| Debugging | 21 | 11.60 |
| Maintenance | 60 | 33.15 |
| DevOps | 46 | 25.41 |
| Documentation | 38 | 20.99 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| purpose | Requirements | 17 |
| purpose | Software Design | 19 |
| purpose | Code Implementation | 62 |
| purpose | Program Analysis | 47 |
| purpose | Testing | 66 |
| purpose | Debugging | 21 |
| purpose | Maintenance | 59 |
| purpose | DevOps | 46 |
| purpose | Documentation | 38 |
| activation | Requirements | 17 |
| activation | Software Design | 19 |
| activation | Code Implementation | 60 |
| activation | Program Analysis | 42 |
| activation | Testing | 59 |
| activation | Debugging | 21 |
| activation | Maintenance | 53 |
| activation | DevOps | 39 |
| activation | Documentation | 35 |
| exclusion | Requirements | 10 |
| exclusion | Software Design | 10 |
| exclusion | Code Implementation | 23 |
| exclusion | Program Analysis | 21 |
| exclusion | Testing | 26 |
| exclusion | Debugging | 11 |
| exclusion | Maintenance | 25 |
| exclusion | DevOps | 20 |
| exclusion | Documentation | 18 |
| workflow | Requirements | 17 |
| workflow | Software Design | 18 |
| workflow | Code Implementation | 54 |
| workflow | Program Analysis | 46 |
| workflow | Testing | 62 |
| workflow | Debugging | 19 |
| workflow | Maintenance | 53 |
| workflow | DevOps | 41 |
| workflow | Documentation | 38 |
| decision-rule | Requirements | 17 |
| decision-rule | Software Design | 19 |
| decision-rule | Code Implementation | 60 |
| decision-rule | Program Analysis | 46 |
| decision-rule | Testing | 65 |
| decision-rule | Debugging | 21 |
| decision-rule | Maintenance | 60 |
| decision-rule | DevOps | 45 |
| decision-rule | Documentation | 36 |
| action-directive | Requirements | 17 |
| action-directive | Software Design | 19 |
| action-directive | Code Implementation | 59 |
| action-directive | Program Analysis | 46 |
| action-directive | Testing | 65 |
| action-directive | Debugging | 21 |
| action-directive | Maintenance | 59 |
| action-directive | DevOps | 46 |
| action-directive | Documentation | 37 |
| positive-example | Requirements | 11 |
| positive-example | Software Design | 13 |
| positive-example | Code Implementation | 44 |
| positive-example | Program Analysis | 25 |
| positive-example | Testing | 38 |
| positive-example | Debugging | 9 |
| positive-example | Maintenance | 32 |
| positive-example | DevOps | 19 |
| positive-example | Documentation | 25 |
| negative-example | Requirements | 3 |
| negative-example | Software Design | 8 |
| negative-example | Code Implementation | 13 |
| negative-example | Program Analysis | 8 |
| negative-example | Testing | 11 |
| negative-example | Debugging | 1 |
| negative-example | Maintenance | 15 |
| negative-example | DevOps | 7 |
| negative-example | Documentation | 6 |
| reference | Requirements | 13 |
| reference | Software Design | 16 |
| reference | Code Implementation | 56 |
| reference | Program Analysis | 37 |
| reference | Testing | 53 |
| reference | Debugging | 18 |
| reference | Maintenance | 46 |
| reference | DevOps | 35 |
| reference | Documentation | 32 |

## TypeScript_All.json

- Dataset root: `TypeScript_All`
- Total documents: 381
- Retained documents: 265 (69.55%)
- Filtered documents: 116 (30.45%)
- Avg labels / doc: 6.312
- Avg labels / retained doc: 8.638
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 72, 'filter-out': 18, 'outside-scope': 0, 'wrong-language': 26}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| purpose | 264 | 99.62 |
| decision-rule | 249 | 93.96 |
| action-directive | 247 | 93.21 |
| activation | 240 | 90.57 |
| positive-example | 194 | 73.21 |
| workflow | 188 | 70.94 |
| reference | 182 | 68.68 |
| Code Implementation | 137 | 51.70 |
| negative-example | 83 | 31.32 |
| exclusion | 80 | 30.19 |
| Testing | 76 | 28.68 |
| Maintenance | 65 | 24.53 |
| Program Analysis | 65 | 24.53 |
| Software Design | 57 | 21.51 |
| Documentation | 54 | 20.38 |
| DevOps | 44 | 16.60 |
| Debugging | 43 | 16.23 |
| Requirements | 21 | 7.92 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 116 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| purpose | 264 | 69.29 |
| activation | 240 | 62.99 |
| exclusion | 80 | 21.00 |
| workflow | 188 | 49.34 |
| decision-rule | 249 | 65.35 |
| action-directive | 247 | 64.83 |
| positive-example | 194 | 50.92 |
| negative-example | 83 | 21.78 |
| reference | 182 | 47.77 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Requirements | 21 | 7.92 |
| Software Design | 57 | 21.51 |
| Code Implementation | 137 | 51.70 |
| Program Analysis | 65 | 24.53 |
| Testing | 76 | 28.68 |
| Debugging | 43 | 16.23 |
| Maintenance | 65 | 24.53 |
| DevOps | 44 | 16.60 |
| Documentation | 54 | 20.38 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| purpose | Requirements | 21 |
| purpose | Software Design | 57 |
| purpose | Code Implementation | 136 |
| purpose | Program Analysis | 65 |
| purpose | Testing | 76 |
| purpose | Debugging | 43 |
| purpose | Maintenance | 65 |
| purpose | DevOps | 44 |
| purpose | Documentation | 54 |
| activation | Requirements | 18 |
| activation | Software Design | 52 |
| activation | Code Implementation | 125 |
| activation | Program Analysis | 60 |
| activation | Testing | 69 |
| activation | Debugging | 40 |
| activation | Maintenance | 61 |
| activation | DevOps | 42 |
| activation | Documentation | 51 |
| exclusion | Requirements | 9 |
| exclusion | Software Design | 18 |
| exclusion | Code Implementation | 43 |
| exclusion | Program Analysis | 20 |
| exclusion | Testing | 27 |
| exclusion | Debugging | 18 |
| exclusion | Maintenance | 19 |
| exclusion | DevOps | 15 |
| exclusion | Documentation | 17 |
| workflow | Requirements | 19 |
| workflow | Software Design | 42 |
| workflow | Code Implementation | 84 |
| workflow | Program Analysis | 53 |
| workflow | Testing | 67 |
| workflow | Debugging | 32 |
| workflow | Maintenance | 46 |
| workflow | DevOps | 40 |
| workflow | Documentation | 50 |
| decision-rule | Requirements | 20 |
| decision-rule | Software Design | 55 |
| decision-rule | Code Implementation | 126 |
| decision-rule | Program Analysis | 65 |
| decision-rule | Testing | 75 |
| decision-rule | Debugging | 42 |
| decision-rule | Maintenance | 62 |
| decision-rule | DevOps | 42 |
| decision-rule | Documentation | 53 |
| action-directive | Requirements | 21 |
| action-directive | Software Design | 55 |
| action-directive | Code Implementation | 126 |
| action-directive | Program Analysis | 64 |
| action-directive | Testing | 75 |
| action-directive | Debugging | 41 |
| action-directive | Maintenance | 59 |
| action-directive | DevOps | 42 |
| action-directive | Documentation | 51 |
| positive-example | Requirements | 19 |
| positive-example | Software Design | 40 |
| positive-example | Code Implementation | 102 |
| positive-example | Program Analysis | 53 |
| positive-example | Testing | 62 |
| positive-example | Debugging | 35 |
| positive-example | Maintenance | 45 |
| positive-example | DevOps | 33 |
| positive-example | Documentation | 38 |
| negative-example | Requirements | 6 |
| negative-example | Software Design | 17 |
| negative-example | Code Implementation | 40 |
| negative-example | Program Analysis | 24 |
| negative-example | Testing | 29 |
| negative-example | Debugging | 15 |
| negative-example | Maintenance | 23 |
| negative-example | DevOps | 13 |
| negative-example | Documentation | 17 |
| reference | Requirements | 13 |
| reference | Software Design | 44 |
| reference | Code Implementation | 94 |
| reference | Program Analysis | 47 |
| reference | Testing | 52 |
| reference | Debugging | 32 |
| reference | Maintenance | 51 |
| reference | DevOps | 31 |
| reference | Documentation | 37 |
