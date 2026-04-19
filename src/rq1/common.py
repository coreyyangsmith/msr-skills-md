from __future__ import annotations

import argparse
import logging
import math
import os
import warnings
from pathlib import Path
from typing import Iterable, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from filters import REPO_NAME_FILTER_WORDS, load_blacklist, load_relevance_terms, repo_name_contains_filter_word
from screening import filter_dataframe_by_screening, load_screening_decisions

warnings.filterwarnings("ignore", category=FutureWarning)

log = logging.getLogger(__name__)

PALETTE_FOUND = "#2196F3"
PALETTE_NOT_FOUND = "#E0E0E0"
PALETTE_ACF = ["#FF5722", "#4CAF50", "#9C27B0"]


def setup_style() -> None:
    try:
        plt.style.use("seaborn-v0_8-whitegrid")
    except OSError:
        plt.style.use("seaborn-whitegrid")
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "legend.fontsize": 10,
            "figure.constrained_layout.use": True,
        }
    )


def savefig(fig: plt.Figure, path: str, dpi: int = 300) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    log.info("Saved figure: %s", output_path)


def write_dataframe(df: pd.DataFrame, path: str) -> str:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    log.info("Saved table: %s", output_path)
    return str(output_path)


def write_missing_data_note(
    out_dir: str,
    artifact: str,
    reason: str,
    missing_columns: Optional[Sequence[str]] = None,
    source_hint: str = "",
) -> str:
    note_path = Path(out_dir) / f"note_{artifact}_missing_data.md"
    note_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Missing data for `{artifact}`",
        "",
        reason.strip(),
    ]
    if missing_columns:
        lines.extend(
            [
                "",
                "Missing or empty columns:",
                "",
                *[f"- `{col}`" for col in missing_columns],
            ]
        )
    if source_hint:
        lines.extend(["", source_hint.strip()])
    note_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.warning("Wrote missing-data note: %s", note_path)
    return str(note_path)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def build_filter_words(
    relevance_terms_path: str,
    extra_words: str = "",
    no_name_filter: bool = False,
) -> list[str]:
    if no_name_filter:
        return []

    filter_words = load_relevance_terms(relevance_terms_path) or list(REPO_NAME_FILTER_WORDS)
    if extra_words.strip():
        filter_words.extend([w.strip() for w in extra_words.split(",") if w.strip()])
    return filter_words


def _apply_repo_filters(
    df: pd.DataFrame,
    blacklist: set[str],
    filter_words: Sequence[str],
    label: str,
) -> pd.DataFrame:
    if "repo" not in df.columns:
        return df

    before = len(df)
    mask_blacklist = df["repo"].isin(blacklist)
    mask_name = df["repo"].apply(
        lambda repo: repo_name_contains_filter_word(str(repo), list(filter_words)) is not None
    )
    excluded = mask_blacklist | mask_name
    n_bl = int(mask_blacklist.sum())
    n_nf = int((~mask_blacklist & mask_name).sum())
    if n_bl or n_nf:
        log.info(
            "%s: excluding %d blacklisted + %d name-filtered repos (%d -> %d rows)",
            label,
            n_bl,
            n_nf,
            before,
            before - int(excluded.sum()),
        )
    return df[~excluded].reset_index(drop=True)


def _coerce_numeric_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")


def _coerce_datetime_columns(df: pd.DataFrame, columns: Iterable[str]) -> None:
    for column in columns:
        if column in df.columns:
            df[column] = pd.to_datetime(df[column], errors="coerce", utc=True)


def load_scan_csv(
    path: str,
    blacklist: Optional[set[str]] = None,
    filter_words: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    log.info("Loaded scan CSV: %s rows, %s cols from %s", len(df), len(df.columns), path)

    df = _apply_repo_filters(
        df,
        blacklist or set(),
        filter_words if filter_words is not None else REPO_NAME_FILTER_WORDS,
        "scan CSV",
    )

    if "found" in df.columns:
        df["found"] = (
            df["found"]
            .astype(str)
            .str.strip()
            .str.lower()
            .map({"true": True, "false": False, "1": True, "0": False})
            .fillna(False)
            .astype(bool)
        )

    _coerce_numeric_columns(
        df,
        [
            "stars",
            "stargazers",
            "codeLines",
            "size",
            "commits",
            "contributors",
            "forks",
            "releases",
            "totalIssues",
            "openIssues",
            "has_README",
            "has_CONTRIBUTING",
            "has_SECURITY",
            "has_CODE_OF_CONDUCT",
        ],
    )
    _coerce_datetime_columns(df, ["createdAt", "pushedAt", "updatedAt", "lastCommit", "scanned_at_utc"])
    return df


def load_instances_csv(path: str) -> Optional[pd.DataFrame]:
    if not path or not os.path.exists(path):
        log.warning("Instances CSV not found or not provided: %s", path)
        return None

    df = pd.read_csv(path, low_memory=False)
    log.info("Loaded instances CSV: %s rows, %s cols from %s", len(df), len(df.columns), path)
    log.info(
        "Using all instance rows as in the file (scan CSV may still apply blacklist/name filters)."
    )

    _coerce_numeric_columns(
        df,
        [
            "skill_count",
            "total_files_in_skills",
            "references_file_count",
            "assets_file_count",
            "scripts_file_count",
            "other_file_count",
            "stars",
            "stargazers",
            "forks",
            "commits",
            "contributors",
            "size",
            "codeLines",
            "has_README",
            "has_CONTRIBUTING",
            "has_SECURITY",
            "has_CODE_OF_CONDUCT",
        ],
    )
    _coerce_datetime_columns(df, ["createdAt", "pushedAt", "updatedAt", "lastCommit", "scanned_at_utc"])
    if "mainLanguage" in df.columns:
        df["mainLanguage"] = df["mainLanguage"].fillna("Unknown").astype(str).replace("", "Unknown")
    return df


def safe_stars(df: pd.DataFrame) -> pd.Series:
    if "stargazers" in df.columns and df["stargazers"].notna().any():
        return df["stargazers"]
    return df.get("stars", pd.Series(dtype=float))


def wilson_ci(k: float, n: float, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (0.0, 0.0)
    n = float(n)
    k = float(min(max(k, 0.0), n))
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    inner = p * (1 - p) / n + z**2 / (4 * n**2)
    half = z * math.sqrt(max(0.0, inner)) / denom
    lo = 100 * (center - half)
    hi = 100 * (center + half)
    return (max(0.0, min(100.0, lo)), max(0.0, min(100.0, hi)))


def latest_non_null(series: pd.Series) -> object:
    non_null = series.dropna()
    if non_null.empty:
        return np.nan
    return non_null.iloc[-1]


def aggregate_instances_to_repo(inst_df: pd.DataFrame) -> pd.DataFrame:
    if inst_df.empty or "repo" not in inst_df.columns:
        return inst_df.copy()

    work = inst_df.copy()
    group = work.groupby("repo", dropna=False)

    rows: list[dict[str, object]] = []
    sum_columns = [
        "total_files_in_skills",
        "references_file_count",
        "assets_file_count",
        "scripts_file_count",
        "other_file_count",
    ]
    numeric_meta_columns = [
        "stars",
        "stargazers",
        "forks",
            "commits",
            "contributors",
            "size",
            "codeLines",
            "releases",
            "totalIssues",
            "openIssues",
            "has_README",
            "has_CONTRIBUTING",
            "has_SECURITY",
            "has_CODE_OF_CONDUCT",
        ]
    categorical_columns = [
        "mainLanguage",
        "default_branch",
        "defaultBranch",
        "license",
        "createdAt",
        "pushedAt",
        "updatedAt",
        "lastCommit",
        "scanned_at_utc",
        "skill_paths",
        "html_url",
    ]

    for repo, repo_df in group:
        row: dict[str, object] = {"repo": repo}
        if "skill_count" in repo_df.columns and repo_df["skill_count"].notna().any():
            row["skill_count"] = pd.to_numeric(repo_df["skill_count"], errors="coerce").max()
        else:
            row["skill_count"] = int(len(repo_df))

        for column in sum_columns:
            if column in repo_df.columns:
                row[column] = pd.to_numeric(repo_df[column], errors="coerce").fillna(0).sum()

        for column in numeric_meta_columns:
            if column in repo_df.columns:
                series = pd.to_numeric(repo_df[column], errors="coerce")
                row[column] = series.max() if series.notna().any() else np.nan

        for column in categorical_columns:
            if column in repo_df.columns:
                row[column] = latest_non_null(repo_df[column])

        rows.append(row)

    repo_df = pd.DataFrame(rows)
    if "mainLanguage" in repo_df.columns:
        repo_df["mainLanguage"] = repo_df["mainLanguage"].fillna("Unknown").astype(str).replace("", "Unknown")
    return repo_df


def merge_repo_metadata(
    repo_df: pd.DataFrame,
    scan_df: Optional[pd.DataFrame],
    preferred_columns: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    if scan_df is None or scan_df.empty or "repo" not in repo_df.columns or "repo" not in scan_df.columns:
        return repo_df

    columns = list(
        preferred_columns
        or [
            "found",
            "contributors",
            "size",
            "codeLines",
            "createdAt",
            "pushedAt",
            "updatedAt",
            "scanned_at_utc",
            "stars",
            "stargazers",
            "forks",
            "commits",
            "releases",
            "totalIssues",
            "has_README",
            "has_CONTRIBUTING",
            "has_SECURITY",
            "has_CODE_OF_CONDUCT",
            "mainLanguage",
            "license",
        ]
    )
    available = ["repo"] + [column for column in columns if column in scan_df.columns]
    metadata = scan_df[available].drop_duplicates(subset=["repo"], keep="last")
    merged = repo_df.merge(metadata, on="repo", how="left", suffixes=("", "_scan"))

    for column in columns:
        scan_column = f"{column}_scan"
        if scan_column not in merged.columns:
            continue
        if column not in merged.columns:
            merged[column] = merged[scan_column]
        else:
            merged[column] = merged[column].where(merged[column].notna(), merged[scan_column])
        merged = merged.drop(columns=[scan_column])

    return merged


def prevalence_by_bucket(
    df: pd.DataFrame,
    value_series: pd.Series,
    bucket_name: str,
    labels: Sequence[str],
    buckets: pd.Series,
) -> pd.DataFrame:
    work = pd.DataFrame({"found": df["found"].astype(bool).values, bucket_name: buckets})
    work = work[work[bucket_name].notna()].copy()
    if work.empty:
        return pd.DataFrame(columns=[bucket_name, "total", "found", "prevalence_pct"])

    grouped = (
        work.groupby(bucket_name, observed=True)["found"]
        .agg(total="count", found="sum")
        .reset_index()
    )
    grouped[bucket_name] = grouped[bucket_name].astype(str)
    grouped = grouped.set_index(bucket_name).reindex(labels, fill_value=0).reset_index()
    grouped["prevalence_pct"] = np.where(
        grouped["total"] > 0,
        100.0 * grouped["found"] / grouped["total"],
        0.0,
    )
    return grouped


def compute_project_age_years(df: pd.DataFrame, fallback_now: Optional[pd.Timestamp] = None) -> pd.Series:
    created = pd.to_datetime(df.get("createdAt"), errors="coerce", utc=True)
    if "scanned_at_utc" in df.columns:
        reference = pd.to_datetime(df["scanned_at_utc"], errors="coerce", utc=True)
    else:
        reference = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")

    now = fallback_now or pd.Timestamp.now(tz="UTC")
    reference = reference.fillna(now)
    ages = (reference - created).dt.total_seconds() / (365.25 * 24 * 60 * 60)
    return ages.where(ages >= 0)


def add_scan_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--scan-csv", required=True, help="Main scan results CSV")
    parser.add_argument(
        "--blacklist",
        default="blacklist.txt",
        help="Path to blacklist file (owner/repo per line). Default: blacklist.txt",
    )
    parser.add_argument(
        "--relevance-terms",
        default="relevance_terms.txt",
        help="Path to relevance terms file (one term per line). Default: relevance_terms.txt",
    )
    parser.add_argument(
        "--name-filter-words",
        default="",
        help="Comma-separated extra repo-name filter words.",
    )
    parser.add_argument(
        "--no-name-filter",
        action="store_true",
        help="Disable the built-in repo-name filter (blacklist still applies).",
    )


def add_instances_input_args(parser: argparse.ArgumentParser, required: bool = True) -> None:
    parser.add_argument(
        "--instances-csv",
        required=required,
        default="" if required else "",
        help="Path to full_skills_instances.csv",
    )


def add_screening_input_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--screening-decisions",
        default="",
        help=(
            "Optional CSV with repo-level screening decisions. Rows with decision=keep are retained. "
            "Use --screening-mode final to fail when unresolved review rows remain."
        ),
    )
    parser.add_argument(
        "--screening-mode",
        default="provisional",
        choices=["provisional", "final"],
        help=(
            "Screening decision strictness. provisional excludes review rows from analyses; "
            "final fails if any review rows remain unresolved."
        ),
    )


def add_output_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--out-dir", default="outputs/rq1", help="Output directory for figures and tables")
    parser.add_argument(
        "--format",
        dest="fig_format",
        default="png",
        choices=["png", "pdf", "svg"],
        help="Figure output format (default: png)",
    )
    parser.add_argument("--dpi", type=int, default=300, help="Figure resolution in DPI (default: 300)")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity",
    )


def resolve_filters(args: argparse.Namespace) -> tuple[set[str], list[str]]:
    blacklist = load_blacklist(args.blacklist)
    filter_words = build_filter_words(args.relevance_terms, args.name_filter_words, args.no_name_filter)
    log.info(
        "Filters: blacklist=%d entries, name_filter=%d words%s",
        len(blacklist),
        len(filter_words),
        " (disabled)" if args.no_name_filter else "",
    )
    return blacklist, filter_words


def resolve_screening_decisions(args: argparse.Namespace) -> Optional[pd.DataFrame]:
    decisions_path = getattr(args, "screening_decisions", "")
    if not decisions_path:
        return None
    final = getattr(args, "screening_mode", "provisional") == "final"
    decisions = load_screening_decisions(decisions_path, final=final)
    log.info(
        "Screening decisions loaded: %d rows from %s (%s mode)",
        len(decisions),
        decisions_path,
        "final" if final else "provisional",
    )
    return decisions


def apply_screening_decisions(
    df: pd.DataFrame,
    decisions: Optional[pd.DataFrame],
    label: str,
) -> pd.DataFrame:
    if decisions is None or df is None or df.empty or "repo" not in df.columns:
        return df
    before = len(df)
    filtered = filter_dataframe_by_screening(df, decisions, repo_column="repo", keep_missing=True)
    log.info(
        "%s: applied screening decisions (%d -> %d rows)",
        label,
        before,
        len(filtered),
    )
    return filtered
