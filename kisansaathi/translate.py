"""Translate the rule messages shown on My Farm (one batched, cached LLM call per language).

Rule texts are written in English with cited thresholds; the translation must keep every number and
falls back to the English original otherwise, so a translation can never change a threshold.
"""
from __future__ import annotations

import hashlib
import logging

from pydantic import BaseModel

from . import cache, llm
from .agent.verify import numbers_in
from .models import LANGUAGES

log = logging.getLogger(__name__)
TTL_S = 90 * 24 * 3600


class _Batch(BaseModel):
    translations: list[str]


def _key(lang: str, text: str) -> str:
    return f"tr:{lang}:{hashlib.sha1(text.encode()).hexdigest()}"


def translate_all(texts: list[str], lang: str) -> dict[str, str]:
    """{english: translated}; missing entries mean 'show the English'."""
    uniq = list(dict.fromkeys(texts))
    if lang == "en" or lang not in LANGUAGES:
        return {}
    out = {x: v for x in uniq if (v := cache.get_fresh(_key(lang, x)))}
    todo = [x for x in uniq if x not in out]
    if not todo or not llm.available():
        return out
    try:
        res, _ = llm.chat_json(
            f"Translate each farm-advisory sentence into {LANGUAGES[lang]} for a smallholder farmer. Keep every number, "
            "unit and °C exactly as written; do not add or drop advice. Return the same number of items in the same order.",
            "\n".join(f"{i + 1}. {x}" for i, x in enumerate(todo)), _Batch, tier="fast")
    except Exception as e:  # noqa: BLE001 - translation is optional
        log.info("translation skipped: %s", str(e)[:120])
        return out
    if len(res.translations) != len(todo):
        return out
    for src, tr in zip(todo, res.translations, strict=True):
        if sorted(numbers_in(src)) == sorted(numbers_in(tr)):
            out[src] = tr
            cache.set_fresh(_key(lang, src), tr, TTL_S)
    return out
