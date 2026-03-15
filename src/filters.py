"""
filters.py

Shared filtering configuration and helpers used across the pipeline
(generate_dataset.py, analyze_metadata.py, etc.).

Filtering happens at two levels:
  1. Blacklist  — exact "owner/repo" strings read from a text file.
  2. Name filter — repos whose *name* portion (after the slash) contains any
                   of the words in REPO_NAME_FILTER_WORDS are excluded because
                   they are likely skill registries, templates, or tooling repos
                   rather than genuine end-user projects that happen to adopt
                   SKILL.md for their own workflows.
"""

from __future__ import annotations

import logging
from typing import List, Optional, Set

log = logging.getLogger(__name__)

# Words matched (case-insensitive) against the repo *name* portion (after the slash).
# Repos whose names contain any of these words are excluded from processing.
REPO_NAME_FILTER_WORDS: List[str] = [
    "skills", "skill", "registry", "awesome",
    "template", "boilerplate", "starter", "scaffold",
    "example", "dotfiles", "config", "setup", "bootstrap",
    "claw", "claude", "plugin", "tool",
]


def load_blacklist(path: str) -> Set[str]:
    """Load a blacklist file and return a set of 'owner/repo' strings to skip."""
    if not path or not __import__("os").path.exists(path):
        return set()
    blacklisted: Set[str] = set()
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            entry = line.strip()
            if entry and not entry.startswith("#"):
                blacklisted.add(entry)
    if blacklisted:
        log.info("Blacklist loaded: %d entries from %s", len(blacklisted), path)
    return blacklisted


def repo_name_contains_filter_word(repo: str, filter_words: List[str]) -> Optional[str]:
    """
    Return the first matched filter word if the repo *name* (part after the slash)
    contains any word from filter_words (case-insensitive), else return None.
    """
    name_part = repo.split("/", 1)[-1].lower()
    for word in filter_words:
        if word.lower() in name_part:
            return word
    return None


def is_repo_excluded(
    repo: str,
    blacklist: Set[str],
    filter_words: List[str],
) -> tuple[bool, str]:
    """
    Return (excluded, reason) for a given repo.

    excluded is True if the repo appears in the blacklist OR its name matches
    any filter word.  reason is a short human-readable explanation or "".
    """
    if repo in blacklist:
        return True, "blacklisted"
    matched = repo_name_contains_filter_word(repo, filter_words)
    if matched:
        return True, f"name_filter:{matched}"
    return False, ""
