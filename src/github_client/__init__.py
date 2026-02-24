"""
github_client -- Multi-token GitHub API client package.

Public surface::

    from github_client import GitHubClient, TokenPool, TokenBucket, RateLimitExhaustedError
    from github_client import SearchThrottle
    from github_client.token_pool import load_tokens_from_env
"""

from .client import GitHubClient
from .token_pool import (
    RateLimitExhaustedError,
    SearchThrottle,
    TokenBucket,
    TokenPool,
    load_tokens_from_env,
)

__all__ = [
    "GitHubClient",
    "RateLimitExhaustedError",
    "SearchThrottle",
    "TokenBucket",
    "TokenPool",
    "load_tokens_from_env",
]
