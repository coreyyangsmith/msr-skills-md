#!/usr/bin/env python3
"""
Validate GitHub personal access tokens against the REST API.

Resolves tokens the same way as pipeline scripts: CLI flags first, then GH_TOKENS
from the environment / .env (via load_tokens_from_env).

Each token is checked with GET /user (one core API request per token).
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path
from typing import Any

import requests

# Allow `from github_client...` when run as a script (repo not installed as a package).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SRC = _REPO_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from github_client.token_pool import TokenBucket, load_tokens_from_env  # noqa: E402


def _mask(token: str) -> str:
    return TokenBucket(token=token).masked()


def _safe_api_message(resp: requests.Response) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict) and "message" in data:
            return str(data["message"])[:200]
    except Exception:
        pass
    return (resp.text or "").strip()[:200]


def _format_reset(reset_epoch: float | None) -> str:
    if not reset_epoch:
        return "—"
    try:
        ts = float(reset_epoch)
        return dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).strftime("%H:%M:%SZ")
    except (ValueError, TypeError, OSError):
        return "—"


def check_token(
    token: str,
    *,
    base_url: str,
    timeout: float,
) -> dict[str, Any]:
    """
    Call GET /user for one token.

    Returns keys: status, ok (200), invalid (401/403), suspect (other non-200),
    login, remaining, limit, reset_epoch, error_detail, exc (if request failed).
    """
    url = f"{base_url.rstrip('/')}/user"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Authorization": f"Bearer {token}",
        "User-Agent": "msr-skills-md-test-gh-tokens/1.0",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        return {
            "status": 0,
            "ok": False,
            "invalid": False,
            "suspect": True,
            "login": None,
            "remaining": None,
            "limit": None,
            "reset_epoch": None,
            "error_detail": str(exc)[:200],
            "exc": exc,
        }

    status = resp.status_code
    rh = {k.lower(): v for k, v in resp.headers.items()}
    remaining = rh.get("x-ratelimit-remaining")
    limit = rh.get("x-ratelimit-limit")
    reset_str = rh.get("x-ratelimit-reset")
    reset_epoch: float | None = None
    if reset_str is not None:
        try:
            reset_epoch = float(reset_str)
        except (ValueError, TypeError):
            pass

    login = None
    if status == 200:
        try:
            body = resp.json()
            if isinstance(body, dict):
                login = body.get("login")
        except Exception:
            pass

    invalid = status in (401, 403)
    ok = status == 200
    suspect = not ok and not invalid

    err = ""
    if not ok:
        err = _safe_api_message(resp) or f"HTTP {status}"

    return {
        "status": status,
        "ok": ok,
        "invalid": invalid,
        "suspect": suspect,
        "login": login,
        "remaining": remaining,
        "limit": limit,
        "reset_epoch": reset_epoch,
        "error_detail": err,
        "exc": None,
    }


def resolve_tokens(github_tokens: str, github_token: str) -> list[str]:
    raw = (github_tokens or "").strip() or (github_token or "").strip()
    if raw:
        return [t.strip() for t in raw.split(",") if t.strip()]
    return load_tokens_from_env()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test GitHub tokens (GET /user) and list any that should be removed.",
    )
    parser.add_argument(
        "--github-tokens",
        default="",
        help="Comma-separated PATs (overrides env when non-empty).",
    )
    parser.add_argument(
        "--github-token",
        default="",
        help="Single PAT or comma-separated list (same as --github-tokens).",
    )
    parser.add_argument(
        "--base-url",
        default="https://api.github.com",
        help="API base URL (GitHub.com default).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="HTTP timeout in seconds (default: 10).",
    )
    args = parser.parse_args()

    tokens = resolve_tokens(args.github_tokens, args.github_token)
    if not tokens:
        print(
            "Error: No tokens found. Set GH_TOKENS in .env or pass "
            "--github-tokens / --github-token.",
            file=sys.stderr,
        )
        sys.exit(2)

    n = len(tokens)
    print(f"Checking {n} token(s)...\n")

    results: list[dict[str, Any]] = []
    for i, tok in enumerate(tokens, start=1):
        m = _mask(tok)
        r = check_token(tok, base_url=args.base_url, timeout=args.timeout)
        results.append({**r, "masked": m})

        if r.get("exc") is not None:
            line = (
                f"  [{i}/{n}] {m}  SUSPECT  network_error: {r['error_detail']}  "
                "(investigate)"
            )
            print(line)
            continue

        status = r["status"]
        if r["ok"]:
            rem = r["remaining"]
            lim = r["limit"]
            quota = f"remaining={rem}/{lim}" if rem is not None and lim is not None else "quota=—"
            reset = _format_reset(r.get("reset_epoch"))
            login = r["login"] or "?"
            print(
                f"  [{i}/{n}] {m}  OK      login={login}  {quota}  reset={reset}",
            )
        elif r["invalid"]:
            print(
                f"  [{i}/{n}] {m}  INVALID  HTTP {status} – {r['error_detail']}  ← REMOVE",
            )
        else:
            print(
                f"  [{i}/{n}] {m}  SUSPECT  HTTP {status} – {r['error_detail']}  "
                "(investigate)",
            )

    valid = sum(1 for r in results if r["ok"])
    invalid = [r for r in results if r.get("invalid")]

    print()
    print(f"Summary: {valid} valid, {len(invalid)} invalid.")
    if invalid:
        print("Tokens to remove from GH_TOKENS:")
        for r in invalid:
            print(f"  {r['masked']}")

    # Exit 0 only if every token returned HTTP 200 from /user.
    if valid == n:
        sys.exit(0)
    sys.exit(1)


if __name__ == "__main__":
    main()
