# Processed RQ3 Label Statistics

Processed vs filtered comparisons are document-level, not repo-level.

## Overview
| File | Docs | Retained | Filtered | Filtered % | Any SDLC | Any Instruction |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-03-28_CY_Labels_Both_Python.json | 56 | 36 | 20 | 35.71 | 35 | 36 |
| 2026-03-29_CY_Labels_Both_TS.json | 56 | 32 | 24 | 42.86 | 32 | 32 |
| 2026-03-31_MV_Labels_Both_Python.json | 56 | 30 | 26 | 46.43 | 30 | 30 |
| 2026-04-02_CY_Labels_Both_Python.json | 56 | 29 | 27 | 48.21 | 29 | 29 |
| 2026-04-06_CY_Labels_A_Python.json | 156 | 73 | 83 | 53.21 | 72 | 68 |
| 2026-04-06_MV_Labels_B_Python.json | 156 | 96 | 60 | 38.46 | 96 | 96 |
| 2026-04-06_MV_Labels_Both_Python.json | 56 | 31 | 25 | 44.64 | 31 | 31 |
| Python_All.json | 368 | 198 | 170 | 46.20 | 197 | 193 |

## 2026-03-28_CY_Labels_Both_Python.json

- Dataset root: `both`
- Total documents: 56
- Retained documents: 36 (64.29%)
- Filtered documents: 20 (35.71%)
- Avg labels / doc: 2.268
- Avg labels / retained doc: 2.972
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 12, 'outside-scope': 6, 'wrong-language': 2}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 23 | 63.89 |
| descriptive | 22 | 61.11 |
| Code Generation | 12 | 33.33 |
| Software Testing | 12 | 33.33 |
| reference | 9 | 25.00 |
| commands | 8 | 22.22 |
| positive-examples | 7 | 19.44 |
| Software Design | 6 | 16.67 |
| Requirements | 3 | 8.33 |
| negative-examples | 3 | 8.33 |
| DevOps | 2 | 5.56 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 20 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 8 | 14.29 |
| instructive | 23 | 41.07 |
| descriptive | 22 | 39.29 |
| reference | 9 | 16.07 |
| positive-examples | 7 | 12.50 |
| negative-examples | 3 | 5.36 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Requirements | 3 | 8.33 |
| Software Design | 6 | 16.67 |
| Code Generation | 12 | 33.33 |
| Software Testing | 12 | 33.33 |
| DevOps | 2 | 5.56 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Code Generation | 3 |
| commands | Software Testing | 3 |
| commands | DevOps | 2 |
| instructive | Requirements | 2 |
| instructive | Software Design | 2 |
| instructive | Code Generation | 7 |
| instructive | Software Testing | 9 |
| instructive | DevOps | 2 |
| descriptive | Requirements | 3 |
| descriptive | Software Design | 5 |
| descriptive | Code Generation | 8 |
| descriptive | Software Testing | 5 |
| descriptive | DevOps | 1 |
| reference | Software Design | 3 |
| reference | Code Generation | 3 |
| reference | Software Testing | 3 |
| positive-examples | Requirements | 1 |
| positive-examples | Software Design | 3 |
| positive-examples | Code Generation | 1 |
| positive-examples | Software Testing | 2 |
| negative-examples | Requirements | 1 |
| negative-examples | Software Design | 1 |
| negative-examples | DevOps | 1 |

## 2026-03-29_CY_Labels_Both_TS.json

- Dataset root: `both`
- Total documents: 56
- Retained documents: 32 (57.14%)
- Filtered documents: 24 (42.86%)
- Avg labels / doc: 2.393
- Avg labels / retained doc: 3.438
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 16, 'outside-scope': 2, 'wrong-language': 6}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| descriptive | 24 | 75.00 |
| positive-examples | 17 | 53.12 |
| instructive | 13 | 40.62 |
| Code Generation | 12 | 37.50 |
| reference | 9 | 28.12 |
| Software Testing | 8 | 25.00 |
| negative-examples | 8 | 25.00 |
| commands | 7 | 21.88 |
| Documentation | 5 | 15.62 |
| DevOps | 4 | 12.50 |
| Software Design | 3 | 9.38 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 24 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 7 | 12.50 |
| instructive | 13 | 23.21 |
| descriptive | 24 | 42.86 |
| reference | 9 | 16.07 |
| positive-examples | 17 | 30.36 |
| negative-examples | 8 | 14.29 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 5 | 15.62 |
| Software Design | 3 | 9.38 |
| Code Generation | 12 | 37.50 |
| Software Testing | 8 | 25.00 |
| DevOps | 4 | 12.50 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Documentation | 1 |
| commands | Software Design | 1 |
| commands | Software Testing | 2 |
| commands | DevOps | 3 |
| instructive | Documentation | 4 |
| instructive | Software Design | 1 |
| instructive | Code Generation | 3 |
| instructive | Software Testing | 5 |
| descriptive | Documentation | 2 |
| descriptive | Software Design | 3 |
| descriptive | Code Generation | 10 |
| descriptive | Software Testing | 7 |
| descriptive | DevOps | 2 |
| reference | Documentation | 1 |
| reference | Code Generation | 5 |
| reference | Software Testing | 2 |
| reference | DevOps | 1 |
| positive-examples | Documentation | 4 |
| positive-examples | Code Generation | 8 |
| positive-examples | Software Testing | 4 |
| positive-examples | DevOps | 1 |
| negative-examples | Documentation | 1 |
| negative-examples | Code Generation | 5 |
| negative-examples | Software Testing | 2 |

## 2026-03-31_MV_Labels_Both_Python.json

- Dataset root: `both`
- Total documents: 56
- Retained documents: 30 (53.57%)
- Filtered documents: 26 (46.43%)
- Avg labels / doc: 2.589
- Avg labels / retained doc: 3.967
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 22, 'outside-scope': 3, 'wrong-language': 2}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| descriptive | 25 | 83.33 |
| reference | 15 | 50.00 |
| instructive | 14 | 46.67 |
| commands | 13 | 43.33 |
| Code Generation | 11 | 36.67 |
| Software Testing | 11 | 36.67 |
| Software Design | 8 | 26.67 |
| negative-examples | 8 | 26.67 |
| DevOps | 5 | 16.67 |
| Documentation | 4 | 13.33 |
| positive-examples | 4 | 13.33 |
| Requirements | 1 | 3.33 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 26 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 13 | 23.21 |
| instructive | 14 | 25.00 |
| descriptive | 25 | 44.64 |
| reference | 15 | 26.79 |
| positive-examples | 4 | 7.14 |
| negative-examples | 8 | 14.29 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 4 | 13.33 |
| Requirements | 1 | 3.33 |
| Software Design | 8 | 26.67 |
| Code Generation | 11 | 36.67 |
| Software Testing | 11 | 36.67 |
| DevOps | 5 | 16.67 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Documentation | 1 |
| commands | Software Design | 2 |
| commands | Code Generation | 6 |
| commands | Software Testing | 4 |
| commands | DevOps | 3 |
| instructive | Documentation | 3 |
| instructive | Software Design | 4 |
| instructive | Code Generation | 4 |
| instructive | Software Testing | 6 |
| instructive | DevOps | 1 |
| descriptive | Documentation | 3 |
| descriptive | Requirements | 1 |
| descriptive | Software Design | 7 |
| descriptive | Code Generation | 9 |
| descriptive | Software Testing | 11 |
| descriptive | DevOps | 4 |
| reference | Documentation | 2 |
| reference | Software Design | 5 |
| reference | Code Generation | 8 |
| reference | Software Testing | 4 |
| reference | DevOps | 2 |
| positive-examples | Documentation | 2 |
| positive-examples | Software Design | 1 |
| positive-examples | Code Generation | 2 |
| positive-examples | Software Testing | 1 |
| negative-examples | Documentation | 2 |
| negative-examples | Software Design | 2 |
| negative-examples | Code Generation | 2 |
| negative-examples | Software Testing | 3 |
| negative-examples | DevOps | 2 |

## 2026-04-02_CY_Labels_Both_Python.json

- Dataset root: `both`
- Total documents: 56
- Retained documents: 29 (51.79%)
- Filtered documents: 27 (48.21%)
- Avg labels / doc: 2.429
- Avg labels / retained doc: 3.759
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 22, 'outside-scope': 4, 'wrong-language': 1}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 20 | 68.97 |
| descriptive | 19 | 65.52 |
| reference | 15 | 51.72 |
| Software Testing | 11 | 37.93 |
| commands | 10 | 34.48 |
| Software Design | 8 | 27.59 |
| positive-examples | 8 | 27.59 |
| Code Generation | 6 | 20.69 |
| DevOps | 5 | 17.24 |
| Requirements | 3 | 10.34 |
| Documentation | 2 | 6.90 |
| negative-examples | 2 | 6.90 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 27 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 10 | 17.86 |
| instructive | 20 | 35.71 |
| descriptive | 19 | 33.93 |
| reference | 15 | 26.79 |
| positive-examples | 8 | 14.29 |
| negative-examples | 2 | 3.57 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 2 | 6.90 |
| Requirements | 3 | 10.34 |
| Software Design | 8 | 27.59 |
| Code Generation | 6 | 20.69 |
| Software Testing | 11 | 37.93 |
| DevOps | 5 | 17.24 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Code Generation | 2 |
| commands | Software Testing | 5 |
| commands | DevOps | 4 |
| instructive | Documentation | 1 |
| instructive | Requirements | 3 |
| instructive | Software Design | 6 |
| instructive | Code Generation | 3 |
| instructive | Software Testing | 9 |
| instructive | DevOps | 3 |
| descriptive | Documentation | 1 |
| descriptive | Requirements | 3 |
| descriptive | Software Design | 7 |
| descriptive | Code Generation | 5 |
| descriptive | Software Testing | 5 |
| descriptive | DevOps | 4 |
| reference | Documentation | 1 |
| reference | Requirements | 1 |
| reference | Software Design | 5 |
| reference | Code Generation | 5 |
| reference | Software Testing | 5 |
| reference | DevOps | 2 |
| positive-examples | Documentation | 2 |
| positive-examples | Requirements | 1 |
| positive-examples | Software Design | 1 |
| positive-examples | Code Generation | 4 |
| positive-examples | Software Testing | 1 |
| negative-examples | Documentation | 1 |
| negative-examples | DevOps | 1 |

## 2026-04-06_CY_Labels_A_Python.json

- Dataset root: `A`
- Total documents: 156
- Retained documents: 73 (46.79%)
- Filtered documents: 83 (53.21%)
- Avg labels / doc: 1.987
- Avg labels / retained doc: 3.110
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 67, 'outside-scope': 5, 'wrong-language': 11}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 44 | 60.27 |
| descriptive | 31 | 42.47 |
| reference | 30 | 41.10 |
| positive-examples | 26 | 35.62 |
| DevOps | 20 | 27.40 |
| Software Testing | 17 | 23.29 |
| Code Generation | 14 | 19.18 |
| Software Design | 14 | 19.18 |
| commands | 14 | 19.18 |
| Documentation | 12 | 16.44 |
| Requirements | 3 | 4.11 |
| negative-examples | 2 | 2.74 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 83 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 14 | 8.97 |
| instructive | 44 | 28.21 |
| descriptive | 31 | 19.87 |
| reference | 30 | 19.23 |
| positive-examples | 26 | 16.67 |
| negative-examples | 2 | 1.28 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 12 | 16.44 |
| Requirements | 3 | 4.11 |
| Software Design | 14 | 19.18 |
| Code Generation | 14 | 19.18 |
| Software Testing | 17 | 23.29 |
| DevOps | 20 | 27.40 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Software Design | 1 |
| commands | Code Generation | 2 |
| commands | Software Testing | 5 |
| commands | DevOps | 7 |
| instructive | Documentation | 9 |
| instructive | Requirements | 3 |
| instructive | Software Design | 10 |
| instructive | Code Generation | 5 |
| instructive | Software Testing | 10 |
| instructive | DevOps | 12 |
| descriptive | Documentation | 7 |
| descriptive | Requirements | 1 |
| descriptive | Software Design | 8 |
| descriptive | Code Generation | 3 |
| descriptive | Software Testing | 5 |
| descriptive | DevOps | 8 |
| reference | Documentation | 4 |
| reference | Requirements | 1 |
| reference | Software Design | 5 |
| reference | Code Generation | 7 |
| reference | Software Testing | 5 |
| reference | DevOps | 9 |
| positive-examples | Documentation | 4 |
| positive-examples | Software Design | 6 |
| positive-examples | Code Generation | 11 |
| positive-examples | Software Testing | 3 |
| positive-examples | DevOps | 4 |
| negative-examples | Code Generation | 2 |
| negative-examples | Software Testing | 2 |

## 2026-04-06_MV_Labels_B_Python.json

- Dataset root: `B`
- Total documents: 156
- Retained documents: 96 (61.54%)
- Filtered documents: 60 (38.46%)
- Avg labels / doc: 2.045
- Avg labels / retained doc: 2.698
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 40, 'outside-scope': 13, 'wrong-language': 7}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 65 | 67.71 |
| reference | 34 | 35.42 |
| Code Generation | 32 | 33.33 |
| Software Testing | 28 | 29.17 |
| DevOps | 17 | 17.71 |
| positive-examples | 17 | 17.71 |
| Documentation | 16 | 16.67 |
| commands | 16 | 16.67 |
| descriptive | 14 | 14.58 |
| Software Design | 7 | 7.29 |
| negative-examples | 7 | 7.29 |
| Requirements | 6 | 6.25 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 60 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 16 | 10.26 |
| instructive | 65 | 41.67 |
| descriptive | 14 | 8.97 |
| reference | 34 | 21.79 |
| positive-examples | 17 | 10.90 |
| negative-examples | 7 | 4.49 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 16 | 16.67 |
| Requirements | 6 | 6.25 |
| Software Design | 7 | 7.29 |
| Code Generation | 32 | 33.33 |
| Software Testing | 28 | 29.17 |
| DevOps | 17 | 17.71 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Documentation | 1 |
| commands | Software Design | 1 |
| commands | Code Generation | 7 |
| commands | Software Testing | 4 |
| commands | DevOps | 4 |
| instructive | Documentation | 13 |
| instructive | Requirements | 4 |
| instructive | Software Design | 3 |
| instructive | Code Generation | 22 |
| instructive | Software Testing | 20 |
| instructive | DevOps | 10 |
| descriptive | Documentation | 3 |
| descriptive | Software Design | 1 |
| descriptive | Code Generation | 3 |
| descriptive | Software Testing | 4 |
| descriptive | DevOps | 3 |
| reference | Documentation | 3 |
| reference | Requirements | 2 |
| reference | Software Design | 3 |
| reference | Code Generation | 13 |
| reference | Software Testing | 12 |
| reference | DevOps | 5 |
| positive-examples | Documentation | 2 |
| positive-examples | Requirements | 1 |
| positive-examples | Code Generation | 5 |
| positive-examples | Software Testing | 2 |
| positive-examples | DevOps | 7 |
| negative-examples | Requirements | 1 |
| negative-examples | Code Generation | 2 |
| negative-examples | Software Testing | 3 |
| negative-examples | DevOps | 1 |

## 2026-04-06_MV_Labels_Both_Python.json

- Dataset root: `both`
- Total documents: 56
- Retained documents: 31 (55.36%)
- Filtered documents: 25 (44.64%)
- Avg labels / doc: 2.643
- Avg labels / retained doc: 3.968
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 21, 'outside-scope': 3, 'wrong-language': 2}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| descriptive | 26 | 83.87 |
| instructive | 17 | 54.84 |
| commands | 14 | 45.16 |
| reference | 14 | 45.16 |
| Code Generation | 13 | 41.94 |
| Software Testing | 10 | 32.26 |
| Software Design | 8 | 25.81 |
| negative-examples | 7 | 22.58 |
| DevOps | 5 | 16.13 |
| Documentation | 4 | 12.90 |
| positive-examples | 4 | 12.90 |
| Requirements | 1 | 3.23 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 25 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 14 | 25.00 |
| instructive | 17 | 30.36 |
| descriptive | 26 | 46.43 |
| reference | 14 | 25.00 |
| positive-examples | 4 | 7.14 |
| negative-examples | 7 | 12.50 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 4 | 12.90 |
| Requirements | 1 | 3.23 |
| Software Design | 8 | 25.81 |
| Code Generation | 13 | 41.94 |
| Software Testing | 10 | 32.26 |
| DevOps | 5 | 16.13 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Documentation | 1 |
| commands | Software Design | 2 |
| commands | Code Generation | 8 |
| commands | Software Testing | 3 |
| commands | DevOps | 3 |
| instructive | Documentation | 3 |
| instructive | Requirements | 1 |
| instructive | Software Design | 5 |
| instructive | Code Generation | 7 |
| instructive | Software Testing | 6 |
| instructive | DevOps | 1 |
| descriptive | Documentation | 3 |
| descriptive | Requirements | 1 |
| descriptive | Software Design | 7 |
| descriptive | Code Generation | 11 |
| descriptive | Software Testing | 10 |
| descriptive | DevOps | 4 |
| reference | Documentation | 2 |
| reference | Software Design | 5 |
| reference | Code Generation | 8 |
| reference | Software Testing | 3 |
| reference | DevOps | 2 |
| positive-examples | Documentation | 2 |
| positive-examples | Software Design | 1 |
| positive-examples | Code Generation | 2 |
| positive-examples | Software Testing | 1 |
| negative-examples | Documentation | 2 |
| negative-examples | Software Design | 1 |
| negative-examples | Code Generation | 2 |
| negative-examples | Software Testing | 2 |
| negative-examples | DevOps | 2 |

## Python_All.json

- Dataset root: `Python_All`
- Total documents: 368
- Retained documents: 198 (53.80%)
- Filtered documents: 170 (46.20%)
- Avg labels / doc: 2.079
- Avg labels / retained doc: 3.005
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 129, 'outside-scope': 22, 'wrong-language': 19}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 129 | 65.15 |
| reference | 79 | 39.90 |
| descriptive | 64 | 32.32 |
| Software Testing | 56 | 28.28 |
| Code Generation | 52 | 26.26 |
| positive-examples | 51 | 25.76 |
| DevOps | 42 | 21.21 |
| commands | 40 | 20.20 |
| Documentation | 30 | 15.15 |
| Software Design | 29 | 14.65 |
| Requirements | 12 | 6.06 |
| negative-examples | 11 | 5.56 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 170 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 40 | 10.87 |
| instructive | 129 | 35.05 |
| descriptive | 64 | 17.39 |
| reference | 79 | 21.47 |
| positive-examples | 51 | 13.86 |
| negative-examples | 11 | 2.99 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 30 | 15.15 |
| Requirements | 12 | 6.06 |
| Software Design | 29 | 14.65 |
| Code Generation | 52 | 26.26 |
| Software Testing | 56 | 28.28 |
| DevOps | 42 | 21.21 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Documentation | 1 |
| commands | Software Design | 2 |
| commands | Code Generation | 11 |
| commands | Software Testing | 14 |
| commands | DevOps | 15 |
| instructive | Documentation | 23 |
| instructive | Requirements | 10 |
| instructive | Software Design | 19 |
| instructive | Code Generation | 30 |
| instructive | Software Testing | 39 |
| instructive | DevOps | 25 |
| descriptive | Documentation | 11 |
| descriptive | Requirements | 4 |
| descriptive | Software Design | 16 |
| descriptive | Code Generation | 11 |
| descriptive | Software Testing | 14 |
| descriptive | DevOps | 15 |
| reference | Documentation | 8 |
| reference | Requirements | 4 |
| reference | Software Design | 13 |
| reference | Code Generation | 25 |
| reference | Software Testing | 22 |
| reference | DevOps | 16 |
| positive-examples | Documentation | 8 |
| positive-examples | Requirements | 2 |
| positive-examples | Software Design | 7 |
| positive-examples | Code Generation | 20 |
| positive-examples | Software Testing | 6 |
| positive-examples | DevOps | 11 |
| negative-examples | Documentation | 1 |
| negative-examples | Requirements | 1 |
| negative-examples | Code Generation | 4 |
| negative-examples | Software Testing | 5 |
| negative-examples | DevOps | 2 |
