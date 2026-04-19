#!/usr/bin/env python3
"""Fetch GitHub repository metadata and README content for a list of repos."""

from __future__ import annotations

import argparse
import base64
import logging
import os
import re
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import pandas as pd
from tqdm import tqdm
from tqdm.contrib.logging import logging_redirect_tqdm

from github_client import GitHubClient, TokenPool, load_tokens_from_env

log = logging.getLogger(__name__)

DEFAULT_INPUT_CSV = "outputs/full_skills_instances.csv"
DEFAULT_OUT_CSV = "outputs/repo_metadata_readmes/repo_metadata.csv"
DEFAULT_README_DIR = "outputs/repo_metadata_readmes/readmes"
DEFAULT_LANGUAGE = "Python"

README_SAFE_EXTENSIONS = {
    ".md",
    ".markdown",
    ".rst",
    ".txt",
    ".adoc",
    ".asciidoc",
    ".org",
}


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch GitHub repo metadata and README content for each repo in a CSV."
    )
    parser.add_argument(
        "--input-csv",
        default=DEFAULT_INPUT_CSV,
        help="Input CSV containing a repo column. Defaults to outputs/full_skills_instances.csv.",
    )
    parser.add_argument(
        "--repo-column",
        default="repo",
        help="Column containing owner/repo identifiers. Default: repo.",
    )
    parser.add_argument(
        "--language-column",
        default="mainLanguage",
        help="Column containing repository language values. Default: mainLanguage.",
    )
    parser.add_argument(
        "--language",
        default=DEFAULT_LANGUAGE,
        help="Only fetch repos whose language column matches this value. Default: Python.",
    )
    parser.add_argument(
        "--all-languages",
        action="store_true",
        help="Disable the default Python-only filter.",
    )
    parser.add_argument(
        "--out-csv",
        default=DEFAULT_OUT_CSV,
        help="Output metadata CSV path.",
    )
    parser.add_argument(
        "--readme-dir",
        default=DEFAULT_README_DIR,
        help="Directory where README files are written.",
    )
    parser.add_argument("--resume", action="store_true", help="Skip repos already present in --out-csv.")
    parser.add_argument("--concurrency", type=int, default=4, help="Worker threads.")
    parser.add_argument("--max-repos", type=int, default=0, help="Limit repos processed, after resume filtering.")
    parser.add_argument("--github-token", default="", help="Single GitHub token (overrides env).")
    parser.add_argument("--github-tokens", default="", help="Comma-separated GitHub tokens (overrides env).")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args(argv)


def resolve_tokens(args: argparse.Namespace) -> list[str]:
    raw_tokens = args.github_tokens.strip() or args.github_token.strip()
    if raw_tokens:
        return [token.strip() for token in raw_tokens.split(",") if token.strip()]
    return load_tokens_from_env()


def load_repos(
    input_csv: str,
    repo_column: str,
    language_column: str,
    language: str,
    all_languages: bool,
) -> list[str]:
    df = pd.read_csv(input_csv, low_memory=False)
    if repo_column not in df.columns:
        raise ValueError(f"Input CSV is missing the '{repo_column}' column")
    if not all_languages:
        if language_column not in df.columns:
            raise ValueError(
                f"Input CSV is missing the '{language_column}' column required for "
                "the Python-only default. Pass --all-languages to disable language filtering."
            )
        df = df[df[language_column].astype(str).str.casefold() == language.casefold()]

    repos = (
        df[repo_column]
        .dropna()
        .astype(str)
        .str.strip()
        .loc[lambda series: series.str.contains("/", regex=False)]
        .drop_duplicates()
        .sort_values()
        .tolist()
    )
    return repos


def repo_to_safe_folder(repo: str) -> str:
    return repo.replace("/", "__")


def readme_output_path(readme_dir: str, repo: str, readme_path: str) -> str:
    suffix = Path(readme_path).suffix.lower()
    extension = suffix if suffix in README_SAFE_EXTENSIONS else ".txt"
    return str(Path(readme_dir) / f"{repo_to_safe_folder(repo)}{extension}")


def decode_readme(body: dict[str, Any]) -> tuple[str, str]:
    encoding = str(body.get("encoding", "")).lower()
    content = body.get("content", "")
    if not isinstance(content, str) or not content:
        return ("", "empty_content")
    if encoding != "base64":
        return ("", f"unsupported_encoding:{encoding or 'unknown'}")

    compact = re.sub(r"\s+", "", content)
    try:
        decoded = base64.b64decode(compact, validate=True)
    except Exception as exc:
        return ("", f"base64_decode_error:{exc}")

    try:
        return (decoded.decode("utf-8"), "")
    except UnicodeDecodeError:
        return (decoded.decode("utf-8", errors="replace"), "utf8_replacement")


def flatten_repo_metadata(repo: str, body: dict[str, Any]) -> dict[str, Any]:
    license_data = body.get("license") if isinstance(body.get("license"), dict) else {}
    owner_data = body.get("owner") if isinstance(body.get("owner"), dict) else {}
    return {
        "repo": repo,
        "repo_id": body.get("id"),
        "node_id": body.get("node_id"),
        "full_name": body.get("full_name"),
        "owner_login": owner_data.get("login"),
        "owner_type": owner_data.get("type"),
        "private": body.get("private"),
        "fork": body.get("fork"),
        "archived": body.get("archived"),
        "disabled": body.get("disabled"),
        "is_template": body.get("is_template"),
        "html_url": body.get("html_url"),
        "description": body.get("description"),
        "homepage": body.get("homepage"),
        "default_branch": body.get("default_branch"),
        "language": body.get("language"),
        "license_key": license_data.get("key"),
        "license_name": license_data.get("name"),
        "stars": body.get("stargazers_count"),
        "watchers": body.get("watchers_count"),
        "forks": body.get("forks_count"),
        "open_issues": body.get("open_issues_count"),
        "subscribers": body.get("subscribers_count"),
        "network_count": body.get("network_count"),
        "size": body.get("size"),
        "topics": ";".join(body.get("topics", []) if isinstance(body.get("topics"), list) else []),
        "created_at": body.get("created_at"),
        "updated_at": body.get("updated_at"),
        "pushed_at": body.get("pushed_at"),
    }


def fetch_repo(gh: GitHubClient, repo: str, readme_dir: str) -> dict[str, Any]:
    owner, name = repo.split("/", 1)
    row: dict[str, Any] = {
        "repo": repo,
        "metadata_status": None,
        "metadata_error": "",
        "readme_status": None,
        "readme_error": "",
        "readme_path": "",
        "readme_name": "",
        "readme_html_url": "",
        "readme_download_url": "",
        "readme_size_bytes": None,
        "readme_local_path": "",
    }

    status, metadata_body, metadata_err = gh.request_json("GET", f"/repos/{owner}/{name}")
    row["metadata_status"] = status
    if status != 200:
        row["metadata_error"] = metadata_err
        return row
    row.update(flatten_repo_metadata(repo, metadata_body))

    readme_status, readme_body, readme_err = gh.request_json("GET", f"/repos/{owner}/{name}/readme")
    row["readme_status"] = readme_status
    if readme_status != 200:
        row["readme_error"] = readme_err
        return row

    readme_path = str(readme_body.get("path", "README"))
    readme_text, decode_error = decode_readme(readme_body)
    local_path = readme_output_path(readme_dir, repo, readme_path)
    Path(local_path).parent.mkdir(parents=True, exist_ok=True)
    Path(local_path).write_text(readme_text, encoding="utf-8", newline="")

    row.update(
        {
            "readme_error": decode_error,
            "readme_path": readme_path,
            "readme_name": readme_body.get("name", ""),
            "readme_html_url": readme_body.get("html_url", ""),
            "readme_download_url": readme_body.get("download_url", ""),
            "readme_size_bytes": readme_body.get("size"),
            "readme_local_path": local_path,
        }
    )
    return row


def write_csv_atomically(df: pd.DataFrame, out_csv: str) -> None:
    out_path = Path(out_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=out_path.parent,
        suffix=out_path.suffix,
        encoding="utf-8",
        newline="",
    ) as handle:
        temp_path = Path(handle.name)
        df.to_csv(handle.name, index=False)
    os.replace(temp_path, out_path)


def load_existing_rows(out_csv: str) -> pd.DataFrame:
    if not os.path.exists(out_csv):
        return pd.DataFrame()
    existing = pd.read_csv(out_csv, low_memory=False)
    if "repo" not in existing.columns:
        raise ValueError(f"Existing output is missing repo column: {out_csv}")
    return existing.drop_duplicates(subset=["repo"], keep="last")


def successful_existing_repos(existing: pd.DataFrame) -> set[str]:
    if existing.empty or "repo" not in existing.columns or "metadata_status" not in existing.columns:
        return set()
    metadata_ok = pd.to_numeric(existing["metadata_status"], errors="coerce") == 200
    return set(existing.loc[metadata_ok, "repo"].astype(str))


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    configure_logging(args.log_level)

    repos = load_repos(
        args.input_csv,
        args.repo_column,
        args.language_column,
        args.language,
        args.all_languages,
    )
    existing = load_existing_rows(args.out_csv) if args.resume else pd.DataFrame()
    done_repos = successful_existing_repos(existing) if args.resume else set()
    pending = [repo for repo in repos if repo not in done_repos]
    if args.max_repos and args.max_repos > 0:
        pending = pending[: args.max_repos]

    if not pending:
        log.info("No repositories need metadata/README fetching.")
        if not existing.empty:
            write_csv_atomically(existing, args.out_csv)
        return 0

    tokens = resolve_tokens(args)
    if not tokens:
        log.warning(
            "No GitHub token detected. Unauthenticated core rate limits are low. "
            "Set GH_TOKENS or pass --github-tokens / --github-token."
        )

    gh = GitHubClient(pool=TokenPool(tokens))
    rows = existing.to_dict("records") if not existing.empty else []
    failures = 0

    log.info(
        "Fetching metadata and READMEs for %d repositories (total=%d, skipped=%d, concurrency=%d)",
        len(pending),
        len(repos),
        len(done_repos),
        args.concurrency,
    )

    with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as executor:
        futures = {executor.submit(fetch_repo, gh, repo, args.readme_dir): repo for repo in pending}
        with logging_redirect_tqdm():
            with tqdm(total=len(pending), desc="Repo metadata", unit="repo", file=sys.stderr) as pbar:
                for count, future in enumerate(as_completed(futures), start=1):
                    repo = futures[future]
                    try:
                        row = future.result()
                    except Exception as exc:
                        failures += 1
                        row = {
                            "repo": repo,
                            "metadata_status": 0,
                            "metadata_error": f"exception:{exc}",
                            "readme_status": 0,
                            "readme_error": "skipped",
                        }
                        log.exception("Fetch failed for %s", repo)
                    else:
                        if row.get("metadata_status") != 200 or row.get("readme_status") not in {200, 404}:
                            failures += 1

                    rows.append(row)
                    if count % 100 == 0 or count == len(pending):
                        write_csv_atomically(pd.DataFrame(rows), args.out_csv)

                    pbar.set_postfix(failures=failures, refresh=False)
                    pbar.update(1)

    write_csv_atomically(pd.DataFrame(rows).drop_duplicates(subset=["repo"], keep="last"), args.out_csv)
    log.info("Done. Wrote %d rows to %s", len(rows), args.out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
