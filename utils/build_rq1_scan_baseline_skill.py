#!/usr/bin/env python3
"""
Build a single --scan-csv for RQ1: relevance-filter population (denominator) with
`found` = repo appears in the skill-only scan (numerator), plus scan/ACF columns
merged from the skill file for matching repos.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    p.add_argument(
        "--population-csv",
        default=str(REPO_ROOT / "data/seart_csvs/github_search_results.csv"),
        help="SEART-style CSV (uses `name` as owner/repo)",
    )
    p.add_argument(
        "--skill-csv",
        default=str(REPO_ROOT / "data/skill_only_scan/skill_repositories.csv"),
        help="Skill-only scan CSV (`repo` column)",
    )
    p.add_argument(
        "--out-csv",
        default=str(REPO_ROOT / "outputs/rq1/rq1_scan_baseline.csv"),
        help="Merged output for rq1 --scan-csv",
    )
    p.add_argument(
        "--languages",
        nargs="+",
        default=["Python", "TypeScript"],
        metavar="LANG",
        help="Primary languages to include (default: Python TypeScript).",
    )
    args = p.parse_args(argv)

    pop = pd.read_csv(args.population_csv, low_memory=False)
    skill = pd.read_csv(args.skill_csv, low_memory=False)

    allowed = {language.strip().lower() for language in args.languages if language.strip()}
    if allowed and "mainLanguage" in pop.columns:
        pop = pop[pop["mainLanguage"].fillna("").astype(str).str.strip().str.lower().isin(allowed)].copy()
    if allowed and "mainLanguage" in skill.columns:
        skill = skill[skill["mainLanguage"].fillna("").astype(str).str.strip().str.lower().isin(allowed)].copy()

    if "repo" not in pop.columns:
        if "name" not in pop.columns:
            print("Population CSV must have `name` or `repo`.", file=sys.stderr)
            return 1
        pop = pop.copy()
        pop["repo"] = pop["name"].astype(str).str.strip()

    skill = skill.copy()
    skill["repo"] = skill["repo"].astype(str).str.strip()
    skill_repos = set(skill["repo"])

    extra_cols = [
        c
        for c in skill.columns
        if c != "repo" and c not in pop.columns and c != "found"
    ]
    skill_dedup = skill.drop_duplicates(subset=["repo"], keep="last")
    merge_frame = skill_dedup[["repo"] + extra_cols]
    merged = pop.merge(merge_frame, on="repo", how="left")
    merged["found"] = merged["repo"].isin(skill_repos)
    merged["error_type"] = "none"
    merged["error_message"] = ""
    merged["acf_error_type"] = ""
    merged["acf_error_message"] = ""

    out = Path(args.out_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out, index=False)

    n_pop = len(merged)
    n_found = int(merged["found"].sum())
    in_both = len(skill_repos & set(merged["repo"]))
    print(f"Wrote {out} ({n_pop} rows, found={n_found}, skill repos in population={in_both})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
