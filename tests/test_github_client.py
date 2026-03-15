"""
Tests for src/github_client/

Covers:
- TokenBucket  (dataclass behaviour, masked())
- TokenPool    (init/dedup, acquire(), update(), stats(), exhaustion, backoff,
                thread-safety, unauthenticated mode)
- GitHubClient (request_json(), token rotation, 403/429 retry, 5xx backoff,
                network errors, unauthenticated mode)
- load_tokens_from_env (env-var resolution priority)

All tests are deterministic: no real network calls, time is frozen where
relevant, and env isolation uses mock.patch.dict.
"""

from __future__ import annotations

import sys
import threading
import time
import unittest
import unittest.mock as mock
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from github_client import GitHubClient, RateLimitExhaustedError, TokenBucket, TokenPool
from github_client.token_pool import load_tokens_from_env


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(
    status_code: int,
    json_data: dict | None = None,
    text: str = "",
    headers: dict | None = None,
) -> mock.MagicMock:
    resp = mock.MagicMock()
    resp.status_code = status_code
    resp.headers = headers or {}
    resp.text = text
    if json_data is not None:
        resp.content = b"x"
        resp.json.return_value = json_data
    else:
        resp.content = b""
        resp.json.side_effect = Exception("no body")
    return resp


def _pool(*tokens: str, max_wait_s: float = 900.0) -> TokenPool:
    return TokenPool(list(tokens), max_wait_s=max_wait_s)


def _gh(*tokens: str) -> GitHubClient:
    return GitHubClient(pool=_pool(*tokens))


# ---------------------------------------------------------------------------
# load_tokens_from_env
# ---------------------------------------------------------------------------

class TestLoadTokensFromEnv(unittest.TestCase):

    def test_gh_tokens_takes_priority(self):
        with mock.patch.dict("os.environ", {
            "GH_TOKENS": "tok1,tok2",
            "GH_TOKEN": "single",
            "GITHUB_TOKEN": "other",
        }, clear=False):
            result = load_tokens_from_env()
        self.assertEqual(result, ["tok1", "tok2"])

    def test_gh_token_is_ignored_without_gh_tokens(self):
        env = {"GH_TOKEN": "only_one"}
        with mock.patch.dict("os.environ", env, clear=True):
            with mock.patch("github_client.token_pool.find_dotenv", return_value=""):
                with mock.patch.dict("os.environ", {"GH_TOKENS": ""}, clear=False):
                    result = load_tokens_from_env()
        self.assertEqual(result, [])

    def test_github_token_is_ignored_without_gh_tokens(self):
        with mock.patch.dict("os.environ", {
            "GH_TOKENS": "",
            "GH_TOKEN": "",
            "GITHUB_TOKEN": "fallback_tok",
        }, clear=True):
            with mock.patch("github_client.token_pool.find_dotenv", return_value=""):
                result = load_tokens_from_env()
        self.assertEqual(result, [])

    def test_no_env_returns_empty(self):
        with mock.patch.dict("os.environ", {
            "GH_TOKENS": "",
            "GH_TOKEN": "",
            "GITHUB_TOKEN": "",
        }, clear=True):
            with mock.patch("github_client.token_pool.find_dotenv", return_value=""):
                result = load_tokens_from_env()
        self.assertEqual(result, [])

    def test_comma_separated_parsed(self):
        with mock.patch.dict("os.environ", {"GH_TOKENS": "a,b,c", "GH_TOKEN": "", "GITHUB_TOKEN": ""}, clear=False):
            result = load_tokens_from_env()
        self.assertEqual(result, ["a", "b", "c"])

    def test_whitespace_stripped(self):
        with mock.patch.dict("os.environ", {"GH_TOKENS": " tok1 , tok2 ", "GH_TOKEN": "", "GITHUB_TOKEN": ""}, clear=False):
            result = load_tokens_from_env()
        self.assertEqual(result, ["tok1", "tok2"])


# ---------------------------------------------------------------------------
# TokenBucket
# ---------------------------------------------------------------------------

class TestTokenBucket(unittest.TestCase):

    def test_default_values(self):
        b = TokenBucket(token="ghp_test")
        self.assertEqual(b.remaining, 5000)
        self.assertEqual(b.limit, 5000)
        self.assertEqual(b.reset_epoch, 0.0)
        self.assertFalse(b.is_exhausted)
        self.assertEqual(b.request_count, 0)

    def test_masked_hides_token(self):
        b = TokenBucket(token="ghp_ABCDEFGHIJ1234")
        masked = b.masked()
        self.assertNotIn("ABCDEFGHIJ", masked)
        self.assertIn("...", masked)

    def test_masked_short_token(self):
        b = TokenBucket(token="abc")
        self.assertEqual(b.masked(), "***")

    def test_masked_exactly_eight_chars(self):
        b = TokenBucket(token="12345678")
        self.assertEqual(b.masked(), "***")


# ---------------------------------------------------------------------------
# TokenPool – initialisation & deduplication
# ---------------------------------------------------------------------------

class TestTokenPoolInit(unittest.TestCase):

    def test_single_token(self):
        pool = _pool("tok1")
        self.assertEqual(len(pool._buckets), 1)

    def test_multiple_tokens(self):
        pool = _pool("tok1", "tok2", "tok3")
        self.assertEqual(len(pool._buckets), 3)

    def test_deduplication(self):
        pool = _pool("tok1", "tok2", "tok1", "tok2")
        self.assertEqual(len(pool._buckets), 2)

    def test_empty_pool(self):
        pool = _pool()
        self.assertFalse(pool.is_authenticated)
        self.assertEqual(len(pool._buckets), 0)

    def test_non_empty_pool_is_authenticated(self):
        pool = _pool("tok1")
        self.assertTrue(pool.is_authenticated)

    def test_empty_strings_ignored(self):
        pool = TokenPool(["", "tok1", ""])
        self.assertEqual(len(pool._buckets), 1)


# ---------------------------------------------------------------------------
# TokenPool – acquire()
# ---------------------------------------------------------------------------

class TestTokenPoolAcquire(unittest.TestCase):

    def test_acquire_returns_none_when_empty(self):
        pool = _pool()
        bucket = pool.acquire()
        self.assertIsNone(bucket)

    def test_acquire_single_token(self):
        pool = _pool("tok1")
        bucket = pool.acquire()
        self.assertIsNotNone(bucket)
        self.assertEqual(bucket.token, "tok1")

    def test_acquire_increments_request_count(self):
        pool = _pool("tok1")
        pool.acquire()
        self.assertEqual(pool._buckets[0].request_count, 1)
        pool.acquire()
        self.assertEqual(pool._buckets[0].request_count, 2)

    def test_acquire_prefers_highest_remaining(self):
        pool = _pool("tok1", "tok2")
        pool._buckets[0].remaining = 100
        pool._buckets[1].remaining = 4000
        bucket = pool.acquire()
        self.assertEqual(bucket.token, "tok2")

    def test_acquire_skips_exhausted_token(self):
        pool = _pool("tok1", "tok2")
        pool._buckets[0].is_exhausted = True
        pool._buckets[0].remaining = 5000  # exhausted but high remaining
        pool._buckets[1].remaining = 10
        bucket = pool.acquire()
        self.assertEqual(bucket.token, "tok2")

    def test_acquire_resets_expired_bucket(self):
        pool = _pool("tok1")
        pool._buckets[0].is_exhausted = True
        pool._buckets[0].reset_epoch = time.time() - 10  # already past
        bucket = pool.acquire()
        self.assertFalse(pool._buckets[0].is_exhausted)
        self.assertEqual(bucket.token, "tok1")

    def test_acquire_sleeps_when_all_exhausted(self):
        pool = _pool("tok1", max_wait_s=900.0)
        future_reset = time.time() + 5.0
        pool._buckets[0].is_exhausted = True
        pool._buckets[0].remaining = 0
        pool._buckets[0].reset_epoch = future_reset

        sleep_calls = []

        def fake_sleep(s):
            sleep_calls.append(s)
            # Simulate reset by un-exhausting the bucket
            pool._buckets[0].reset_epoch = time.time() - 1

        with mock.patch("time.sleep", side_effect=fake_sleep):
            bucket = pool.acquire()

        self.assertTrue(len(sleep_calls) >= 1)
        self.assertEqual(bucket.token, "tok1")

    def test_acquire_raises_when_wait_exceeds_max(self):
        pool = _pool("tok1", max_wait_s=10.0)
        pool._buckets[0].is_exhausted = True
        pool._buckets[0].remaining = 0
        pool._buckets[0].reset_epoch = time.time() + 3600  # 1 hour

        with self.assertRaises(RateLimitExhaustedError):
            pool.acquire()


# ---------------------------------------------------------------------------
# TokenPool – update()
# ---------------------------------------------------------------------------

class TestTokenPoolUpdate(unittest.TestCase):

    def test_update_parses_remaining(self):
        pool = _pool("tok1")
        bucket = pool._buckets[0]
        pool.update(bucket, {"X-RateLimit-Remaining": "3000", "X-RateLimit-Limit": "5000", "X-RateLimit-Reset": "9999999999"})
        self.assertEqual(bucket.remaining, 3000)

    def test_update_parses_limit(self):
        pool = _pool("tok1")
        bucket = pool._buckets[0]
        pool.update(bucket, {"X-RateLimit-Remaining": "5000", "X-RateLimit-Limit": "5000", "X-RateLimit-Reset": "9999999999"})
        self.assertEqual(bucket.limit, 5000)

    def test_update_marks_exhausted_when_remaining_zero(self):
        pool = _pool("tok1")
        bucket = pool._buckets[0]
        future = str(int(time.time()) + 3600)
        pool.update(bucket, {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Reset": future,
        })
        self.assertTrue(bucket.is_exhausted)

    def test_update_does_not_exhaust_when_reset_in_past(self):
        pool = _pool("tok1")
        bucket = pool._buckets[0]
        past = str(int(time.time()) - 10)
        pool.update(bucket, {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Reset": past,
        })
        self.assertFalse(bucket.is_exhausted)

    def test_update_clears_exhausted_when_remaining_nonzero(self):
        pool = _pool("tok1")
        bucket = pool._buckets[0]
        bucket.is_exhausted = True
        pool.update(bucket, {
            "X-RateLimit-Remaining": "100",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Reset": "9999999999",
        })
        self.assertFalse(bucket.is_exhausted)

    def test_update_noop_on_none_bucket(self):
        pool = _pool("tok1")
        pool.update(None, {"X-RateLimit-Remaining": "0"})  # must not raise

    def test_update_tolerates_missing_headers(self):
        pool = _pool("tok1")
        bucket = pool._buckets[0]
        original_remaining = bucket.remaining
        pool.update(bucket, {})
        self.assertEqual(bucket.remaining, original_remaining)

    def test_update_tolerates_invalid_header_values(self):
        pool = _pool("tok1")
        bucket = pool._buckets[0]
        pool.update(bucket, {"X-RateLimit-Remaining": "not_a_number"})  # must not raise

    def test_update_retry_after_sets_synthetic_reset(self):
        """Retry-After header (secondary rate limit) forces exhaustion until the delay elapses."""
        pool = _pool("tok1")
        bucket = pool._buckets[0]
        now_approx = time.time()
        pool.update(bucket, {"Retry-After": "60"})
        self.assertTrue(bucket.is_exhausted)
        self.assertGreater(bucket.reset_epoch, now_approx + 58)  # ~60s from now

    def test_update_retry_after_does_not_shorten_existing_reset(self):
        """A small Retry-After never overrides a later reset_epoch already recorded."""
        pool = _pool("tok1")
        bucket = pool._buckets[0]
        far_future = time.time() + 3600
        bucket.reset_epoch = far_future
        pool.update(bucket, {"Retry-After": "1"})
        # reset_epoch should not be shortened to now+1
        self.assertAlmostEqual(bucket.reset_epoch, far_future, delta=5)


# ---------------------------------------------------------------------------
# TokenPool – stats()
# ---------------------------------------------------------------------------

class TestTokenPoolStats(unittest.TestCase):

    def test_stats_keys(self):
        pool = _pool("tok1", "tok2")
        s = pool.stats()
        self.assertIn("token_count", s)
        self.assertIn("total_requests", s)
        self.assertIn("total_remaining", s)
        self.assertIn("tokens", s)

    def test_stats_token_count(self):
        pool = _pool("tok1", "tok2")
        self.assertEqual(pool.stats()["token_count"], 2)

    def test_stats_total_remaining(self):
        pool = _pool("tok1", "tok2")
        pool._buckets[0].remaining = 3000
        pool._buckets[1].remaining = 2000
        self.assertEqual(pool.stats()["total_remaining"], 5000)

    def test_stats_total_requests(self):
        pool = _pool("tok1")
        pool.acquire()
        pool.acquire()
        self.assertEqual(pool.stats()["total_requests"], 2)

    def test_stats_masks_tokens(self):
        pool = _pool("ghp_ABCDEFGHIJ1234")
        tokens_info = pool.stats()["tokens"]
        self.assertEqual(len(tokens_info), 1)
        self.assertNotIn("ABCDEFGHIJ", tokens_info[0]["token"])


# ---------------------------------------------------------------------------
# TokenPool – thread safety
# ---------------------------------------------------------------------------

class TestTokenPoolThreadSafety(unittest.TestCase):

    def test_concurrent_acquires_do_not_corrupt_count(self):
        pool = _pool("tok1")
        n_threads = 20

        def worker():
            pool.acquire()

        threads = [threading.Thread(target=worker) for _ in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(pool._buckets[0].request_count, n_threads)

    def test_concurrent_updates_do_not_raise(self):
        pool = _pool("tok1")
        bucket = pool._buckets[0]
        errors = []

        def worker():
            try:
                pool.update(bucket, {"X-RateLimit-Remaining": "100", "X-RateLimit-Limit": "5000", "X-RateLimit-Reset": "9999999999"})
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# GitHubClient – basic request_json behaviour
# ---------------------------------------------------------------------------

class TestGitHubClientRequestJson(unittest.TestCase):

    def test_200_returns_json(self):
        gh = _gh("tok1")
        resp = _make_response(200, {"key": "value"})
        with mock.patch.object(gh.session, "request", return_value=resp):
            status, data, err = gh.request_json("GET", "/repos/a/b")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"key": "value"})
        self.assertEqual(err, "")

    def test_200_empty_body(self):
        gh = _gh("tok1")
        resp = _make_response(200)
        with mock.patch.object(gh.session, "request", return_value=resp):
            status, data, err = gh.request_json("GET", "/repos/a/b")
        self.assertEqual(status, 200)
        self.assertEqual(data, {})

    def test_404_does_not_retry(self):
        gh = _gh("tok1")
        resp = _make_response(404, {"message": "Not Found"})
        with mock.patch.object(gh.session, "request", return_value=resp) as m:
            status, _, _ = gh.request_json("GET", "/repos/missing/repo", max_retries=3)
        self.assertEqual(status, 404)
        self.assertEqual(m.call_count, 1)

    def test_401_does_not_retry(self):
        gh = _gh("tok1")
        resp = _make_response(401, {"message": "Unauthorized"})
        with mock.patch.object(gh.session, "request", return_value=resp) as m:
            status, _, _ = gh.request_json("GET", "/repos/a/b", max_retries=3)
        self.assertEqual(status, 401)
        self.assertEqual(m.call_count, 1)

    def test_5xx_retries_until_success(self):
        gh = _gh("tok1")
        err_resp = _make_response(503, text="Service Unavailable")
        ok_resp = _make_response(200, {"ok": True})
        with mock.patch.object(gh.session, "request", side_effect=[err_resp, ok_resp]):
            with mock.patch("time.sleep"):
                status, data, _ = gh.request_json("GET", "/repos/a/b", max_retries=2)
        self.assertEqual(status, 200)
        self.assertEqual(data, {"ok": True})

    def test_5xx_exhausted_retries_returns_error_status(self):
        gh = _gh("tok1")
        err_resp = _make_response(500, text="error")
        with mock.patch.object(gh.session, "request", return_value=err_resp) as m:
            with mock.patch("time.sleep"):
                status, _, _ = gh.request_json("GET", "/repos/a/b", max_retries=2)
        self.assertEqual(status, 500)
        self.assertEqual(m.call_count, 3)  # initial + 2 retries

    def test_network_error_retries_and_returns_zero(self):
        gh = _gh("tok1")
        with mock.patch.object(
            gh.session, "request",
            side_effect=requests.RequestException("timeout"),
        ) as m:
            with mock.patch("time.sleep"):
                status, _, err = gh.request_json("GET", "/repos/a/b", max_retries=2)
        self.assertEqual(status, 0)
        self.assertIn("network_error", err)
        self.assertEqual(m.call_count, 3)

    def test_authorization_header_injected(self):
        gh = _gh("ghp_mytoken")
        resp = _make_response(200, {})
        captured = []

        def fake_request(method, url, **kwargs):
            captured.append(kwargs.get("headers", {}))
            return resp

        with mock.patch.object(gh.session, "request", side_effect=fake_request):
            gh.request_json("GET", "/rate_limit")

        self.assertTrue(any("ghp_mytoken" in str(h) for h in captured))

    def test_no_auth_header_when_no_token(self):
        gh = GitHubClient(pool=TokenPool([]))
        resp = _make_response(200, {})
        captured = []

        def fake_request(method, url, **kwargs):
            captured.append(kwargs.get("headers", {}))
            return resp

        with mock.patch.object(gh.session, "request", side_effect=fake_request):
            gh.request_json("GET", "/rate_limit")

        self.assertFalse(any("Authorization" in h for h in captured))

    def test_request_json_with_headers_returns_headers(self):
        gh = _gh("tok1")
        resp = _make_response(200, {"ok": True}, headers={"Link": "<https://api.github.com/x?page=2>; rel=\"last\""})
        with mock.patch.object(gh.session, "request", return_value=resp):
            status, data, headers, err = gh.request_json_with_headers("GET", "/repos/a/b")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"ok": True})
        self.assertEqual(headers["Link"], "<https://api.github.com/x?page=2>; rel=\"last\"")
        self.assertEqual(err, "")

    def test_request_json_preserves_original_signature(self):
        gh = _gh("tok1")
        resp = _make_response(200, {"ok": True}, headers={"X-Test": "1"})
        with mock.patch.object(gh.session, "request", return_value=resp):
            result = gh.request_json("GET", "/repos/a/b")
        self.assertEqual(result, (200, {"ok": True}, ""))


# ---------------------------------------------------------------------------
# GitHubClient – token rotation on 403/429
# ---------------------------------------------------------------------------

class TestGitHubClientTokenRotation(unittest.TestCase):

    def test_403_triggers_token_rotation(self):
        """After a 403, the pool should be asked to acquire again (different token)."""
        pool = TokenPool(["tok1", "tok2"])
        gh = GitHubClient(pool=pool)

        # First call: 403 (marks tok1 exhausted); second call: success with tok2
        rate_resp = _make_response(403, {"message": "rate limited"}, headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
            "X-RateLimit-Limit": "5000",
        })
        ok_resp = _make_response(200, {"ok": True})

        with mock.patch.object(gh.session, "request", side_effect=[rate_resp, ok_resp]):
            status, data, _ = gh.request_json("GET", "/repos/a/b", max_retries=2)

        self.assertEqual(status, 200)
        # tok1 should be exhausted; tok2 should have been used
        self.assertTrue(pool._buckets[0].is_exhausted)
        self.assertGreater(pool._buckets[1].request_count, 0)

    def test_429_triggers_retry(self):
        pool = TokenPool(["tok1", "tok2"])
        gh = GitHubClient(pool=pool)

        rate_resp = _make_response(429, {"message": "too many"}, headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
            "X-RateLimit-Limit": "5000",
        })
        ok_resp = _make_response(200, {"ok": True})

        with mock.patch.object(gh.session, "request", side_effect=[rate_resp, ok_resp]):
            status, _, _ = gh.request_json("GET", "/repos/a/b", max_retries=2)

        self.assertEqual(status, 200)

    def test_all_tokens_exhausted_returns_rate_limit_error(self):
        pool = TokenPool(["tok1"], max_wait_s=5.0)
        gh = GitHubClient(pool=pool)

        # Exhaust the only token immediately
        pool._buckets[0].is_exhausted = True
        pool._buckets[0].remaining = 0
        pool._buckets[0].reset_epoch = time.time() + 3600  # far future

        status, _, err = gh.request_json("GET", "/repos/a/b", max_retries=1)
        self.assertEqual(status, 0)
        self.assertIn("rate_limit_exhausted", err)

    def test_single_token_backward_compat(self):
        """A pool with one token behaves like the old single-token client."""
        gh = _gh("ghp_single")
        resp = _make_response(200, {"name": "requests"})
        with mock.patch.object(gh.session, "request", return_value=resp):
            status, data, err = gh.request_json("GET", "/repos/psf/requests")
        self.assertEqual(status, 200)
        self.assertEqual(data, {"name": "requests"})
        self.assertEqual(err, "")

    def test_403_retries_are_not_bounded_by_max_retries(self):
        """Rate-limit responses never exhaust max_retries; they retry until success.

        This is the key guarantee: even if we get many 403s, the request eventually
        succeeds once a token becomes available. max_retries only applies to 5xx/network.
        """
        pool = TokenPool(["tok1", "tok2"])
        gh = GitHubClient(pool=pool)

        # Three consecutive 403s (both tokens exhausted), then success on the fourth call.
        rate_resp = _make_response(403, {"message": "rate limited"}, headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
            "X-RateLimit-Limit": "5000",
        })
        rate_resp2 = _make_response(403, {"message": "rate limited"}, headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
            "X-RateLimit-Limit": "5000",
        })
        rate_resp3 = _make_response(403, {"message": "rate limited"}, headers={
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + 3600),
            "X-RateLimit-Limit": "5000",
        })
        ok_resp = _make_response(200, {"ok": True})

        call_count = 0

        def fake_request(method, url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return rate_resp if call_count == 1 else (rate_resp2 if call_count == 2 else rate_resp3)
            return ok_resp

        # Simulate the pool waking up after sleeping (reset all tokens)
        def fake_acquire():
            b = pool._buckets[0]
            b.is_exhausted = False
            b.remaining = 100
            b.request_count += 1
            return b

        with mock.patch.object(gh.session, "request", side_effect=fake_request):
            with mock.patch.object(pool, "acquire", side_effect=fake_acquire):
                status, data, _ = gh.request_json("GET", "/repos/a/b", max_retries=2)

        # Should succeed despite 3 rate-limit failures (max_retries=2 would have stopped
        # a 5xx error after 3 attempts, but not a rate-limit retry).
        self.assertEqual(status, 200)
        self.assertEqual(call_count, 4)

    def test_pool_update_called_after_response(self):
        pool = TokenPool(["tok1"])
        gh = GitHubClient(pool=pool)
        resp = _make_response(200, {}, headers={
            "X-RateLimit-Remaining": "4000",
            "X-RateLimit-Limit": "5000",
            "X-RateLimit-Reset": "9999999999",
        })

        with mock.patch.object(gh.session, "request", return_value=resp):
            with mock.patch.object(pool, "update", wraps=pool.update) as mock_update:
                gh.request_json("GET", "/rate_limit")

        mock_update.assert_called_once()
        # After update, remaining should be 4000
        self.assertEqual(pool._buckets[0].remaining, 4000)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main()
