"""
client.py

GitHub API HTTP client backed by a TokenPool.

Each call to request_json() acquires the best available token from the pool,
injects it as an Authorization header for that specific request, then updates
the pool with the rate-limit headers from the response.

On 403/429 rate-limit responses the current bucket is marked exhausted and the
pool is asked to acquire a fresh token before retrying. Transient 5xx errors
and network failures use exponential backoff as before.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

import requests

from .token_pool import RateLimitExhaustedError, TokenBucket, TokenPool

log = logging.getLogger(__name__)


class GitHubClient:
    """
    Rate-limit-aware GitHub REST API client.

    Parameters
    ----------
    pool:
        A ``TokenPool`` instance. Pass ``TokenPool([])`` for unauthenticated
        access (60 req/hr). Pass ``TokenPool(["tok"])`` for a single token.
    base_url:
        Override for GitHub Enterprise or testing.
    """

    def __init__(
        self,
        pool: TokenPool,
        base_url: str = "https://api.github.com",
    ) -> None:
        self.pool = pool
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "skills-md-miner/1.0",
        })

    def request_json(
        self,
        method: str,
        path: str,
        params: Optional[dict] = None,
        max_retries: int = 5,
        timeout_s: int = 30,
    ) -> Tuple[int, dict, str]:
        """
        Execute a GitHub API request and return ``(status, json_body, error_msg)``.

        Token selection and rate-limit updates are handled transparently via
        the TokenPool. On rate-limit responses (403/429) the pool is asked for
        the next available token and the request is retried immediately (the
        pool handles the sleep when all tokens are exhausted).

        Transient server errors (5xx) and network failures use exponential
        backoff up to ``max_retries`` attempts.
        """
        url = f"{self.base_url}{path}"
        backoff = 2.0

        bucket: Optional[TokenBucket] = None

        # Two independent counters:
        # - transient_attempt: counts 5xx / network failures (bounded by max_retries)
        # - rl_attempt:        counts rate-limit waits (unbounded — always retries)
        transient_attempt = 0
        rl_attempt = 0

        while True:
            # Acquire a token. With max_wait_s=inf (default) this will sleep as
            # long as needed for a reset and then return — it never gives up.
            try:
                bucket = self.pool.acquire()
            except RateLimitExhaustedError as exc:
                # Only reachable when pool was constructed with a finite max_wait_s
                # (e.g. in tests). In production the default is inf.
                return (0, {}, f"rate_limit_exhausted: {exc}")

            # Build per-request headers so token rotation works across retries.
            extra_headers: dict = {}
            if bucket is not None:
                extra_headers["Authorization"] = f"Bearer {bucket.token}"

            try:
                resp = self.session.request(
                    method,
                    url,
                    params=params,
                    headers=extra_headers,
                    timeout=timeout_s,
                )
            except requests.RequestException as exc:
                self.pool.update(bucket, {})
                if transient_attempt >= max_retries:
                    return (0, {}, f"network_error: {exc}")
                log.debug("Network error on transient attempt %d: %s", transient_attempt, exc)
                transient_attempt += 1
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue

            status = resp.status_code

            # Always update the pool with the latest rate-limit headers.
            self.pool.update(bucket, dict(resp.headers))

            # Success
            if 200 <= status < 300:
                if resp.content:
                    try:
                        return (status, resp.json(), "")
                    except Exception:
                        return (status, {}, "json_parse_error")
                return (status, {}, "")

            # Auth / not-found: do not retry
            if status in (401, 404):
                return (status, {}, self._safe_error_message(resp))

            # Rate limiting or abuse throttling.
            # pool.update() already marked this bucket exhausted and recorded
            # the reset time (or Retry-After). pool.acquire() on the next
            # iteration will sleep until a token becomes available.
            # Rate-limit retries are UNBOUNDED — every repo is scanned.
            if status in (403, 429):
                rl_attempt += 1
                msg = self._safe_error_message(resp)
                log.warning(
                    "Rate-limit HTTP %d (rl_attempt=%d, token=%s). "
                    "Pipeline paused — waiting for quota reset then retrying.",
                    status, rl_attempt,
                    bucket.masked() if bucket else "none",
                )
                continue  # pool.acquire() on next iteration handles the sleep

            # Transient server errors: bounded by max_retries
            if 500 <= status <= 599:
                msg = self._safe_error_message(resp)
                if transient_attempt >= max_retries:
                    return (status, {}, msg)
                log.debug(
                    "Server error %d on transient attempt %d, backoff %.1fs",
                    status, transient_attempt, backoff,
                )
                transient_attempt += 1
                time.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue

            # Other non-retryable errors
            return (status, {}, self._safe_error_message(resp))

    @staticmethod
    def _safe_error_message(resp: requests.Response) -> str:
        try:
            data = resp.json()
            if isinstance(data, dict) and "message" in data:
                return str(data["message"])[:400]
        except Exception:
            pass
        return (resp.text or "").strip()[:400]
