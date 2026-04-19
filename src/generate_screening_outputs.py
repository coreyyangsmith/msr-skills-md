#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from rq3.label_processing import (  # noqa: E402
    FILTER_SOURCE_LABELS,
    SDLC_STAGE_LABELS,
    build_doc_label_matrix,
    collapse_label,
    iter_label_exports,
    load_json,
)
from screening import (  # noqa: E402
    DECISION_EXCLUDE,
    DECISION_KEEP,
    DECISION_REVIEW,
    DEFAULT_V1_RULES_PATH,
    DEFAULT_V2_RULES_PATH,
    apply_rules_to_features,
    artifact_id_to_repo_and_skill_path,
    build_repo_features,
    decision_counts,
    load_blacklist,
    load_filter_rules,
    load_name_filter_log,
    matched_name_terms,
    write_csv,
)

log = logging.getLogger(__name__)

TAXONOMY_ROWS = [
    (
        "skill marketplace / skill hub",
        "Repository primarily distributes, indexes, or installs agent skills rather than building a software product.",
    ),
    (
        "curated skill collection",
        "Repository is a curated set of standalone skill documents, packs, or shared skill libraries.",
    ),
    (
        "boilerplate / starter / template repo",
        "Repository exists as a starter/template scaffold rather than as the subject software system.",
    ),
    (
        "personal config / dotfiles / setup repo",
        "Repository stores personal environment setup, dotfiles, editor config, or machine bootstrap instructions.",
    ),
    (
        "spec / standard / documentation-only repo",
        "Repository mainly contains specifications, standards, or documentation with little implemented software.",
    ),
    (
        "toy demo / example repo",
        "Repository is an example, test fixture, or demo used to illustrate another tool.",
    ),
    (
        "real software repo with misleading name",
        "Repository has noisy terms in the name but contains a real application, library, service, or tool.",
    ),
    (
        "true positive SE repo",
        "Repository is an in-scope software engineering repository with SKILL.md artifacts used in context.",
    ),
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate RQ3-informed screening audit and full-corpus screening decisions."
    )
    parser.add_argument("--scan-csv", default="outputs/skill_md_scan_results.csv")
    parser.add_argument("--found-csv", default="outputs/skill_md_scan_results_found.csv")
    parser.add_argument("--instances-csv", default="outputs/full_skills_instances.csv")
    parser.add_argument("--raw-data-dir", default="outputs/raw_data")
    parser.add_argument("--rq3-results-dir", default="outputs/rq3/results")
    parser.add_argument("--name-filter-log", default="outputs/name_filtered_repos.tsv")
    parser.add_argument("--blacklist", default="blacklist.txt")
    parser.add_argument("--v1-rules", default=DEFAULT_V1_RULES_PATH)
    parser.add_argument("--v2-rules", default=DEFAULT_V2_RULES_PATH)
    parser.add_argument(
        "--manual-decisions",
        default="",
        help=(
            "Optional adjudication CSV with repo,decision[,primary_reason]. "
            "Rows override v2 decisions before final outputs are written."
        ),
    )
    parser.add_argument("--out-dir", default="outputs/screening")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    return parser.parse_args(argv)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def label_relevance(raw_labels: set[str]) -> tuple[str, str, str]:
    filter_sources = sorted(raw_labels & set(FILTER_SOURCE_LABELS))
    collapsed_sdlc = sorted(
        {
            collapsed
            for label in raw_labels
            if (collapsed := collapse_label(label)) in SDLC_STAGE_LABELS
        }
    )

    if collapsed_sdlc and not filter_sources:
        return (
            "in-scope SE repo",
            "manual SDLC label(s): " + "|".join(collapsed_sdlc),
            "true positive SE repo",
        )
    if "outside-scope" in filter_sources and not collapsed_sdlc:
        return (
            "out-of-scope marketplace or config repo",
            "manual outside-scope label",
            "curated skill collection",
        )
    if "wrong-language" in filter_sources and not collapsed_sdlc:
        return (
            "out-of-scope marketplace or config repo",
            "manual wrong-language label",
            "spec / standard / documentation-only repo",
        )
    if "agent-skill" in filter_sources and not collapsed_sdlc:
        return (
            "out-of-scope marketplace or config repo",
            "manual agent-skill label",
            "skill marketplace / skill hub",
        )
    if filter_sources and collapsed_sdlc:
        return (
            "ambiguous",
            "manual labels contain both filter-source and SDLC evidence",
            "real software repo with misleading name",
        )
    return (
        "ambiguous",
        "manual labels do not clearly map to SDLC or filter-source categories",
        "spec / standard / documentation-only repo",
    )


def load_audit_labels(results_dir: Path) -> dict[str, dict[str, Any]]:
    audit: dict[str, dict[str, Any]] = {}
    for path in iter_label_exports(results_dir):
        data = load_json(path)
        matrix = build_doc_label_matrix(data, normalise=True, apply_special_filter=False)
        for artifact_id, labels in matrix.items():
            record = audit.setdefault(
                artifact_id,
                {
                    "artifact_id": artifact_id,
                    "manual_labels": set(),
                    "source_files": set(),
                },
            )
            record["manual_labels"].update(labels)
            record["source_files"].add(path.name)
    return audit


def build_audit_rows(
    audit_labels: dict[str, dict[str, Any]],
    *,
    v1_decisions: pd.DataFrame,
    name_filter_matches: dict[str, str],
    v1_rules_terms: list[str],
) -> list[dict[str, object]]:
    v1_by_repo = {
        str(row["repo"]): str(row["decision"])
        for _, row in v1_decisions.iterrows()
        if str(row.get("repo", "")).strip()
    }
    rows: list[dict[str, object]] = []
    for artifact_id, record in sorted(audit_labels.items()):
        repo, skill_path = artifact_id_to_repo_and_skill_path(artifact_id)
        labels = set(record["manual_labels"])
        relevance, reason, false_positive_type = label_relevance(labels)
        matched_terms = name_filter_matches.get(repo)
        if not matched_terms:
            matches = matched_name_terms(repo, v1_rules_terms)
            matched_terms = "|".join(matches)
        initial_decision = v1_by_repo.get(repo)
        if not initial_decision:
            initial_decision = DECISION_EXCLUDE if matched_terms else DECISION_KEEP
        rows.append(
            {
                "repo": repo,
                "artifact_id": artifact_id,
                "skill_path": skill_path,
                "filter_outcome_initial": initial_decision,
                "human_relevance": relevance,
                "reason_for_human_label": reason,
                "dominant_false_positive_type": false_positive_type,
                "manual_labels": "|".join(sorted(labels)),
                "raw_filter_source": "|".join(sorted(labels & set(FILTER_SOURCE_LABELS))),
                "sdlc_stage_labels": "|".join(
                    sorted(
                        {
                            collapsed
                            for label in labels
                            if (collapsed := collapse_label(label)) in SDLC_STAGE_LABELS
                        }
                    )
                ),
                "matched_v1_keyword": matched_terms,
                "source_files": "|".join(sorted(record["source_files"])),
            }
        )
    return rows


def compute_audit_summary(audit_rows: list[dict[str, object]]) -> dict[str, object]:
    kept = [row for row in audit_rows if row["filter_outcome_initial"] == DECISION_KEEP]
    excluded = [row for row in audit_rows if row["filter_outcome_initial"] == DECISION_EXCLUDE]
    kept_false_positives = [
        row for row in kept if str(row["human_relevance"]).startswith("out-of-scope")
    ]
    excluded_false_negatives = [
        row for row in excluded if row["human_relevance"] == "in-scope SE repo"
    ]

    def pct(num: int, denom: int) -> float:
        return round((100.0 * num / denom) if denom else 0.0, 2)

    keyword_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in audit_rows:
        keyword_blob = str(row.get("matched_v1_keyword") or "")
        category = str(row["human_relevance"])
        for keyword in [value for value in keyword_blob.split("|") if value]:
            keyword_counts[keyword][category] += 1

    return {
        "audit_documents": len(audit_rows),
        "kept_documents": len(kept),
        "excluded_documents": len(excluded),
        "kept_false_positive_documents": len(kept_false_positives),
        "excluded_false_negative_documents": len(excluded_false_negatives),
        "kept_false_positive_rate_pct": pct(len(kept_false_positives), len(kept)),
        "excluded_false_negative_rate_pct": pct(len(excluded_false_negatives), len(excluded)),
        "precision_among_audited_kept_pct": pct(
            sum(1 for row in kept if row["human_relevance"] == "in-scope SE repo"),
            len(kept),
        ),
        "keyword_counts": {
            keyword: dict(counter)
            for keyword, counter in sorted(keyword_counts.items())
        },
    }


def build_screening_changes_table(
    audit_rows: list[dict[str, object]],
    v1_terms: list[str],
    v2_rules_path: Path,
) -> list[dict[str, object]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in audit_rows:
        for keyword in str(row.get("matched_v1_keyword") or "").split("|"):
            if keyword:
                counts[keyword][str(row["human_relevance"])] += 1

    hard_v2 = set(load_filter_rules(v2_rules_path).hard_exclude_name_terms)
    review_v2 = set(load_filter_rules(v2_rules_path).review_name_terms)

    rows: list[dict[str, object]] = []
    for term in v1_terms:
        valid = counts[term]["in-scope SE repo"]
        out = counts[term]["out-of-scope marketplace or config repo"]
        ambiguous = counts[term]["ambiguous"]
        if term in hard_v2:
            revised = "hard exclude"
        elif term in review_v2:
            revised = "manual review unless strong software signals"
        else:
            revised = "removed"
        observed = f"audit valid={valid}; out_of_scope={out}; ambiguous={ambiguous}"
        rows.append(
            {
                "rule_or_keyword": term,
                "initial_behavior": "hard exclude",
                "observed_issue_from_audited_sample": observed,
                "revised_behavior": revised,
                "rationale": (
                    "Kept as hard exclude only for consistently non-SE collection/config signals; "
                    "noisier terms are now review flags with software-project keep overrides."
                ),
            }
        )
    rows.append(
        {
            "rule_or_keyword": "collection path patterns",
            "initial_behavior": "not evaluated",
            "observed_issue_from_audited_sample": "manual labels identified marketplace/config/demo false positives not captured by repo name alone",
            "revised_behavior": "hard exclude or review based on path term",
            "rationale": "Path structure catches skill hubs and fixture/template repositories whose names look like normal software projects.",
        }
    )
    return rows


def build_manual_review_rows(decisions: pd.DataFrame, instances_csv: Path) -> pd.DataFrame:
    review_repos = set(
        decisions.loc[decisions["decision"].astype(str) == DECISION_REVIEW, "repo"].astype(str)
    )
    rows: list[dict[str, object]] = []
    for _, row in decisions[decisions["repo"].astype(str).isin(review_repos)].iterrows():
        rows.append(
            {
                "level": "repo",
                "repo": row["repo"],
                "artifact_id": "",
                "skill_path": "",
                "decision": row["decision"],
                "primary_reason": row.get("primary_reason", ""),
                "matched_terms": row.get("matched_terms", ""),
                "supporting_signals": row.get("supporting_signals", ""),
            }
        )

    if instances_csv.exists() and review_repos:
        inst_df = pd.read_csv(instances_csv, low_memory=False)
        if {"repo", "skill_path"}.issubset(inst_df.columns):
            for _, row in inst_df[inst_df["repo"].astype(str).isin(review_repos)].iterrows():
                repo = str(row["repo"])
                skill_path = str(row.get("skill_path") or "")
                rows.append(
                    {
                        "level": "artifact",
                        "repo": repo,
                        "artifact_id": f"{repo.replace('/', '__')}/{skill_path.removesuffix('/SKILL.md').removesuffix('SKILL.md').strip('/')}",
                        "skill_path": skill_path,
                        "decision": DECISION_REVIEW,
                        "primary_reason": "repo_requires_manual_review",
                        "matched_terms": "",
                        "supporting_signals": "",
                    }
                )
    return pd.DataFrame(rows)


def apply_manual_decision_overrides(decisions: pd.DataFrame, manual_decisions_path: str) -> pd.DataFrame:
    if not manual_decisions_path:
        return decisions
    path = Path(manual_decisions_path)
    if not path.exists():
        raise FileNotFoundError(f"Manual decisions file not found: {path}")
    overrides = pd.read_csv(path, low_memory=False)
    required = {"repo", "decision"}
    missing = required - set(overrides.columns)
    if missing:
        raise ValueError(f"Manual decisions file is missing required columns: {sorted(missing)}")

    output = decisions.copy()
    output = output.set_index("repo", drop=False)
    for _, override in overrides.iterrows():
        repo = str(override["repo"])
        if repo not in output.index:
            continue
        output.at[repo, "decision"] = str(override["decision"]).strip().lower()
        output.at[repo, "primary_reason"] = str(
            override.get("primary_reason") or "manual_adjudication"
        )
        output.at[repo, "supporting_signals"] = str(
            output.at[repo, "supporting_signals"] or ""
        )
    return output.reset_index(drop=True)


def write_taxonomy(path: Path, audit_rows: list[dict[str, object]]) -> None:
    counts = Counter(str(row["dominant_false_positive_type"]) for row in audit_rows)
    lines = [
        "# False-Positive Taxonomy",
        "",
        "This taxonomy was derived from the RQ3 audit labels and is used to refine the full-corpus screening rule. Counts are document-level within the audited set.",
        "",
        "| Category | Audit count | Definition |",
        "|---|---:|---|",
    ]
    for category, definition in TAXONOMY_ROWS:
        lines.append(f"| {category} | {counts.get(category, 0)} | {definition} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    blacklist = load_blacklist(args.blacklist)
    v1_rules = load_filter_rules(args.v1_rules)
    v2_rules = load_filter_rules(args.v2_rules)

    log.info("Building full-corpus screening features")
    features = build_repo_features(
        scan_csv=args.scan_csv,
        found_csv=args.found_csv,
        instances_csv=args.instances_csv,
        raw_data_dir=args.raw_data_dir,
    )
    v1_decisions = apply_rules_to_features(features, v1_rules, blacklist)
    v2_decisions = apply_rules_to_features(features, v2_rules, blacklist)
    v2_decisions = apply_manual_decision_overrides(v2_decisions, args.manual_decisions)

    write_csv(out_dir / "full_corpus_screening_decisions.csv", v2_decisions)
    write_csv(
        out_dir / "screening_summary_v1_v2.csv",
        pd.DataFrame([decision_counts(v1_decisions, "v1"), decision_counts(v2_decisions, "v2")]),
    )

    log.info("Building RQ3 audit sample")
    audit_labels = load_audit_labels(Path(args.rq3_results_dir))
    name_filter_matches = load_name_filter_log(args.name_filter_log)
    audit_rows = build_audit_rows(
        audit_labels,
        v1_decisions=v1_decisions,
        name_filter_matches=name_filter_matches,
        v1_rules_terms=list(v1_rules.hard_exclude_name_terms),
    )
    audit_summary = compute_audit_summary(audit_rows)
    write_csv(out_dir / "filter_audit_sample.csv", audit_rows)
    pd.DataFrame([audit_summary]).drop(columns=["keyword_counts"]).to_csv(
        out_dir / "filter_audit_summary.csv",
        index=False,
    )
    keyword_rows = [
        {"keyword": keyword, **counts}
        for keyword, counts in audit_summary["keyword_counts"].items()
    ]
    write_csv(
        out_dir / "filter_audit_keyword_counts.csv",
        keyword_rows,
        fieldnames=[
            "keyword",
            "in-scope SE repo",
            "out-of-scope marketplace or config repo",
            "ambiguous",
        ],
    )

    changes = build_screening_changes_table(audit_rows, list(v1_rules.hard_exclude_name_terms), Path(args.v2_rules))
    write_csv(out_dir / "screening_changes_table.csv", changes)
    write_taxonomy(out_dir / "false_positive_taxonomy.md", audit_rows)

    manual_review = build_manual_review_rows(v2_decisions, Path(args.instances_csv))
    write_csv(out_dir / "manual_review_borderline.csv", manual_review)

    print(f"Wrote screening outputs to {out_dir.resolve()}")
    print(
        f"v2 decisions: keep={int((v2_decisions['decision'] == DECISION_KEEP).sum())}, "
        f"exclude={int((v2_decisions['decision'] == DECISION_EXCLUDE).sum())}, "
        f"review={int((v2_decisions['decision'] == DECISION_REVIEW).sum())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
