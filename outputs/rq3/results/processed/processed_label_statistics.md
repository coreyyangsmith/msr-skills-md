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
| 2026-04-19-MV_Relabels_Both_Python.json | 6 | 5 | 1 | 16.67 | 5 | 5 |
| 2026-04-19_CY_Final_Labels_A_Python.json | 151 | 74 | 77 | 50.99 | 73 | 71 |
| 2026-04-19_CY_Final_Labels_Both_Python.json | 52 | 28 | 24 | 46.15 | 28 | 28 |
| 2026-04-19_CY_Relabels_A_Python.json | 12 | 9 | 3 | 25.00 | 9 | 9 |
| 2026-04-19_CY_Relabels_Both_Python.json | 6 | 4 | 2 | 33.33 | 4 | 4 |
| 2026-04-19_MV_Final_Labels_B_Python.json | 156 | 96 | 60 | 38.46 | 96 | 96 |
| 2026-04-19_MV_Final_Labels_Both_Python.json | 52 | 29 | 23 | 44.23 | 29 | 29 |
| 2026-04-19_MV_Relabels_B_Python.json | 8 | 3 | 5 | 62.50 | 3 | 3 |
| Python_All.json | 359 | 198 | 161 | 44.85 | 197 | 195 |

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

## 2026-04-19-MV_Relabels_Both_Python.json

- Dataset root: `both`
- Total documents: 6
- Retained documents: 5 (83.33%)
- Filtered documents: 1 (16.67%)
- Avg labels / doc: 3.000
- Avg labels / retained doc: 3.400
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 0, 'outside-scope': 0, 'wrong-language': 1}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 4 | 80.00 |
| Code Generation | 3 | 60.00 |
| reference | 3 | 60.00 |
| Software Design | 2 | 40.00 |
| commands | 2 | 40.00 |
| descriptive | 1 | 20.00 |
| negative-examples | 1 | 20.00 |
| positive-examples | 1 | 20.00 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 1 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 2 | 33.33 |
| instructive | 4 | 66.67 |
| descriptive | 1 | 16.67 |
| reference | 3 | 50.00 |
| positive-examples | 1 | 16.67 |
| negative-examples | 1 | 16.67 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Software Design | 2 | 40.00 |
| Code Generation | 3 | 60.00 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Code Generation | 2 |
| instructive | Software Design | 2 |
| instructive | Code Generation | 2 |
| descriptive | Code Generation | 1 |
| reference | Software Design | 1 |
| reference | Code Generation | 2 |
| positive-examples | Code Generation | 1 |
| negative-examples | Software Design | 1 |

## 2026-04-19_CY_Final_Labels_A_Python.json

- Dataset root: `A`
- Total documents: 151
- Retained documents: 74 (49.01%)
- Filtered documents: 77 (50.99%)
- Avg labels / doc: 2.106
- Avg labels / retained doc: 3.257
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 60, 'outside-scope': 5, 'wrong-language': 12}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 46 | 62.16 |
| reference | 35 | 47.30 |
| descriptive | 32 | 43.24 |
| positive-examples | 29 | 39.19 |
| DevOps | 19 | 25.68 |
| Software Design | 16 | 21.62 |
| Software Testing | 16 | 21.62 |
| Code Generation | 15 | 20.27 |
| commands | 14 | 18.92 |
| Documentation | 12 | 16.22 |
| negative-examples | 4 | 5.41 |
| Requirements | 3 | 4.05 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 77 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 14 | 9.27 |
| instructive | 46 | 30.46 |
| descriptive | 32 | 21.19 |
| reference | 35 | 23.18 |
| positive-examples | 29 | 19.21 |
| negative-examples | 4 | 2.65 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 12 | 16.22 |
| Requirements | 3 | 4.05 |
| Software Design | 16 | 21.62 |
| Code Generation | 15 | 20.27 |
| Software Testing | 16 | 21.62 |
| DevOps | 19 | 25.68 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Software Design | 1 |
| commands | Code Generation | 2 |
| commands | Software Testing | 6 |
| commands | DevOps | 6 |
| instructive | Documentation | 9 |
| instructive | Requirements | 3 |
| instructive | Software Design | 12 |
| instructive | Code Generation | 6 |
| instructive | Software Testing | 9 |
| instructive | DevOps | 12 |
| descriptive | Documentation | 7 |
| descriptive | Requirements | 1 |
| descriptive | Software Design | 8 |
| descriptive | Code Generation | 3 |
| descriptive | Software Testing | 6 |
| descriptive | DevOps | 8 |
| reference | Documentation | 4 |
| reference | Requirements | 1 |
| reference | Software Design | 7 |
| reference | Code Generation | 7 |
| reference | Software Testing | 7 |
| reference | DevOps | 10 |
| positive-examples | Documentation | 4 |
| positive-examples | Software Design | 6 |
| positive-examples | Code Generation | 12 |
| positive-examples | Software Testing | 5 |
| positive-examples | DevOps | 4 |
| negative-examples | Code Generation | 3 |
| negative-examples | Software Testing | 3 |

## 2026-04-19_CY_Final_Labels_Both_Python.json

- Dataset root: `both`
- Total documents: 52
- Retained documents: 28 (53.85%)
- Filtered documents: 24 (46.15%)
- Avg labels / doc: 2.462
- Avg labels / retained doc: 3.714
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 19, 'outside-scope': 3, 'wrong-language': 2}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 20 | 71.43 |
| descriptive | 16 | 57.14 |
| reference | 15 | 53.57 |
| Software Testing | 11 | 39.29 |
| commands | 11 | 39.29 |
| Code Generation | 7 | 25.00 |
| Software Design | 7 | 25.00 |
| positive-examples | 7 | 25.00 |
| DevOps | 5 | 17.86 |
| Requirements | 2 | 7.14 |
| negative-examples | 2 | 7.14 |
| Documentation | 1 | 3.57 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 24 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 11 | 21.15 |
| instructive | 20 | 38.46 |
| descriptive | 16 | 30.77 |
| reference | 15 | 28.85 |
| positive-examples | 7 | 13.46 |
| negative-examples | 2 | 3.85 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 1 | 3.57 |
| Requirements | 2 | 7.14 |
| Software Design | 7 | 25.00 |
| Code Generation | 7 | 25.00 |
| Software Testing | 11 | 39.29 |
| DevOps | 5 | 17.86 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Code Generation | 3 |
| commands | Software Testing | 5 |
| commands | DevOps | 4 |
| instructive | Documentation | 1 |
| instructive | Requirements | 2 |
| instructive | Software Design | 5 |
| instructive | Code Generation | 4 |
| instructive | Software Testing | 9 |
| instructive | DevOps | 3 |
| descriptive | Requirements | 2 |
| descriptive | Software Design | 5 |
| descriptive | Code Generation | 5 |
| descriptive | Software Testing | 5 |
| descriptive | DevOps | 4 |
| reference | Requirements | 1 |
| reference | Software Design | 5 |
| reference | Code Generation | 6 |
| reference | Software Testing | 5 |
| reference | DevOps | 2 |
| positive-examples | Documentation | 1 |
| positive-examples | Requirements | 1 |
| positive-examples | Software Design | 1 |
| positive-examples | Code Generation | 4 |
| positive-examples | Software Testing | 1 |
| negative-examples | Software Design | 1 |
| negative-examples | DevOps | 1 |

## 2026-04-19_CY_Relabels_A_Python.json

- Dataset root: `A`
- Total documents: 12
- Retained documents: 9 (75.00%)
- Filtered documents: 3 (25.00%)
- Avg labels / doc: 2.917
- Avg labels / retained doc: 3.556
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 0, 'outside-scope': 0, 'wrong-language': 3}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| reference | 7 | 77.78 |
| instructive | 5 | 55.56 |
| positive-examples | 4 | 44.44 |
| DevOps | 3 | 33.33 |
| Software Testing | 3 | 33.33 |
| descriptive | 3 | 33.33 |
| Software Design | 2 | 22.22 |
| commands | 2 | 22.22 |
| negative-examples | 2 | 22.22 |
| Code Generation | 1 | 11.11 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 3 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 2 | 16.67 |
| instructive | 5 | 41.67 |
| descriptive | 3 | 25.00 |
| reference | 7 | 58.33 |
| positive-examples | 4 | 33.33 |
| negative-examples | 2 | 16.67 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Software Design | 2 | 22.22 |
| Code Generation | 1 | 11.11 |
| Software Testing | 3 | 33.33 |
| DevOps | 3 | 33.33 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Software Testing | 1 |
| commands | DevOps | 1 |
| instructive | Software Design | 2 |
| instructive | Code Generation | 1 |
| instructive | Software Testing | 1 |
| instructive | DevOps | 1 |
| descriptive | Software Testing | 1 |
| descriptive | DevOps | 2 |
| reference | Software Design | 2 |
| reference | Software Testing | 2 |
| reference | DevOps | 3 |
| positive-examples | Code Generation | 1 |
| positive-examples | Software Testing | 2 |
| positive-examples | DevOps | 1 |
| negative-examples | Code Generation | 1 |
| negative-examples | Software Testing | 1 |

## 2026-04-19_CY_Relabels_Both_Python.json

- Dataset root: `both`
- Total documents: 6
- Retained documents: 4 (66.67%)
- Filtered documents: 2 (33.33%)
- Avg labels / doc: 2.833
- Avg labels / retained doc: 3.750
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 1, 'outside-scope': 0, 'wrong-language': 1}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 4 | 100.00 |
| reference | 3 | 75.00 |
| Code Generation | 2 | 50.00 |
| Software Design | 2 | 50.00 |
| commands | 1 | 25.00 |
| descriptive | 1 | 25.00 |
| negative-examples | 1 | 25.00 |
| positive-examples | 1 | 25.00 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 2 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 1 | 16.67 |
| instructive | 4 | 66.67 |
| descriptive | 1 | 16.67 |
| reference | 3 | 50.00 |
| positive-examples | 1 | 16.67 |
| negative-examples | 1 | 16.67 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Software Design | 2 | 50.00 |
| Code Generation | 2 | 50.00 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Code Generation | 1 |
| instructive | Software Design | 2 |
| instructive | Code Generation | 2 |
| descriptive | Code Generation | 1 |
| reference | Software Design | 1 |
| reference | Code Generation | 2 |
| positive-examples | Code Generation | 1 |
| negative-examples | Software Design | 1 |

## 2026-04-19_MV_Final_Labels_B_Python.json

- Dataset root: `B`
- Total documents: 156
- Retained documents: 96 (61.54%)
- Filtered documents: 60 (38.46%)
- Avg labels / doc: 2.077
- Avg labels / retained doc: 2.750
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 37, 'outside-scope': 12, 'wrong-language': 11}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 64 | 66.67 |
| reference | 35 | 36.46 |
| Code Generation | 32 | 33.33 |
| Software Testing | 27 | 28.12 |
| positive-examples | 18 | 18.75 |
| DevOps | 17 | 17.71 |
| commands | 17 | 17.71 |
| Documentation | 16 | 16.67 |
| descriptive | 14 | 14.58 |
| Software Design | 9 | 9.38 |
| negative-examples | 8 | 8.33 |
| Requirements | 7 | 7.29 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 60 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 17 | 10.90 |
| instructive | 64 | 41.03 |
| descriptive | 14 | 8.97 |
| reference | 35 | 22.44 |
| positive-examples | 18 | 11.54 |
| negative-examples | 8 | 5.13 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 16 | 16.67 |
| Requirements | 7 | 7.29 |
| Software Design | 9 | 9.38 |
| Code Generation | 32 | 33.33 |
| Software Testing | 27 | 28.12 |
| DevOps | 17 | 17.71 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Documentation | 1 |
| commands | Software Design | 2 |
| commands | Code Generation | 8 |
| commands | Software Testing | 4 |
| commands | DevOps | 4 |
| instructive | Documentation | 13 |
| instructive | Requirements | 5 |
| instructive | Software Design | 5 |
| instructive | Code Generation | 22 |
| instructive | Software Testing | 18 |
| instructive | DevOps | 10 |
| descriptive | Documentation | 3 |
| descriptive | Software Design | 1 |
| descriptive | Code Generation | 3 |
| descriptive | Software Testing | 4 |
| descriptive | DevOps | 3 |
| reference | Documentation | 3 |
| reference | Requirements | 3 |
| reference | Software Design | 5 |
| reference | Code Generation | 13 |
| reference | Software Testing | 12 |
| reference | DevOps | 5 |
| positive-examples | Documentation | 2 |
| positive-examples | Requirements | 1 |
| positive-examples | Code Generation | 5 |
| positive-examples | Software Testing | 3 |
| positive-examples | DevOps | 7 |
| negative-examples | Requirements | 1 |
| negative-examples | Code Generation | 2 |
| negative-examples | Software Testing | 4 |
| negative-examples | DevOps | 1 |

## 2026-04-19_MV_Final_Labels_Both_Python.json

- Dataset root: `both`
- Total documents: 52
- Retained documents: 29 (55.77%)
- Filtered documents: 23 (44.23%)
- Avg labels / doc: 2.558
- Avg labels / retained doc: 3.793
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 18, 'outside-scope': 3, 'wrong-language': 3}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| descriptive | 21 | 72.41 |
| instructive | 15 | 51.72 |
| commands | 14 | 48.28 |
| reference | 14 | 48.28 |
| Code Generation | 11 | 37.93 |
| Software Testing | 11 | 37.93 |
| negative-examples | 7 | 24.14 |
| Software Design | 6 | 20.69 |
| DevOps | 5 | 17.24 |
| Documentation | 3 | 10.34 |
| positive-examples | 3 | 10.34 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 23 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 14 | 26.92 |
| instructive | 15 | 28.85 |
| descriptive | 21 | 40.38 |
| reference | 14 | 26.92 |
| positive-examples | 3 | 5.77 |
| negative-examples | 7 | 13.46 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 3 | 10.34 |
| Software Design | 6 | 20.69 |
| Code Generation | 11 | 37.93 |
| Software Testing | 11 | 37.93 |
| DevOps | 5 | 17.24 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Documentation | 1 |
| commands | Software Design | 2 |
| commands | Code Generation | 7 |
| commands | Software Testing | 4 |
| commands | DevOps | 3 |
| instructive | Documentation | 3 |
| instructive | Software Design | 3 |
| instructive | Code Generation | 4 |
| instructive | Software Testing | 6 |
| instructive | DevOps | 1 |
| descriptive | Documentation | 2 |
| descriptive | Software Design | 4 |
| descriptive | Code Generation | 7 |
| descriptive | Software Testing | 11 |
| descriptive | DevOps | 4 |
| reference | Documentation | 1 |
| reference | Software Design | 4 |
| reference | Code Generation | 7 |
| reference | Software Testing | 4 |
| reference | DevOps | 2 |
| positive-examples | Documentation | 1 |
| positive-examples | Code Generation | 2 |
| positive-examples | Software Testing | 1 |
| negative-examples | Documentation | 1 |
| negative-examples | Software Design | 2 |
| negative-examples | Code Generation | 1 |
| negative-examples | Software Testing | 3 |
| negative-examples | DevOps | 2 |

## 2026-04-19_MV_Relabels_B_Python.json

- Dataset root: `B`
- Total documents: 8
- Retained documents: 3 (37.50%)
- Filtered documents: 5 (62.50%)
- Avg labels / doc: 2.125
- Avg labels / retained doc: 4.000
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 1, 'outside-scope': 0, 'wrong-language': 4}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| Software Design | 2 | 66.67 |
| instructive | 2 | 66.67 |
| reference | 2 | 66.67 |
| Code Generation | 1 | 33.33 |
| Requirements | 1 | 33.33 |
| Software Testing | 1 | 33.33 |
| commands | 1 | 33.33 |
| negative-examples | 1 | 33.33 |
| positive-examples | 1 | 33.33 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 5 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 1 | 12.50 |
| instructive | 2 | 25.00 |
| reference | 2 | 25.00 |
| positive-examples | 1 | 12.50 |
| negative-examples | 1 | 12.50 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Requirements | 1 | 33.33 |
| Software Design | 2 | 66.67 |
| Code Generation | 1 | 33.33 |
| Software Testing | 1 | 33.33 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Software Design | 1 |
| commands | Code Generation | 1 |
| instructive | Requirements | 1 |
| instructive | Software Design | 2 |
| instructive | Code Generation | 1 |
| reference | Requirements | 1 |
| reference | Software Design | 2 |
| reference | Code Generation | 1 |
| positive-examples | Software Testing | 1 |
| negative-examples | Software Testing | 1 |

## Python_All.json

- Dataset root: `Python_All`
- Total documents: 359
- Retained documents: 198 (55.15%)
- Filtered documents: 161 (44.85%)
- Avg labels / doc: 2.145
- Avg labels / retained doc: 3.076
- Avg labels / filtered doc: 1.000
- Filter source counts: `{'agent-skill': 116, 'outside-scope': 20, 'wrong-language': 25}`

### Label Distribution (Retained)
| Label | Count | % Docs |
| --- | ---: | ---: |
| instructive | 130 | 65.66 |
| reference | 85 | 42.93 |
| descriptive | 62 | 31.31 |
| Code Generation | 54 | 27.27 |
| Software Testing | 54 | 27.27 |
| positive-examples | 54 | 27.27 |
| commands | 42 | 21.21 |
| DevOps | 41 | 20.71 |
| Software Design | 32 | 16.16 |
| Documentation | 29 | 14.65 |
| negative-examples | 14 | 7.07 |
| Requirements | 12 | 6.06 |

### Label Distribution (Filtered)
| Label | Count | % Docs |
| --- | ---: | ---: |
| filter | 161 | 100.00 |

### Instruction Type Distribution (All)
| Instruction Type | Count | % Docs |
| --- | ---: | ---: |
| commands | 42 | 11.70 |
| instructive | 130 | 36.21 |
| descriptive | 62 | 17.27 |
| reference | 85 | 23.68 |
| positive-examples | 54 | 15.04 |
| negative-examples | 14 | 3.90 |

### SDLC Stage Distribution (Retained)
| SDLC Stage | Count | % Docs |
| --- | ---: | ---: |
| Documentation | 29 | 14.65 |
| Requirements | 12 | 6.06 |
| Software Design | 32 | 16.16 |
| Code Generation | 54 | 27.27 |
| Software Testing | 54 | 27.27 |
| DevOps | 41 | 20.71 |

### Instruction x SDLC Stage (Retained)
| Instruction Type | SDLC Stage | Count |
| --- | ---: | ---: |
| commands | Documentation | 1 |
| commands | Software Design | 3 |
| commands | Code Generation | 13 |
| commands | Software Testing | 15 |
| commands | DevOps | 14 |
| instructive | Documentation | 23 |
| instructive | Requirements | 10 |
| instructive | Software Design | 22 |
| instructive | Code Generation | 32 |
| instructive | Software Testing | 36 |
| instructive | DevOps | 25 |
| descriptive | Documentation | 10 |
| descriptive | Requirements | 3 |
| descriptive | Software Design | 14 |
| descriptive | Code Generation | 11 |
| descriptive | Software Testing | 15 |
| descriptive | DevOps | 15 |
| reference | Documentation | 7 |
| reference | Requirements | 5 |
| reference | Software Design | 17 |
| reference | Code Generation | 26 |
| reference | Software Testing | 24 |
| reference | DevOps | 17 |
| positive-examples | Documentation | 7 |
| positive-examples | Requirements | 2 |
| positive-examples | Software Design | 7 |
| positive-examples | Code Generation | 21 |
| positive-examples | Software Testing | 9 |
| positive-examples | DevOps | 11 |
| negative-examples | Requirements | 1 |
| negative-examples | Software Design | 1 |
| negative-examples | Code Generation | 5 |
| negative-examples | Software Testing | 7 |
| negative-examples | DevOps | 2 |
