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

import dataclasses
import datetime as dt
import logging
import os
import threading
import time
from typing import List, Optional

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


def load_tokens_from_env() -> List[str]:
    """
    Resolve tokens from environment variables.

    Priority:
      1. GH_TOKENS  (comma-separated, new multi-token variable)
      2. GH_TOKEN   (single token, backward-compatible)
      3. GITHUB_TOKEN (single token, backward-compatible)
    """
    for var in ("GH_TOKENS", "GH_TOKEN", "GITHUB_TOKEN"):
        raw = os.getenv(var, "").strip()
        if raw:
            tokens = [t.strip() for t in raw.split(",") if t.strip()]
            if tokens:
                return tokens
    return []


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
                candidates = [b for b in self._buckets if not b.is_exhausted]
                if candidates:
                    best = max(candidates, key=lambda b: b.remaining)
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

    def update(self, bucket: Optional[TokenBucket], headers: dict) -> None:
        """
        Update a token bucket's quota from GitHub response headers.

        Expects standard X-RateLimit-* headers::

            X-RateLimit-Remaining: 4998
            X-RateLimit-Limit:     5000
            X-RateLimit-Reset:     1700000000   (unix epoch)
        """
        if bucket is None:
            return

        with self._lock:
            try:
                remaining_str = headers.get("X-RateLimit-Remaining")
                limit_str = headers.get("X-RateLimit-Limit")
                reset_str = headers.get("X-RateLimit-Reset")

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
