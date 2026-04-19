#!/usr/bin/env python3
"""Process the four Final Label exports into outputs/rq3/results/processed/."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from rq3.label_processing import build_processed_export, load_json, write_json

REPO = Path(__file__).resolve().parents[1]
RESULTS = REPO / "outputs" / "rq3" / "results"
PROCESSED = RESULTS / "processed"

FINALS = [
    "2026-04-19_CY_Final_Labels_A_Python.json",
    "2026-04-19_CY_Final_Labels_Both_Python.json",
    "2026-04-19_MV_Final_Labels_B_Python.json",
    "2026-04-19_MV_Final_Labels_Both_Python.json",
]


def main() -> None:
    for name in FINALS:
        path = RESULTS / name
        data = load_json(path)
        out = build_processed_export(data, source_name=name)
        out_path = PROCESSED / name
        write_json(out_path, out)
        counts = out["processing"]["counts"]
        fc = out["processing"]["filter_source_document_counts"]
        total = counts["documents"]
        filtered = counts["documents_collapsed_to_filter"]
        retained = total - filtered
        filtered_pct = round(filtered / total * 100, 2) if total else 0
        print(f"{name}")
        print(f"  total={total}, filtered={filtered} ({filtered_pct}%), retained={retained}")
        print(f"  filter sources: {fc}")
        print()


if __name__ == "__main__":
    main()
