"""LLM access with a fallback chain and quota protection.

  writing answers (tier="main"):  Gemini flash -> Gemini flash-lite -> Groq
  routing / judging (tier="fast"): Gemini flash-lite -> Groq

Free tiers are tight, so:
- clients never retry internally (max_retries=0): the chain itself is the retry, so a failure costs no duplicate call;
- a model that answers 429 (rate limit) / 503 (overloaded) / times out is put on cooldown and skipped
  instead of being hit again on every request.
"""
from __future__ import annotations

import json
import logging
import re
import time
import warnings
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from .config import settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)
# Overloads/timeouts tend to last, so pause those models longer; per-minute rate limits clear quickly.
COOLDOWN_S = {"rate": 90, "overloaded": 600, "timeout": 600, "auth": 3600, "other": 30}
_cooldown: dict[str, float] = {}  # model name -> unix time when it may be tried again


class LLMUnavailable(RuntimeError):
    pass


@lru_cache
def _clients() -> dict[str, object]:
    s = settings()
    out = {}
    if s.gemini_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        # Newer Gemini models fix their own sampling settings and warn about temperature; harmless.
        warnings.filterwarnings("ignore", message=".*uses fixed sampling defaults.*")
        for m in dict.fromkeys([s.gemini_model, s.gemini_fast_model]):
            # The big model gets a short leash: when it's overloaded it hangs, and lite/Groq answer in seconds.
            out[f"gemini:{m}"] = ChatGoogleGenerativeAI(model=m, google_api_key=s.gemini_api_key, temperature=0.2,
                                                        timeout=15 if m == s.gemini_model else 25, max_retries=0)
    if s.groq_api_key:
        from langchain_groq import ChatGroq
        out[f"groq:{s.groq_model}"] = ChatGroq(model=s.groq_model, api_key=s.groq_api_key, temperature=0.2,
                                               timeout=30, max_retries=0)
    return out


def chain(tier: str = "main") -> list[str]:
    s = settings()
    names = ([f"gemini:{s.gemini_model}"] if tier == "main" else []) + \
        [f"gemini:{s.gemini_fast_model}", f"groq:{s.groq_model}"]
    have = _clients()
    return [n for n in dict.fromkeys(names) if n in have]


def available() -> list[str]:
    return chain("main")


def cooling() -> dict[str, int]:
    """Models currently skipped, with seconds left (for the status panel)."""
    now = time.time()
    return {m: int(t - now) for m, t in _cooldown.items() if t > now}


def _kind(e: Exception) -> str:
    msg = f"{type(e).__name__} {e}".lower()
    if "429" in msg or "resource_exhausted" in msg or "rate" in msg and "limit" in msg or "quota" in msg:
        return "rate"
    if "503" in msg or "unavailable" in msg or "overloaded" in msg or "high demand" in msg:
        return "overloaded"
    if "timeout" in msg or "timed out" in msg or "deadline" in msg or "504" in msg:
        return "timeout"
    if "401" in msg or "403" in msg or "api key" in msg or "permission" in msg:
        return "auth"
    return "other"


def _text(msg) -> str:
    c = msg.content
    return (c if isinstance(c, str) else "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)).strip()


def chat(system: str, user: str, tier: str = "main") -> tuple[str, str]:
    errors = []
    now = time.time()
    for name in chain(tier):
        if _cooldown.get(name, 0) > now:
            errors.append(f"{name}: cooling down")
            continue
        try:
            return _text(_clients()[name].invoke([("system", system), ("human", user)])), name
        except Exception as e:  # noqa: BLE001 - any failure -> next provider
            kind = _kind(e)
            _cooldown[name] = time.time() + COOLDOWN_S[kind]
            log.warning("LLM %s failed (%s): %s", name, kind, str(e)[:160])
            errors.append(f"{name}: {kind}")
    raise LLMUnavailable("; ".join(errors) or "no LLM API key configured (GEMINI_API_KEY / GROQ_API_KEY)")


def _extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise ValueError("no JSON object in model output")
    return json.loads(m.group(1))


def chat_json(system: str, user: str, schema: type[T], tier: str = "main") -> tuple[T, str]:
    """Ask for JSON matching `schema`; validate with pydantic. One repair attempt if the JSON is invalid."""
    sys = (system + "\n\nReply with ONLY one JSON object matching this JSON schema, no prose:\n"
           + json.dumps(schema.model_json_schema()))
    text, name = chat(sys, user, tier)
    try:
        return schema.model_validate(_extract_json(text)), name
    except Exception as e:  # noqa: BLE001
        text, name = chat(sys, f"{user}\n\nYour previous reply was invalid ({e}). Return valid JSON only.", tier)
        return schema.model_validate(_extract_json(text)), name
