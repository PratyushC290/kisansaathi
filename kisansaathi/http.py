"""One place for outbound HTTP: timeouts, retries with backoff, cache + last-good fallback.

Tools call `cached_fetch(...)`, which always returns a ToolResult and never raises,
so a broken upstream can't crash the agent or the demo.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from . import cache
from .config import settings
from .models import ToolResult

log = logging.getLogger(__name__)
IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def _retryable(e: BaseException) -> bool:
    # Retry network errors and 429/5xx; a 4xx like 400/401 won't fix itself.
    if isinstance(e, httpx.HTTPStatusError):
        return e.response.status_code == 429 or e.response.status_code >= 500
    return isinstance(e, (httpx.TransportError, httpx.TimeoutException))


@retry(retry=retry_if_exception(_retryable), stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=0.6, max=4), reraise=True)
def get_json(url: str, params: Any = None, timeout: float = 15.0) -> Any:
    with httpx.Client(timeout=timeout, headers={"User-Agent": settings().user_agent},
                      follow_redirects=True) as c:
        r = c.get(url, params=params)
        r.raise_for_status()
        return r.json()


def _key(tool: str, url: str, params: Any) -> str:
    raw = json.dumps([tool, url, params], sort_keys=True, default=str)
    return tool + ":" + hashlib.sha1(raw.encode()).hexdigest()[:16]


def cached_fetch(tool: str, source: str, url: str, params: Any,
                 parse: Callable[[Any], Any], ttl_s: int, timeout: float = 15.0,
                 cache_key: str | None = None) -> ToolResult:
    """Fetch -> parse -> ToolResult. Order: fresh cache, live call, last-good cache, error."""
    key = cache_key or _key(tool, url, params)
    hit = cache.get_fresh(key)
    if hit is not None:
        return ToolResult(**hit)
    try:
        data = parse(get_json(url, params, timeout))
        res = ToolResult(tool=tool, ok=True, data=data, source=source, url=url, fetched_at=now_ist())
        dumped = res.model_dump(mode="json")
        cache.set_fresh(key, dumped, ttl_s)
        cache.set_last_good(key, dumped)
        return res
    except Exception as e:  # noqa: BLE001 - we deliberately convert every failure into data
        # ValueError = upstream answered but had no usable data (e.g. masked soil pixel): expected, not alarming.
        (log.info if isinstance(e, ValueError) else log.warning)("%s failed: %r", tool, e)
        err = f"{type(e).__name__}: {str(e)[:200]}"
        old = cache.get_last_good(key)
        if old is not None:
            res = ToolResult(**old)
            res.is_cached, res.error = True, f"live call failed ({err}); showing last saved data"
            return res
        return ToolResult(tool=tool, ok=False, source=source, url=url, error=err)
