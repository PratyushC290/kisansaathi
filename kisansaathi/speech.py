"""Voice in and out for Indian languages, each with a fallback chain.

transcribe(audio) : Sarvam saaras:v4 STT -> Gemini audio understanding
tts(text, lang)   : Sarvam bulbul:v3 TTS -> gTTS (Google Translate voices, free)
Request fields follow docs.sarvam.ai (checked 31 Oct 2026); each provider is wrapped so a failure
just moves to the next one.
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
    return "od-IN" if lang == "or" else f"{lang}-IN"  # Sarvam uses od-IN for Odia


def _sarvam_stt(audio: bytes, mime: str) -> tuple[str, str]:
    r = httpx.post(f"{SARVAM}/speech-to-text", timeout=60,
                   headers={"api-subscription-key": settings().sarvam_api_key},
                   files={"file": ("question.wav", audio, mime)},
                   data={"model": "saaras:v4", "language_code": "unknown"})  # unknown = auto-detect
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


WHISPER_LANG = {"hindi": "hi", "marathi": "mr", "english": "en", "tamil": "ta", "telugu": "te", "bengali": "bn",
                "kannada": "kn", "gujarati": "gu", "punjabi": "pa", "malayalam": "ml", "odia": "or", "urdu": "hi"}


def _groq_stt(audio: bytes, mime: str) -> tuple[str, str]:
    """Groq-hosted Whisper (free tier) — last voice fallback."""
    r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions", timeout=60,
                   headers={"Authorization": f"Bearer {settings().groq_api_key}"},
                   files={"file": ("question.wav", audio, mime)},
                   data={"model": "whisper-large-v3-turbo", "response_format": "verbose_json"})
    r.raise_for_status()
    j = r.json()
    return j.get("text", "").strip(), WHISPER_LANG.get((j.get("language") or "").lower(), "hi")


def transcribe(audio: bytes, mime: str = "audio/wav") -> tuple[str, str, str]:
    """Return (transcript, language, provider). Empty transcript means 'please repeat'."""
    s = settings()
    chain = []
    if s.sarvam_api_key:
        chain.append(("Sarvam saarika", _sarvam_stt))
    if s.gemini_api_key:
        chain.append(("Gemini audio", _gemini_stt))
    if s.groq_api_key:
        chain.append(("Groq Whisper", _groq_stt))
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
                   json={"text": text[:2500], "language_code": _bcp47(lang), "model": "bulbul:v3",
                         "speaker": "priya", "pace": 0.95})
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
