"""Typed data passed between tools, the agent and the UI."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

LANGUAGES = {
    "en": "English", "hi": "हिन्दी", "mr": "मराठी", "ta": "தமிழ்", "te": "తెలుగు",
    "bn": "বাংলা", "kn": "ಕನ್ನಡ", "gu": "ગુજરાતી", "pa": "ਪੰਜਾਬੀ",
}


class CropPlan(BaseModel):
    name: str  # key into data/crops.yaml, e.g. "onion"
    sowing_date: date


class FarmerProfile(BaseModel):
    id: int | None = None
    name: str = ""
    lat: float
    lon: float
    place: str = ""  # village / town as the farmer typed it
    district: str = ""
    state: str = ""
    language: str = "hi"
    crops: list[CropPlan] = Field(default_factory=list)


class ToolResult(BaseModel):
    """Every tool returns this, so the agent always knows where a number came from and how fresh it is."""
    tool: str
    ok: bool
    data: Any = None
    source: str = ""  # human readable, e.g. "Open-Meteo forecast API"
    url: str = ""
    fetched_at: datetime | None = None
    is_cached: bool = False  # True when served from last-good cache after a live failure
    error: str = ""


class RiskFlag(BaseModel):
    day: date
    type: str  # heavy_rain, heat_stress, frost, high_wind, fungal_humidity, dry_soil, ...
    severity: Literal["low", "medium", "high"]
    message: str
    rule_id: str
    value: float | None = None
    threshold: float | None = None
    citation: str = ""  # "doc_id p.N" from rules.yaml


class Citation(BaseModel):
    id: str  # "S1"
    label: str
    url: str = ""
    detail: str = ""  # fetch time / page number
    is_cached: bool = False


class Answer(BaseModel):
    answer_local: str
    answer_en: str = ""
    language: str = "hi"
    citations: list[Citation] = Field(default_factory=list)
    risks: list[RiskFlag] = Field(default_factory=list)
    verified: bool = False
    trace: list[str] = Field(default_factory=list)
    audio_bytes: bytes | None = None
    clarification: bool = False
    latency_ms: int = 0
    llm_used: str = ""
