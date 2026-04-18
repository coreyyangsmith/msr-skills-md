from __future__ import annotations

import csv
import dataclasses
import json
import logging
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd
import yaml

log = logging.getLogger(__name__)

DECISION_KEEP = "keep"
DECISION_EXCLUDE = "exclude"
DECISION_REVIEW = "review"
DECISIONS = {DECISION_KEEP, DECISION_EXCLUDE, DECISION_REVIEW}

DEFAULT_V1_RULES_PATH = "config/filter_rules_v1.yaml"
DEFAULT_V2_RULES_PATH = "config/filter_rules_v2.yaml"

MANIFEST_FILENAMES = {
    "package.json": "has_package_json",
    "pyproject.toml": "has_pyproject_toml",
    "go.mod": "has_go_mod",
    "cargo.toml": "has_cargo_toml",
    "pom.xml": "has_pom_xml",
}

CI_PATH_MARKERS = (
    ".github/workflows/",
    ".gitlab-ci.yml",
    "azure-pipelines.yml",
    "circle.yml",
    ".circleci/",
)

CODE_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".go", ".rs", ".c", ".cc",
    ".cpp", ".cs", ".php", ".rb", ".swift", ".kt", ".scala", ".sh",
}
MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdx"}


@dataclasses.dataclass(frozen=True)
class ScreeningRules:
    version: str
    name_filter_mode: str
    hard_exclude_name_terms: tuple[str, ...]
    review_name_terms: tuple[str, ...]
    hard_exclude_path_terms: tuple[str, ...]
    review_path_terms: tuple[str, ...]
    keep_override_signals: tuple[str, ...]
    minimum_code_lines_for_keep_override: int = 0
    maximum_skill_to_source_ratio_for_keep_override: float | None = None


@dataclasses.dataclass(frozen=True)
class ScreeningDecision:
    repo: str
    decision: str
    primary_reason: str
    matched_terms: tuple[str, ...]
    supporting_signals: tuple[str, ...]
    rule_version: str

    def as_row(self) -> dict[str, str]:
        return {
            "repo": self.repo,
            "decision": self.decision,
            "primary_reason": self.primary_reason,
            "matched_terms": "|".join(self.matched_terms),
            "supporting_signals": "|".join(self.supporting_signals),
            "rule_version": self.rule_version,
        }


def _as_tuple(value: object) -> tuple[str, ...]:
    if not value:
        return ()
    if isinstance(value, str):
        return (value.lower(),)
    if isinstance(value, Iterable):
        return tuple(str(item).strip().lower() for item in value if str(item).strip())
    return ()


def load_filter_rules(path: str | Path) -> ScreeningRules:
    rules_path = Path(path)
    with rules_path.open(encoding="utf-8") as handle:
        payload = yaml.safe_load(handle) or {}

    return ScreeningRules(
        version=str(payload.get("version") or rules_path.stem),
        name_filter_mode=str(payload.get("name_filter_mode") or "triage"),
        hard_exclude_name_terms=_as_tuple(payload.get("hard_exclude_name_terms")),
        review_name_terms=_as_tuple(payload.get("review_name_terms")),
        hard_exclude_path_terms=_as_tuple(payload.get("hard_exclude_path_terms")),
        review_path_terms=_as_tuple(payload.get("review_path_terms")),
        keep_override_signals=_as_tuple(payload.get("keep_override_signals")),
        minimum_code_lines_for_keep_override=int(payload.get("minimum_code_lines_for_keep_override") or 0),
        maximum_skill_to_source_ratio_for_keep_override=(
            float(payload["maximum_skill_to_source_ratio_for_keep_override"])
            if payload.get("maximum_skill_to_source_ratio_for_keep_override") is not None
            else None
        ),
    )


def repo_name(repo: str) -> str:
    return str(repo).split("/", 1)[-1].lower()


def matched_name_terms(repo: str, terms: Sequence[str]) -> tuple[str, ...]:
    name = repo_name(repo)
    return tuple(term for term in terms if term and term in name)


def matched_path_terms(paths: Iterable[str], terms: Sequence[str]) -> tuple[str, ...]:
    lower_paths = [str(path).replace("\\", "/").lower() for path in paths if str(path).strip()]
    matches: list[str] = []
    for term in terms:
        term_l = term.lower()
        if any(term_l in path for path in lower_paths):
            matches.append(term)
    return tuple(matches)


def _bool_feature(features: Mapping[str, object], key: str) -> bool:
    value = features.get(key)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _float_feature(features: Mapping[str, object], key: str) -> float:
    try:
        return float(features.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def strong_software_signals(features: Mapping[str, object], rules: ScreeningRules) -> tuple[str, ...]:
    signals = [signal for signal in rules.keep_override_signals if _bool_feature(features, signal)]

    code_lines = _float_feature(features, "codeLines")
    if rules.minimum_code_lines_for_keep_override and code_lines >= rules.minimum_code_lines_for_keep_override:
        signals.append("codeLines")

    ratio_limit = rules.maximum_skill_to_source_ratio_for_keep_override
    if ratio_limit is not None:
        ratio = _float_feature(features, "skill_to_source_file_ratio")
        if ratio and ratio <= ratio_limit:
            signals.append("skill_to_source_file_ratio")

    return tuple(dict.fromkeys(signals))


def decide_repo(
    repo: str,
    features: Mapping[str, object],
    rules: ScreeningRules,
    blacklist: set[str] | frozenset[str] | None = None,
) -> ScreeningDecision:
    blacklist = blacklist or set()
    paths = str(features.get("skill_paths") or "").split("|")

    if repo in blacklist:
        return ScreeningDecision(repo, DECISION_EXCLUDE, "blacklist", (), (), rules.version)

    hard_name_matches = matched_name_terms(repo, rules.hard_exclude_name_terms)
    if hard_name_matches:
        return ScreeningDecision(
            repo,
            DECISION_EXCLUDE,
            f"name_filter:{hard_name_matches[0]}",
            hard_name_matches,
            (),
            rules.version,
        )

    hard_path_matches = matched_path_terms(paths, rules.hard_exclude_path_terms)
    if hard_path_matches:
        return ScreeningDecision(
            repo,
            DECISION_EXCLUDE,
            f"path_filter:{hard_path_matches[0]}",
            hard_path_matches,
            (),
            rules.version,
        )

    review_name_matches = matched_name_terms(repo, rules.review_name_terms)
    review_path_matches = matched_path_terms(paths, rules.review_path_terms)
    review_matches = review_name_matches + tuple(
        term for term in review_path_matches if term not in review_name_matches
    )
    signals = strong_software_signals(features, rules)

    if review_matches and signals:
        return ScreeningDecision(
            repo,
            DECISION_KEEP,
            "keep_override:strong_software_signals",
            review_matches,
            signals,
            rules.version,
        )

    if review_matches:
        reason_prefix = "name_review" if review_name_matches else "path_review"
        return ScreeningDecision(
            repo,
            DECISION_REVIEW,
            f"{reason_prefix}:{review_matches[0]}",
            review_matches,
            signals,
            rules.version,
        )

    if signals:
        return ScreeningDecision(repo, DECISION_KEEP, "software_project_signals", (), signals, rules.version)

    return ScreeningDecision(repo, DECISION_KEEP, "default_keep", (), (), rules.version)


def repo_folder_to_full_name(repo_folder: str) -> str:
    return str(repo_folder).replace("__", "/", 1)


def artifact_id_to_repo_and_skill_path(artifact_id: str) -> tuple[str, str]:
    cleaned = str(artifact_id).replace("\\", "/").strip("/")
    parts = cleaned.split("/", 1)
    repo = repo_folder_to_full_name(parts[0]) if parts else ""
    skill_parent = parts[1] if len(parts) > 1 else ""
    skill_path = f"{skill_parent}/SKILL.md" if skill_parent else "SKILL.md"
    return repo, skill_path


def load_blacklist(path: str | Path) -> set[str]:
    blacklist_path = Path(path)
    if not blacklist_path.exists():
        return set()
    entries: set[str] = set()
    with blacklist_path.open(encoding="utf-8") as handle:
        for line in handle:
            value = line.strip()
            if value and not value.startswith("#"):
                entries.add(value)
    return entries


def load_name_filter_log(path: str | Path) -> dict[str, str]:
    log_path = Path(path)
    if not log_path.exists():
        return {}
    matches: dict[str, str] = {}
    with log_path.open(encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2 and parts[0].strip():
                matches.setdefault(parts[0].strip(), parts[1].strip())
    return matches


def _row_repo(row: Mapping[str, object]) -> str:
    return str(row.get("repo") or row.get("name") or "").strip()


def _flag(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    return bool(value)


def _safe_int(value: object) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _append_paths(features: dict[str, dict[str, object]], repo: str, paths: Iterable[object]) -> None:
    current = set(str(features[repo].get("skill_paths") or "").split("|"))
    current.discard("")
    current.update(str(path).replace("\\", "/") for path in paths if str(path).strip())
    features[repo]["skill_paths"] = "|".join(sorted(current))


def build_repo_features(
    scan_csv: str | Path | None = None,
    found_csv: str | Path | None = None,
    instances_csv: str | Path | None = None,
    raw_data_dir: str | Path | None = None,
) -> pd.DataFrame:
    features: dict[str, dict[str, object]] = defaultdict(dict)

    if scan_csv and Path(scan_csv).exists():
        scan_df = pd.read_csv(scan_csv, low_memory=False)
        for _, row in scan_df.iterrows():
            repo = _row_repo(row)
            if not repo:
                continue
            out = features[repo]
            out["repo"] = repo
            for column in [
                "mainLanguage",
                "languages",
                "topics",
                "stars",
                "stargazers",
                "codeLines",
                "size",
                "has_README",
                "has_CONTRIBUTING",
                "has_SECURITY",
                "has_CODE_OF_CONDUCT",
                "has_CLAUDE",
                "has_AGENTS",
                "has_COPILOT",
            ]:
                if column in row and pd.notna(row[column]):
                    out[column] = row[column]

    if found_csv and Path(found_csv).exists():
        found_df = pd.read_csv(found_csv, low_memory=False)
        for repo, group in found_df.groupby("repo", dropna=True):
            repo = str(repo)
            features[repo]["repo"] = repo
            paths = [value for value in group.get("match_path", pd.Series(dtype=str)).dropna().astype(str)]
            _append_paths(features, repo, paths)
            features[repo]["stage2_match_count"] = len(group)

    if instances_csv and Path(instances_csv).exists():
        inst_df = pd.read_csv(instances_csv, low_memory=False)
        for repo, group in inst_df.groupby("repo", dropna=True):
            repo = str(repo)
            features[repo]["repo"] = repo
            skill_paths = group.get("skill_path", pd.Series(dtype=str)).dropna().astype(str).tolist()
            _append_paths(features, repo, skill_paths)
            skill_count = len(skill_paths)
            features[repo]["skill_file_count"] = skill_count
            code_lines = _safe_int(features[repo].get("codeLines"))
            if "codeLines" in group.columns and not code_lines:
                code_lines = int(pd.to_numeric(group["codeLines"], errors="coerce").fillna(0).max())
                features[repo]["codeLines"] = code_lines
            features[repo]["skill_to_source_file_ratio"] = skill_count / max(code_lines, 1)
            for column in ["has_README", "has_CONTRIBUTING", "has_SECURITY", "has_CODE_OF_CONDUCT"]:
                if column in group.columns:
                    features[repo][column] = int(pd.to_numeric(group[column], errors="coerce").fillna(0).max())

    if raw_data_dir and Path(raw_data_dir).exists():
        root = Path(raw_data_dir)
        for language_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            for repo_dir in sorted(path for path in language_dir.iterdir() if path.is_dir()):
                repo = repo_folder_to_full_name(repo_dir.name)
                out = features[repo]
                out["repo"] = repo
                out.setdefault("mainLanguage", language_dir.name)
                code_files = 0
                md_files = 0
                for file_path in repo_dir.rglob("*"):
                    if not file_path.is_file():
                        continue
                    rel = file_path.relative_to(repo_dir).as_posix().lower()
                    suffix = file_path.suffix.lower()
                    if suffix in CODE_SUFFIXES:
                        code_files += 1
                    if suffix in MARKDOWN_SUFFIXES:
                        md_files += 1
                    if rel.startswith("src/") or "/src/" in rel:
                        out["has_src_dir"] = 1
                    if rel.startswith("tests/") or rel.startswith("test/") or "/tests/" in rel or "/test/" in rel:
                        out["has_tests_dir"] = 1
                    if any(marker in rel for marker in CI_PATH_MARKERS):
                        out["has_ci_config"] = 1
                    manifest_flag = MANIFEST_FILENAMES.get(file_path.name.lower())
                    if manifest_flag:
                        out[manifest_flag] = 1
                out["raw_code_file_count"] = code_files
                out["raw_markdown_file_count"] = md_files
                out["markdown_to_code_ratio"] = md_files / max(code_files, 1)

    rows = []
    for repo, values in sorted(features.items()):
        row = {"repo": repo}
        row.update(values)
        row.setdefault("skill_file_count", row.get("stage2_match_count", 0))
        for flag in [
            "has_src_dir",
            "has_tests_dir",
            "has_ci_config",
            "has_package_json",
            "has_pyproject_toml",
            "has_go_mod",
            "has_cargo_toml",
            "has_pom_xml",
        ]:
            row[flag] = int(_flag(row.get(flag)))
        rows.append(row)
    return pd.DataFrame(rows)


def apply_rules_to_features(
    features_df: pd.DataFrame,
    rules: ScreeningRules,
    blacklist: set[str] | None = None,
) -> pd.DataFrame:
    rows = []
    for _, feature_row in features_df.fillna("").iterrows():
        repo = str(feature_row["repo"])
        decision = decide_repo(repo, feature_row.to_dict(), rules, blacklist)
        output = feature_row.to_dict()
        output.update(decision.as_row())
        rows.append(output)
    return pd.DataFrame(rows)


def load_screening_decisions(
    path: str | Path,
    *,
    final: bool = False,
) -> pd.DataFrame:
    decisions_path = Path(path)
    if not decisions_path.exists():
        raise FileNotFoundError(f"Screening decisions file not found: {decisions_path}")
    df = pd.read_csv(decisions_path, low_memory=False)
    required = {"repo", "decision"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Screening decisions file is missing required columns: {sorted(missing)}")

    df["decision"] = df["decision"].astype(str).str.strip().str.lower()
    invalid = sorted(set(df["decision"]) - DECISIONS)
    if invalid:
        raise ValueError(f"Screening decisions file contains invalid decisions: {invalid}")
    if final and (df["decision"] == DECISION_REVIEW).any():
        count = int((df["decision"] == DECISION_REVIEW).sum())
        raise ValueError(
            f"Screening decisions contain {count} unresolved review row(s); "
            "resolve them before running in final mode."
        )
    return df


def filter_dataframe_by_screening(
    df: pd.DataFrame,
    decisions: pd.DataFrame,
    *,
    repo_column: str = "repo",
    keep_missing: bool = True,
) -> pd.DataFrame:
    if repo_column not in df.columns or df.empty:
        return df
    keep_repos = set(
        decisions.loc[decisions["decision"].astype(str).str.lower() == DECISION_KEEP, "repo"].astype(str)
    )
    known_repos = set(decisions["repo"].astype(str))
    mask_keep = df[repo_column].astype(str).isin(keep_repos)
    if keep_missing:
        mask_keep = mask_keep | ~df[repo_column].astype(str).isin(known_repos)
    return df[mask_keep].reset_index(drop=True)


def write_csv(path: str | Path, rows: Sequence[Mapping[str, object]] | pd.DataFrame, fieldnames: Sequence[str] | None = None) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(rows, pd.DataFrame):
        rows.to_csv(output_path, index=False)
        return
    resolved_fieldnames = list(fieldnames or (list(rows[0].keys()) if rows else []))
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=resolved_fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def decision_counts(df: pd.DataFrame, label: str) -> dict[str, object]:
    counts = Counter(df.get("decision", pd.Series(dtype=str)).astype(str))
    return {
        "rule_version": label,
        "keep": counts.get(DECISION_KEEP, 0),
        "exclude": counts.get(DECISION_EXCLUDE, 0),
        "review": counts.get(DECISION_REVIEW, 0),
        "total": int(sum(counts.values())),
    }


def write_json(path: str | Path, payload: Mapping[str, object]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
