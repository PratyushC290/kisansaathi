"""LLM access: Gemini (primary, free tier) with automatic fallback to Groq (Llama) on 429/5xx/timeout/missing key.

Two helpers used by the agent:
  chat(system, user)              -> (text, model_name)
  chat_json(system, user, Schema) -> (pydantic object, model_name)
"""
from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from typing import TypeVar

from pydantic import BaseModel

from .config import settings

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(RuntimeError):
    pass


@lru_cache
def _models() -> list[tuple[str, object]]:
    s = settings()
    out = []
    if s.gemini_api_key:
        from langchain_google_genai import ChatGoogleGenerativeAI
        out.append((f"gemini:{s.gemini_model}", ChatGoogleGenerativeAI(
            model=s.gemini_model, google_api_key=s.gemini_api_key, temperature=0.2, timeout=40, max_retries=1)))
    if s.groq_api_key:
        from langchain_groq import ChatGroq
        out.append((f"groq:{s.groq_model}", ChatGroq(
            model=s.groq_model, api_key=s.groq_api_key, temperature=0.2, timeout=40, max_retries=1)))
    return out


def available() -> list[str]:
    return [name for name, _ in _models()]


def chat(system: str, user: str) -> tuple[str, str]:
    errors = []
    for name, model in _models():
        try:
            msg = model.invoke([("system", system), ("human", user)])
            text = msg.content if isinstance(msg.content, str) else "".join(
                p.get("text", "") if isinstance(p, dict) else str(p) for p in msg.content)
            return text.strip(), name
        except Exception as e:  # noqa: BLE001 - any failure -> try the next provider
            log.warning("LLM %s failed: %r", name, e)
            errors.append(f"{name}: {type(e).__name__}")
    raise LLMUnavailable("; ".join(errors) or "no LLM API key configured (GEMINI_API_KEY / GROQ_API_KEY)")


def _extract_json(text: str) -> dict:
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S) or re.search(r"(\{.*\})", text, re.S)
    if not m:
        raise ValueError("no JSON object in model output")
    return json.loads(m.group(1))


def chat_json(system: str, user: str, schema: type[T]) -> tuple[T, str]:
    """Ask for JSON matching `schema`; validate with pydantic. Retries once with the error fed back."""
    sys = (system + "\n\nReply with ONLY one JSON object matching this JSON schema, no prose:\n"
           + json.dumps(schema.model_json_schema()))
    text, name = chat(sys, user)
    try:
        return schema.model_validate(_extract_json(text)), name
    except Exception as e:  # noqa: BLE001
        text, name = chat(sys, f"{user}\n\nYour previous reply was invalid ({e}). Return valid JSON only.")
        return schema.model_validate(_extract_json(text)), name
