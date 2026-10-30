"""Voice in and out for Indian languages, each with a fallback chain.

transcribe(audio) : Sarvam saarika STT -> Gemini audio understanding
tts(text, lang)   : Sarvam bulbul TTS  -> gTTS (Google Translate voices, free)
API field names drift; both providers are wrapped so a failure just moves to the next one.
"""
from __future__ import annotations

import base64
import io
import json
import logging
import re

import httpx

from .config import settings

log = logging.getLogger(__name__)
SARVAM = "https://api.sarvam.ai"
SUPPORTED = {"en", "hi", "mr", "ta", "te", "bn", "kn", "gu", "pa", "ml", "or"}


def _bcp47(lang: str) -> str:
    return f"{lang}-IN"


def _sarvam_stt(audio: bytes, mime: str) -> tuple[str, str]:
    r = httpx.post(f"{SARVAM}/speech-to-text", timeout=60,
                   headers={"api-subscription-key": settings().sarvam_api_key},
                   files={"file": ("question.wav", audio, mime)},
                   data={"model": "saarika:v2.5", "language_code": "unknown"})
    r.raise_for_status()
    j = r.json()
    lang = (j.get("language_code") or "hi-IN").split("-")[0]
    return j.get("transcript", "").strip(), lang


def _gemini_stt(audio: bytes, mime: str) -> tuple[str, str]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings().gemini_api_key)
    resp = client.models.generate_content(
        model=settings().gemini_model,
        contents=[types.Part.from_bytes(data=audio, mime_type=mime),
                  'Transcribe this farmer\'s spoken question exactly, in the language and script spoken. '
                  'Return JSON only: {"transcript": "...", "language": "<ISO 639-1 code>"}. '
                  'If there is no clear speech, return {"transcript": "", "language": ""}.'])
    m = re.search(r"\{.*\}", resp.text or "", re.S)
    j = json.loads(m.group(0)) if m else {}
    return j.get("transcript", "").strip(), (j.get("language") or "hi")[:2]


def transcribe(audio: bytes, mime: str = "audio/wav") -> tuple[str, str, str]:
    """Return (transcript, language, provider). Empty transcript means 'please repeat'."""
    s = settings()
    chain = []
    if s.sarvam_api_key:
        chain.append(("Sarvam saarika", _sarvam_stt))
    if s.gemini_api_key:
        chain.append(("Gemini audio", _gemini_stt))
    for name, fn in chain:
        try:
            text, lang = fn(audio, mime)
            if text:
                return text, lang if lang in SUPPORTED else "hi", name
        except Exception as e:  # noqa: BLE001
            log.warning("STT %s failed: %r", name, e)
    return "", "", "none"


def _sarvam_tts(text: str, lang: str) -> bytes:
    r = httpx.post(f"{SARVAM}/text-to-speech", timeout=60,
                   headers={"api-subscription-key": settings().sarvam_api_key},
                   json={"text": text[:1500], "target_language_code": _bcp47(lang), "model": "bulbul:v2",
                         "speaker": "anushka", "pace": 0.95})
    r.raise_for_status()
    return base64.b64decode(r.json()["audios"][0])


def _gtts(text: str, lang: str) -> bytes:
    from gtts import gTTS

    buf = io.BytesIO()
    gTTS(text=text, lang=lang if lang != "or" else "hi").write_to_fp(buf)
    return buf.getvalue()


def tts(text: str, lang: str) -> tuple[bytes | None, str]:
    """Return (audio bytes, mime). Strips citation markers like [S1] so they aren't read aloud."""
    clean = re.sub(r"\[S\d+(?:,\s*S\d+)*\]", "", text).replace("*", "")
    chain = []
    if settings().sarvam_api_key and lang != "en":
        chain.append((_sarvam_tts, "audio/wav"))
    chain.append((_gtts, "audio/mp3"))
    for fn, mime in chain:
        try:
            return fn(clean, lang), mime
        except Exception as e:  # noqa: BLE001
            log.warning("TTS %s failed: %r", fn.__name__, e)
    return None, ""
