"""Two caches on disk:
- fresh: short TTL, avoids hammering free APIs (and saves LLM/API quota during the demo).
- last_good: no TTL, used ONLY when the live call fails; results are flagged is_cached=True
  and keep their original fetch time, so the UI can say "last updated …". Never fake data.
"""
from __future__ import annotations

from functools import lru_cache

import diskcache

from .config import settings


@lru_cache
def _store() -> diskcache.Cache:
    return diskcache.Cache(str(settings().cache_dir))


def get_fresh(key: str):
    return _store().get(("fresh", key))


def set_fresh(key: str, value, ttl_s: int) -> None:
    _store().set(("fresh", key), value, expire=ttl_s)


def get_last_good(key: str):
    return _store().get(("last_good", key))


def set_last_good(key: str, value) -> None:
    _store().set(("last_good", key), value)
