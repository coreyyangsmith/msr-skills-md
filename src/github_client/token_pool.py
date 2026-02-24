"""
token_pool.py

Multi-token GitHub API rate-limit manager.

Supports receiving one or more GitHub PATs (via env or constructor), tracking
each token's remaining quota against the 5000 req/hr per-token limit, and
automatically rotating to the least-exhausted token on every request.

When all tokens are exhausted it sleeps until the earliest reset time, then
re-issues the request. If the required wait exceeds ``max_wait_s`` a
``RateLimitExhaustedError`` is raised so callers can decide whether to abort.
"""

from __future__ import annotations

import collections
import dataclasses
import datetime as dt
import json
import logging
import os
import threading
import time
from typing import Dict, Deque, List, Optional

from dotenv import dotenv_values, find_dotenv, load_dotenv

log = logging.getLogger(__name__)

_GITHUB_RATE_LIMIT = 5000  # authenticated requests per hour per token


class RateLimitExhaustedError(Exception):
    """Raised when all tokens are exhausted and the wait would exceed max_wait_s."""


@dataclasses.dataclass
class TokenBucket:
    token: str                      # raw PAT -- never logged
    remaining: int = _GITHUB_RATE_LIMIT
    limit: int = _GITHUB_RATE_LIMIT
    reset_epoch: float = 0.0        # X-RateLimit-Reset (unix epoch seconds)
    is_exhausted: bool = False
    request_count: int = 0          # cumulative requests made with this token

    def masked(self) -> str:
        """Return a safe masked representation for logging."""
        if len(self.token) <= 8:
            return "***"
        return f"{self.token[:4]}...{self.token[-4:]}"


def _parse_token_string(raw: str) -> List[str]:
    """
    Parse a token string into a list of tokens.

    Accepts two formats:
      - JSON array:       ``["ghp_tok1", "ghp_tok2"]``
      - Comma-separated:  ``ghp_tok1,ghp_tok2``

    Comment-only fragments (stripped value starts with ``#``) produced by
    a failed JSON parse / comma-split are silently discarded.
    """
    raw = raw.strip()
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(t).strip() for t in parsed if str(t).strip()]
        except json.JSONDecodeError:
            pass
    # Fallback: comma-split.  Strip leading/trailing JSON bracket/quote
    # characters that leak in when json.loads() fails on a broken array.
    tokens = []
    for fragment in raw.split(","):
        t = fragment.strip().strip('[]"\'')
        if t and not t.startswith("#"):
            tokens.append(t)
    return tokens


def _read_dotenv_multiline(dotenv_path: str, key: str) -> str:
    """
    Read a potentially multi-line value for ``key`` from a ``.env`` file.

    python-dotenv stops at the first newline for unquoted values, so a
    JSON array written across multiple lines::

        GH_TOKENS=[
            "ghp_tok1",
            # optional comment lines are ignored
            "ghp_tok2"
        ]

    is not parsed correctly by ``dotenv_values()``.  This function reads
    the raw file text, skips comment lines (those whose non-whitespace
    content starts with ``#``), and stitches continuation lines together
    until the JSON array bracket is closed.
    """
    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except OSError:
        return ""

    collecting = False
    parts: list[str] = []
    for line in lines:
        stripped = line.rstrip("\n").rstrip("\r")
        content = stripped.strip()

        # Skip comment-only lines regardless of position.
        if content.startswith("#"):
            continue

        if not collecting:
            if stripped.startswith(f"{key}="):
                value_part = stripped[len(key) + 1:]
                parts.append(value_part)
                # Check if the value is complete (balanced brackets or no bracket)
                joined = "".join(parts)
                if not joined.startswith("[") or joined.count("[") == joined.count("]"):
                    break
                collecting = True
        else:
            parts.append(stripped)
            joined = "".join(parts)
            if joined.count("[") == joined.count("]"):
                break

    return "".join(parts).strip()


def load_tokens_from_env() -> List[str]:
    """
    Resolve tokens from environment variables, loading ``.env`` automatically.

    Searches for a ``.env`` file starting from the current working directory
    and walking upward.  Multi-line JSON arrays (values that span several
    lines) are handled by a custom reader because python-dotenv stops at the
    first newline for unquoted values.

    ``GH_TOKENS`` accepts either a JSON array or a comma-separated string::

        GH_TOKENS=["ghp_tok1","ghp_tok2"]   # JSON array, single line
        GH_TOKENS=[                          # JSON array, multi-line
            "ghp_tok1",
            "ghp_tok2"
        ]
        GH_TOKENS=ghp_tok1,ghp_tok2          # comma-separated

    Only ``GH_TOKENS`` is consulted.
    """
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        load_dotenv(dotenv_path=dotenv_path, override=False)
        log.debug("Loaded .env from: %s", dotenv_path)

    # os.getenv reflects values written by load_dotenv (single-line ones).
    raw = os.getenv("GH_TOKENS", "").strip()

    # If the value is incomplete (e.g. just "["), the JSON array is multi-line.
    # Fall back to the manual multi-line reader.
    if not raw or (raw.startswith("[") and raw.count("[") != raw.count("]")):
        if dotenv_path:
            raw = _read_dotenv_multiline(dotenv_path, "GH_TOKENS")
            log.debug("Multi-line .env reader returned: %.40r ...", raw)

    if not raw:
        log.warning("GH_TOKENS is not set in the environment or .env file.")
        return []

    tokens = _parse_token_string(raw)

    if tokens:
        masked = [f"{t[:4]}...{t[-4:]}" if len(t) > 8 else "***" for t in tokens]
        log.info("Token pool loaded %d token(s) from GH_TOKENS: %s", len(tokens), masked)
    else:
        log.warning(
            "GH_TOKENS was set but no valid tokens could be parsed "
            "(raw value starts with: %.30r)", raw
        )

    return tokens


class SearchThrottle:
    """
    Thread-safe per-token sliding-window throttle for the GitHub Code Search API.

    GitHub allows only **10** authenticated code-search requests per minute per
    token (``/search/code`` has its own rate-limit category, separate from the
    30 req/min limit used by other ``/search/*`` endpoints).

    This class tracks a deque of request timestamps for each token and blocks
    callers that would exceed the limit, spreading requests smoothly across time
    instead of letting threads race to a 403.

    Usage::

        throttle = SearchThrottle()          # defaults to 10 req/min
        waited = throttle.wait_if_needed(bucket.token)
        # ... make the search request ...
    """

    def __init__(self, max_per_minute: int = 10, window_s: float = 60.0) -> None:
        self._max = max_per_minute
        self._window_s = window_s
        self._lock = threading.Lock()
        # Maps masked token → deque of float timestamps (time.time())
        self._windows: Dict[str, Deque[float]] = {}

    # Use a stable key that never logs the raw token.
    @staticmethod
    def _key(token: str) -> str:
        if len(token) <= 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"

    def wait_if_needed(self, token: str) -> float:
        """
        Block until ``token`` has remaining search quota, then record the request.

        Returns the number of seconds the caller was paused (0.0 if no wait).
        """
        key = self._key(token)
        total_waited = 0.0

        while True:
            with self._lock:
                now = time.time()
                dq = self._windows.setdefault(key, collections.deque())

                # Prune timestamps that have slid out of the window.
                cutoff = now - self._window_s
                while dq and dq[0] <= cutoff:
                    dq.popleft()

                if len(dq) < self._max:
                    # Quota available — record this request and proceed.
                    dq.append(now)
                    if total_waited > 0.0:
                        log.debug(
                            "SearchThrottle [%s]: quota restored after %.1fs wait.",
                            key, total_waited,
                        )
                    return total_waited

                # Quota full — compute how long until the oldest request ages out.
                sleep_until = dq[0] + self._window_s
                wait_s = max(0.01, sleep_until - now)
                log.warning(
                    "SearchThrottle [%s]: %d/%d code-search slots used. "
                    "Pausing %.1fs to stay within %d req/min limit.",
                    key, len(dq), self._max, wait_s, self._max,
                )

            # Release the lock while sleeping so other threads can proceed.
            time.sleep(wait_s)
            total_waited += wait_s


class TokenPool:
    """
    Thread-safe pool of GitHub API tokens.

    Usage::

        pool = TokenPool(["ghp_token1", "ghp_token2"])
        bucket = pool.acquire()
        # ... make HTTP request using bucket.token ...
        pool.update(bucket, response.headers)
    """

    def __init__(
        self,
        tokens: List[str],
        max_wait_s: float = float("inf"),  # wait forever by default; rate limits always reset
    ) -> None:
        # Deduplicate while preserving order.
        seen: set[str] = set()
        unique: List[str] = []
        for t in tokens:
            if t and t not in seen:
                seen.add(t)
                unique.append(t)

        self._buckets: List[TokenBucket] = [TokenBucket(token=t) for t in unique]
        self._lock = threading.Lock()
        self._max_wait_s = max_wait_s

        if self._buckets:
            log.info("TokenPool initialised with %d token(s).", len(self._buckets))
        else:
            log.warning(
                "TokenPool has no tokens. Running unauthenticated "
                "(60 core req/hr limit)."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_authenticated(self) -> bool:
        return bool(self._buckets)

    def acquire(self) -> Optional[TokenBucket]:
        """
        Return the best available token bucket.

        Selection order:
          1. Pick the non-exhausted bucket with the highest ``remaining``.
          2. If all are exhausted, sleep until the soonest ``reset_epoch``,
             then return that bucket.
          3. If the required wait > ``max_wait_s``, raise RateLimitExhaustedError.

        Returns ``None`` when the pool has no tokens (unauthenticated mode).
        """
        if not self._buckets:
            return None

        while True:
            with self._lock:
                now = time.time()

                # Un-exhaust any bucket whose reset time has passed.
                for b in self._buckets:
                    if b.is_exhausted and b.reset_epoch and now >= b.reset_epoch:
                        b.is_exhausted = False
                        b.remaining = b.limit or _GITHUB_RATE_LIMIT
                        log.debug(
                            "Token %s reset – remaining restored to %d.",
                            b.masked(), b.remaining,
                        )

                # Find the best non-exhausted bucket.
                # Primary key: most remaining quota (avoids near-exhausted tokens).
                # Tie-breaker: fewest requests made (-request_count), which
                # round-robins tokens when their remaining counts are equal.
                # This is critical for search-only workloads: because search API
                # responses no longer overwrite bucket.remaining (to avoid
                # clobbering core-API quota), all search tokens stay at their
                # initial remaining=5000, so without the tie-breaker the pool
                # would always pick the same token, wasting the others.
                candidates = [b for b in self._buckets if not b.is_exhausted]
                if candidates:
                    best = max(candidates, key=lambda b: (b.remaining, -b.request_count))
                    best.request_count += 1
                    return best

                # All exhausted – compute minimum wait.
                valid_resets = [b.reset_epoch for b in self._buckets if b.reset_epoch > 0]
                if valid_resets:
                    earliest = min(valid_resets)
                    wait_s = max(0.0, earliest - now) + 2.0
                else:
                    wait_s = 60.0  # conservative fallback

                if wait_s > self._max_wait_s:
                    raise RateLimitExhaustedError(
                        f"All tokens exhausted. Earliest reset in {wait_s:.0f}s "
                        f"exceeds max_wait_s={self._max_wait_s:.0f}s."
                    )

                log.warning(
                    "All %d token(s) exhausted. Pausing %.0fs until earliest reset "
                    "(~%s). Pipeline will resume automatically.",
                    len(self._buckets),
                    wait_s,
                    dt.datetime.fromtimestamp(
                        earliest if valid_resets else time.time() + wait_s,
                        dt.timezone.utc,
                    ).strftime("%H:%M:%SZ"),
                )

            # Release the lock while sleeping so other threads can still call update().
            time.sleep(wait_s)

    def update(
        self,
        bucket: Optional[TokenBucket],
        headers: dict,
        is_search: bool = False,
    ) -> None:
        """
        Update a token bucket's quota from GitHub response headers.

        Expects standard X-RateLimit-* headers::

            X-RateLimit-Remaining: 4998
            X-RateLimit-Limit:     5000
            X-RateLimit-Reset:     1700000000   (unix epoch)

        Pass ``is_search=True`` for Code Search API responses.  In that case
        the bucket's ``remaining`` and ``limit`` fields (which track the core
        API quota, 5 000 req/hr) are **not** overwritten by the search-specific
        values (10 req/min for ``/search/code``).  The ``reset_epoch`` and
        ``is_exhausted`` flag are still updated so that ``acquire()`` sleeps
        for the correct ~60 s when the search quota is spent.
        """
        if bucket is None:
            return

        with self._lock:
            try:
                remaining_str = headers.get("X-RateLimit-Remaining")
                limit_str = headers.get("X-RateLimit-Limit")
                reset_str = headers.get("X-RateLimit-Reset")

                if is_search:
                    # /search/code has a separate rate-limit pool (10 req/min
                    # authenticated).  Never overwrite the core quota counters;
                    # only update timing so the pool sleeps the right amount
                    # when search is exhausted.
                    search_remaining = int(remaining_str) if remaining_str is not None else None
                    search_limit = int(limit_str) if limit_str is not None else None
                    if reset_str is not None:
                        bucket.reset_epoch = float(reset_str)

                    # Secondary rate limits.
                    retry_after_str = headers.get("Retry-After")
                    if retry_after_str is not None:
                        try:
                            retry_after_s = float(retry_after_str)
                            synthetic_reset = time.time() + retry_after_s
                            bucket.reset_epoch = max(bucket.reset_epoch, synthetic_reset)
                            if not bucket.is_exhausted:
                                log.warning(
                                    "Token %s hit secondary rate limit (Retry-After=%.0fs).",
                                    bucket.masked(), retry_after_s,
                                )
                            bucket.is_exhausted = True
                        except (ValueError, TypeError):
                            pass
                        return

                    if search_remaining == 0 and bucket.reset_epoch > time.time():
                        if not bucket.is_exhausted:
                            log.warning(
                                "Token %s code-search quota exhausted "
                                "(limit=%s req/min, resets in ~%.0fs).",
                                bucket.masked(),
                                search_limit,
                                max(0.0, bucket.reset_epoch - time.time()),
                            )
                        bucket.is_exhausted = True
                    elif search_remaining is not None and search_remaining > 0:
                        bucket.is_exhausted = False
                    return

                # Core API path — update all quota fields.
                if remaining_str is not None:
                    bucket.remaining = int(remaining_str)
                if limit_str is not None:
                    bucket.limit = int(limit_str)
                if reset_str is not None:
                    bucket.reset_epoch = float(reset_str)

                # Secondary rate limits (abuse detection) use Retry-After instead
                # of X-RateLimit-Reset. Synthesise a reset_epoch from it so that
                # acquire() sleeps for the right duration before retrying.
                retry_after_str = headers.get("Retry-After")
                if retry_after_str is not None:
                    try:
                        retry_after_s = float(retry_after_str)
                        synthetic_reset = time.time() + retry_after_s
                        # Only extend the reset epoch; never shorten it.
                        bucket.reset_epoch = max(bucket.reset_epoch, synthetic_reset)
                        bucket.remaining = 0
                        if not bucket.is_exhausted:
                            log.warning(
                                "Token %s hit secondary rate limit (Retry-After=%.0fs).",
                                bucket.masked(), retry_after_s,
                            )
                        bucket.is_exhausted = True
                    except (ValueError, TypeError):
                        pass

                # Mark exhausted when primary quota is spent and reset is in the future.
                if bucket.remaining == 0 and bucket.reset_epoch > time.time():
                    if not bucket.is_exhausted:
                        log.warning(
                            "Token %s exhausted (limit=%d, resets in ~%.0fs).",
                            bucket.masked(),
                            bucket.limit,
                            max(0.0, bucket.reset_epoch - time.time()),
                        )
                    bucket.is_exhausted = True
                elif retry_after_str is None:
                    # Only un-exhaust via primary headers if no Retry-After was set.
                    bucket.is_exhausted = False

            except (ValueError, TypeError) as exc:
                log.debug("Could not parse rate-limit headers: %s", exc)

    def stats(self) -> dict:
        """Return a snapshot of pool statistics for logging/monitoring."""
        with self._lock:
            per_token = [
                {
                    "token": b.masked(),
                    "remaining": b.remaining,
                    "limit": b.limit,
                    "reset_epoch": b.reset_epoch,
                    "is_exhausted": b.is_exhausted,
                    "request_count": b.request_count,
                }
                for b in self._buckets
            ]
            return {
                "token_count": len(self._buckets),
                "total_requests": sum(b.request_count for b in self._buckets),
                "total_remaining": sum(b.remaining for b in self._buckets),
                "tokens": per_token,
            }
