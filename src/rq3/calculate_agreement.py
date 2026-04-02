#!/usr/bin/env python3
"""
calculate_agreement.py

RQ3: Compute per-label Cohen's kappa between two labelers on the shared
'both' set.

Each label file is a JSON export from the labeling tool with the schema:

    {
      "tags": [{"id": "<uuid>", "name": "<tag>", ...}, ...],
      "labels": {
        "<doc_key>": {"tagIds": ["<uuid>", ...], ...},
        ...
      }
    }

Because each document can carry multiple tags (multi-label annotation),
agreement is measured per label using a binary indicator:
  1 = labeler applied this tag to the document
  0 = labeler did not apply this tag

Cohen's kappa is then computed for each label across all documents that
appear in both files.

Usage examples
--------------
Compare CY vs MV on the Python "both" set:

    uv run python src/rq3/calculate_agreement.py \\
        outputs/rq3/results/2026-03-28_CY_Labels_Both_Python.json \\
        outputs/rq3/results/2026-03-31_MV_Labels_Both_Python.json

Compare CY Python vs CY TypeScript (same labeler, different language sets):

    uv run python src/rq3/calculate_agreement.py \\
        outputs/rq3/results/2026-03-28_CY_Labels_Both_Python.json \\
        outputs/rq3/results/2026-03-29_CY_Labels_Both_TS.json

Save results to a custom output file:

    uv run python src/rq3/calculate_agreement.py \\
        outputs/rq3/results/2026-03-28_CY_Labels_Both_Python.json \\
        outputs/rq3/results/2026-03-31_MV_Labels_Both_Python.json \\
        --output outputs/rq3/results/kappa_CY_vs_MV_Python.json

Show only labels that appear in at least one annotation (skip zero-support):

    uv run python src/rq3/calculate_agreement.py \\
        outputs/rq3/results/2026-03-28_CY_Labels_Both_Python.json \\
        outputs/rq3/results/2026-03-31_MV_Labels_Both_Python.json \\
        --min-support 1
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Label normalisation
# ---------------------------------------------------------------------------

_NORMALISE_MAP: dict[str, str] = {
    # case variants
    "instructive": "instructive",
    "Instructive": "instructive",
    # spelling / naming variants observed across files
    "software design": "software-design",
    "software-design": "software-design",
    "code-integration": "code-generation",
    "implementation": "code-generation",
    "program-analysis": "code-generation",
    "wrong-language": "non-english",
    "SE workflow management": "requirements",
}


def normalise_label(name: str) -> str:
    """Return a canonical label name, lower-cased and stripped."""
    stripped = name.strip()
    return _NORMALISE_MAP.get(stripped, stripped.lower())


# ---------------------------------------------------------------------------
# JSON loading helpers
# ---------------------------------------------------------------------------


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------


def build_doc_label_matrix(data: dict) -> dict[str, set[str]]:
    """
    Return a mapping  doc_key -> set of normalised label names
    for every document in *data*.
    """
    tag_map: dict[str, str] = {
        tag["id"]: normalise_label(tag["name"]) for tag in data["tags"]
    }
    matrix: dict[str, set[str]] = {}
    for doc_key, doc_data in data["labels"].items():
        labels = {
            tag_map[tid]
            for tid in doc_data.get("tagIds", [])
            if tid in tag_map
        }
        matrix[doc_key] = labels
    return matrix


# ---------------------------------------------------------------------------
# Cohen's kappa (binary, per-label)
# ---------------------------------------------------------------------------


def cohen_kappa_binary(
    y1: list[int], y2: list[int]
) -> float | None:
    """
    Compute Cohen's kappa for two binary raters without external libraries.

    Returns None when kappa is undefined (both raters always agree on the
    same class, making the expected agreement equal to 1).
    """
    n = len(y1)
    if n == 0:
        return None

    # Observed agreement
    p_o = sum(a == b for a, b in zip(y1, y2)) / n

    # Marginal probabilities
    p1_pos = sum(y1) / n
    p2_pos = sum(y2) / n
    p1_neg = 1.0 - p1_pos
    p2_neg = 1.0 - p2_pos

    # Expected agreement by chance
    p_e = p1_pos * p2_pos + p1_neg * p2_neg

    if p_e == 1.0:
        return None  # undefined: both raters always use the same class

    return (p_o - p_e) / (1.0 - p_e)


def interpret_kappa(kappa: float | None) -> str:
    """Landis & Koch (1977) interpretation bands."""
    if kappa is None:
        return "undefined"
    if kappa < 0:
        return "poor (< 0)"
    if kappa < 0.20:
        return "slight"
    if kappa < 0.40:
        return "fair"
    if kappa < 0.60:
        return "moderate"
    if kappa < 0.80:
        return "substantial"
    return "almost perfect"


# ---------------------------------------------------------------------------
# Main agreement calculation
# ---------------------------------------------------------------------------


def calculate_per_label_kappa(
    matrix1: dict[str, set[str]],
    matrix2: dict[str, set[str]],
    min_support: int = 0,
) -> dict[str, dict]:
    """
    For every label that appears in either matrix, compute Cohen's kappa
    over the set of documents common to both matrices.

    Parameters
    ----------
    matrix1, matrix2:
        doc_key -> set of normalised label names
    min_support:
        Skip labels where the total number of positive annotations across
        both raters is below this threshold.

    Returns
    -------
    Mapping label -> result dict with keys:
        kappa, interpretation, support_r1, support_r2,
        observed_agreement, n_docs
    """
    common_docs = sorted(set(matrix1) & set(matrix2))
    n_docs = len(common_docs)
    log.info("Common documents: %d", n_docs)

    all_labels = sorted(
        {label for labels in matrix1.values() for label in labels}
        | {label for labels in matrix2.values() for label in labels}
    )

    results: dict[str, dict] = {}

    for label in all_labels:
        y1 = [1 if label in matrix1.get(doc, set()) else 0 for doc in common_docs]
        y2 = [1 if label in matrix2.get(doc, set()) else 0 for doc in common_docs]

        support_r1 = sum(y1)
        support_r2 = sum(y2)
        total_support = support_r1 + support_r2

        if total_support < min_support:
            log.debug("Skipping label '%s' (support %d < %d)", label, total_support, min_support)
            continue

        kappa = cohen_kappa_binary(y1, y2)
        observed_agreement = (
            sum(a == b for a, b in zip(y1, y2)) / n_docs if n_docs else None
        )

        results[label] = {
            "kappa": round(kappa, 4) if kappa is not None else None,
            "interpretation": interpret_kappa(kappa),
            "observed_agreement": round(observed_agreement, 4) if observed_agreement is not None else None,
            "support_r1": support_r1,
            "support_r2": support_r2,
            "n_docs": n_docs,
        }

    return results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def print_report(
    file1: Path,
    file2: Path,
    results: dict[str, dict],
    only_common_docs: int,
) -> None:
    print()
    print("=" * 72)
    print("  Per-label Cohen's Kappa")
    print(f"  Rater 1 : {file1.name}")
    print(f"  Rater 2 : {file2.name}")
    print(f"  Common documents: {only_common_docs}")
    print("=" * 72)
    print(
        f"  {'Label':<28}  {'Kappa':>7}  {'Interp.':<18}  "
        f"{'Obs.Agr':>7}  {'Sup1':>4}  {'Sup2':>4}"
    )
    print("-" * 72)

    for label, r in sorted(results.items()):
        kappa_str = f"{r['kappa']:.4f}" if r["kappa"] is not None else "  N/A  "
        obs_str = f"{r['observed_agreement']:.4f}" if r["observed_agreement"] is not None else "  N/A  "
        print(
            f"  {label:<28}  {kappa_str:>7}  {r['interpretation']:<18}  "
            f"{obs_str:>7}  {r['support_r1']:>4}  {r['support_r2']:>4}"
        )

    print("=" * 72)
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compute per-label Cohen's kappa between two labeling JSON files "
            "produced by the RQ3 labeling tool."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "file1",
        metavar="FILE1",
        help="Path to the first labeler's JSON file.",
    )
    parser.add_argument(
        "file2",
        metavar="FILE2",
        help="Path to the second labeler's JSON file.",
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="PATH",
        default=None,
        help=(
            "Optional path to write JSON results. "
            "Defaults to outputs/rq3/results/kappa_<stem1>_vs_<stem2>.json."
        ),
    )
    parser.add_argument(
        "--min-support",
        type=int,
        default=0,
        metavar="N",
        help=(
            "Skip labels where the combined positive annotation count "
            "across both raters is below N (default: 0 = keep all)."
        ),
    )
    parser.add_argument(
        "--no-normalise",
        action="store_true",
        default=False,
        help="Disable label name normalisation (use raw tag names).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO).",
    )
    return parser


def resolve_path(p: str) -> Path:
    path = Path(p)
    return path if path.is_absolute() else (Path.cwd() / path).resolve()


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=args.log_level,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )

    file1 = resolve_path(args.file1)
    file2 = resolve_path(args.file2)

    for p in (file1, file2):
        if not p.is_file():
            log.error("File not found: %s", p)
            sys.exit(1)

    log.info("Loading %s", file1.name)
    data1 = load_json(file1)
    log.info("Loading %s", file2.name)
    data2 = load_json(file2)

    if args.no_normalise:
        # Bypass normalisation: use raw lowercase names only
        def _build_raw(data: dict) -> dict[str, set[str]]:
            tag_map = {tag["id"]: tag["name"].strip() for tag in data["tags"]}
            return {
                doc: {tag_map[tid] for tid in doc_data.get("tagIds", []) if tid in tag_map}
                for doc, doc_data in data["labels"].items()
            }
        matrix1 = _build_raw(data1)
        matrix2 = _build_raw(data2)
    else:
        matrix1 = build_doc_label_matrix(data1)
        matrix2 = build_doc_label_matrix(data2)

    common_docs = set(matrix1) & set(matrix2)
    only_in_1 = set(matrix1) - set(matrix2)
    only_in_2 = set(matrix2) - set(matrix1)

    if only_in_1:
        log.warning("%d document(s) only in file1 (excluded): %s", len(only_in_1), sorted(only_in_1))
    if only_in_2:
        log.warning("%d document(s) only in file2 (excluded): %s", len(only_in_2), sorted(only_in_2))

    results = calculate_per_label_kappa(matrix1, matrix2, min_support=args.min_support)

    print_report(file1, file2, results, len(common_docs))

    # Determine output path
    if args.output:
        out_path = resolve_path(args.output)
    else:
        stem = f"kappa_{file1.stem}_vs_{file2.stem}"
        out_path = file1.parent / f"{stem}.json"

    output_data = {
        "file1": str(file1),
        "file2": str(file2),
        "common_docs": len(common_docs),
        "docs_only_in_file1": sorted(only_in_1),
        "docs_only_in_file2": sorted(only_in_2),
        "min_support": args.min_support,
        "normalisation_applied": not args.no_normalise,
        "per_label_kappa": results,
    }

    write_json(out_path, output_data)
    log.info("Results written to %s", out_path)


if __name__ == "__main__":
    main()
