from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import mannwhitneyu

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rq1.common import (
    add_instances_input_args,
    add_language_args,
    add_output_args,
    add_scan_input_args,
    aggregate_instances_to_repo,
    compute_project_age_years,
    configure_logging,
    filter_dataframe_by_languages,
    load_instances_csv,
    load_scan_csv,
    resolve_filters,
    safe_stars,
    write_dataframe,
)

log = logging.getLogger(__name__)

GROUP_SKILL = "SKILL.md"
GROUP_NONSKILL = "No SKILL.md"

METRIC_STARS = "Stars"
METRIC_CONTRIBUTORS = "Contributors"
METRIC_SIZE = "Repository size (MB)"
METRIC_AGE = "Project age (years)"
METRIC_SKILLS = "SKILL.md files"

TIDY_CSV = "table_repo_descriptives_by_skill_presence.csv"
SKILL_CSV = "table_repo_descriptives_skill.csv"
NONSKILL_CSV = "table_repo_descriptives_nonskill.csv"
TESTS_CSV = "table_repo_skill_presence_tests.csv"
LATEX_NAME = "table_repo_descriptives_by_skill_presence.tex"

_INTEGER_EXTREMA = {METRIC_STARS, METRIC_CONTRIBUTORS, METRIC_SKILLS}


def _found_mask(scan_df: pd.DataFrame) -> pd.Series:
    return scan_df["found"].fillna(False).astype(bool)


def _summarize(series: pd.Series, integer_extrema: bool) -> dict[str, object]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {"n": 0, "min": None, "mean": None, "median": None, "max": None}
    min_v = float(values.min())
    max_v = float(values.max())
    return {
        "n": int(len(values)),
        "min": int(min_v) if integer_extrema else round(min_v, 2),
        "mean": round(float(values.mean()), 2),
        "median": round(float(values.median()), 2),
        "max": int(max_v) if integer_extrema else round(max_v, 2),
    }


def _skill_counts(scan_df: pd.DataFrame, repo_instances_df: pd.DataFrame | None) -> pd.Series:
    counts = pd.Series(pd.NA, index=scan_df.index, dtype="Float64")
    found = _found_mask(scan_df)
    counts.loc[~found] = 0
    if repo_instances_df is None or repo_instances_df.empty or "repo" not in repo_instances_df.columns:
        return pd.to_numeric(counts, errors="coerce")
    if "skill_count" not in repo_instances_df.columns:
        return pd.to_numeric(counts, errors="coerce")
    mapped = scan_df["repo"].map(repo_instances_df.drop_duplicates("repo").set_index("repo")["skill_count"])
    has_instance = found & mapped.notna()
    counts.loc[has_instance] = pd.to_numeric(mapped.loc[has_instance], errors="coerce")
    return pd.to_numeric(counts, errors="coerce")


_METRIC_COLUMNS = [
    (METRIC_STARS, "_stars"),
    (METRIC_CONTRIBUTORS, "_contributors"),
    (METRIC_SIZE, "_size_mb"),
    (METRIC_AGE, "_age_years"),
    (METRIC_SKILLS, "_skill_count"),
]


def _metric_frame(
    scan_df: pd.DataFrame,
    repo_instances_df: pd.DataFrame | None = None,
    fallback_now: pd.Timestamp | None = None,
) -> pd.DataFrame:
    if (
        repo_instances_df is not None
        and not repo_instances_df.empty
        and "skill_count" not in repo_instances_df.columns
    ):
        repo_instances_df = aggregate_instances_to_repo(repo_instances_df)

    work = scan_df.copy()
    work["_stars"] = pd.to_numeric(safe_stars(work), errors="coerce")
    work["_contributors"] = pd.to_numeric(work.get("contributors"), errors="coerce")
    work["_size_mb"] = pd.to_numeric(work.get("size"), errors="coerce") / 1024.0
    work["_age_years"] = compute_project_age_years(work, fallback_now=fallback_now)
    work["_skill_count"] = _skill_counts(work, repo_instances_df)
    return work


def cliffs_delta_mwu(skill: pd.Series, nonskill: pd.Series) -> dict[str, object]:
    """Two-sided Mann-Whitney U; Cliff's delta > 0 means SKILL.md values tend to be larger."""
    a = pd.to_numeric(skill, errors="coerce").dropna()
    b = pd.to_numeric(nonskill, errors="coerce").dropna()
    u, p = mannwhitneyu(a, b, alternative="two-sided")
    return {
        "n_skill": int(len(a)),
        "n_nonskill": int(len(b)),
        "U": float(u),
        "p": float(p),
        "cliffs_delta": round(2.0 * float(u) / (len(a) * len(b)) - 1.0, 4),
    }


def build_group_tests(scan_df: pd.DataFrame, fallback_now: pd.Timestamp | None = None) -> pd.DataFrame:
    """One independent Mann-Whitney U test per metric (SKILL.md count excluded: 0 by definition)."""
    work = _metric_frame(scan_df, fallback_now=fallback_now)
    found = _found_mask(work)
    rows = [
        {"metric": metric, **cliffs_delta_mwu(work.loc[found, column], work.loc[~found, column])}
        for metric, column in _METRIC_COLUMNS
        if metric != METRIC_SKILLS
    ]
    return pd.DataFrame(rows)


def build_descriptive_tables(
    scan_df: pd.DataFrame,
    repo_instances_df: pd.DataFrame | None = None,
    fallback_now: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    work = _metric_frame(scan_df, repo_instances_df, fallback_now)
    found = _found_mask(work)
    groups = [(GROUP_SKILL, found), (GROUP_NONSKILL, ~found)]

    rows: list[dict[str, object]] = []
    for group_name, mask in groups:
        subset = work.loc[mask]
        for metric_name, column in _METRIC_COLUMNS:
            stats = _summarize(subset[column], integer_extrema=metric_name in _INTEGER_EXTREMA)
            rows.append({"group": group_name, "metric": metric_name, **stats})

    tidy = pd.DataFrame(rows)
    skill_wide = tidy.loc[tidy["group"] == GROUP_SKILL].drop(columns=["group"]).reset_index(drop=True)
    nonskill_wide = tidy.loc[tidy["group"] == GROUP_NONSKILL].drop(columns=["group"]).reset_index(drop=True)
    return tidy, skill_wide, nonskill_wide


def _fmt_cell(value: object, integer_extrema: bool, extrema: bool) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return "---"
    if extrema and integer_extrema:
        return str(int(value))
    return f"{float(value):.2f}"


def _fmt_p(p: float) -> str:
    return r"$<$0.001" if p < 0.001 else f"{p:.3f}"


def format_latex_table(
    tidy: pd.DataFrame,
    n_skill: int,
    n_nonskill: int,
    tests: pd.DataFrame | None = None,
) -> str:
    lookup = {(row.group, row.metric): row for row in tidy.itertuples(index=False)}
    test_lookup = {} if tests is None else {row.metric: row for row in tests.itertuples(index=False)}
    metric_order = [METRIC_STARS, METRIC_CONTRIBUTORS, METRIC_SIZE, METRIC_AGE, METRIC_SKILLS]
    body_lines = []
    for metric in metric_order:
        skill = lookup[(GROUP_SKILL, metric)]
        nonskill = lookup[(GROUP_NONSKILL, metric)]
        integer = metric in _INTEGER_EXTREMA
        test = test_lookup.get(metric)
        test_cells = [f"{test.cliffs_delta:+.2f}", _fmt_p(test.p)] if test else ["---", "---"]
        cells = [
            metric,
            _fmt_cell(skill.min, integer, True),
            _fmt_cell(skill.mean, integer, False),
            _fmt_cell(skill.median, integer, False),
            _fmt_cell(skill.max, integer, True),
            _fmt_cell(nonskill.min, integer, True),
            _fmt_cell(nonskill.mean, integer, False),
            _fmt_cell(nonskill.median, integer, False),
            _fmt_cell(nonskill.max, integer, True),
            *test_cells,
        ]
        body_lines.append(" & ".join(cells) + r" \\")

    omitted = n_skill - int(lookup[(GROUP_SKILL, METRIC_SKILLS)].n)
    omit_note = (
        f" SKILL.md file counts omit {omitted} found repositories with no instance row."
        if omitted
        else ""
    )
    caption = (
        r"Repository descriptives for RQ1 candidate repositories, split by SKILL.md presence. "
        r"Project age uses \texttt{createdAt} versus \texttt{scanned\_at\_utc}; "
        r"not-found rows lack \texttt{scanned\_at\_utc} and use the latest scan time as the reference. "
        r"$\delta$ is Cliff's delta from a two-sided Mann--Whitney U test, one test per metric reported "
        r"independently; $\delta > 0$ means SKILL.md repositories tend to have higher values."
        rf"{omit_note}"
    )
    return "\n".join(
        [
            r"\begin{table}[t]",
            r"\centering",
            rf"\caption{{{caption}}}",
            r"\label{tab:repo-descriptives-skill-presence}",
            r"\begin{tabular}{l rrrr rrrr rr}",
            r"\toprule",
            rf" & \multicolumn{{4}}{{c}}{{SKILL.md repos ($n={n_skill:,}$)}} & "
            rf"\multicolumn{{4}}{{c}}{{No SKILL.md ($n={n_nonskill:,}$)}} & & \\",
            r"Metric & Min & Mean & Median & Max & Min & Mean & Median & Max & $\delta$ & $p$ \\",
            r"\midrule",
            *body_lines,
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{table}",
            "",
        ]
    )


def generate(
    scan_df: pd.DataFrame,
    out_dir: str,
    repo_instances_df: pd.DataFrame | None = None,
    fallback_now: pd.Timestamp | None = None,
) -> Path:
    tidy, skill_wide, nonskill_wide = build_descriptive_tables(
        scan_df, repo_instances_df, fallback_now=fallback_now
    )
    n_skill = int(_found_mask(scan_df).sum())
    n_nonskill = int((~_found_mask(scan_df)).sum())

    out_path = Path(out_dir)
    tidy_path = out_path / TIDY_CSV
    write_dataframe(tidy, str(tidy_path))
    write_dataframe(skill_wide, str(out_path / SKILL_CSV))
    write_dataframe(nonskill_wide, str(out_path / NONSKILL_CSV))
    tests = build_group_tests(scan_df, fallback_now=fallback_now)
    write_dataframe(tests, str(out_path / TESTS_CSV))

    latex_path = out_path / LATEX_NAME
    latex_path.parent.mkdir(parents=True, exist_ok=True)
    latex_path.write_text(format_latex_table(tidy, n_skill, n_nonskill, tests), encoding="utf-8")
    log.info("Saved table: %s", latex_path)
    return tidy_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate SKILL.md vs non-SKILL.md repository descriptives for RQ1"
    )
    add_scan_input_args(parser)
    add_instances_input_args(parser)
    add_language_args(parser)
    add_output_args(parser)
    args = parser.parse_args(argv)

    configure_logging(args.log_level)
    blacklist, filter_words = resolve_filters(args)
    scan_df = load_scan_csv(args.scan_csv, blacklist=blacklist, filter_words=filter_words)
    scan_df = filter_dataframe_by_languages(scan_df, args.languages)

    inst_df = load_instances_csv(args.instances_csv)
    if inst_df is None:
        log.error("Instances CSV missing or unreadable: %s", args.instances_csv)
        return 2
    inst_df = filter_dataframe_by_languages(inst_df, args.languages)
    repo_instances_df = aggregate_instances_to_repo(inst_df)

    generate(scan_df, args.out_dir, repo_instances_df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
