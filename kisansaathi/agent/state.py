"""Shared state that flows through the LangGraph nodes."""
from __future__ import annotations

from typing import Any, TypedDict

from pydantic import BaseModel, Field

from ..models import Citation, FarmerProfile, RiskFlag, ToolResult

INTENTS = ["spray_timing", "irrigation", "sell_or_hold", "harvest_timing", "sowing", "pest_disease",
           "fertilizer", "weather", "soil", "general"]


class Understanding(BaseModel):
    """Structured output of the `understand` node."""
    question_en: str = Field(description="The farmer's question translated to plain English")
    language: str = Field(description="ISO 639-1 code of the language the farmer used, e.g. hi, mr, en")
    intents: list[str] = Field(description=f"One or more of {INTENTS}")
    crop: str | None = Field(default=None, description="Crop key the question is about, if any")
    in_scope: bool = Field(description="False if not about farming/crops/weather/markets (e.g. loans, medical, politics)")
    clarification: str | None = Field(default=None, description="If essential info is missing, a short question back to the farmer in their language; else null")


class Draft(BaseModel):
    answer_local: str = Field(description="Answer in the farmer's language, with [S#] citations")
    answer_en: str = Field(description="Same answer in English, with the same [S#] citations")


class Judgement(BaseModel):
    supported: bool
    unsupported_claims: list[str] = Field(default_factory=list)


class AgentState(TypedDict, total=False):
    farmer: FarmerProfile
    audio: bytes | None
    audio_mime: str
    question_raw: str
    language: str
    question_en: str
    intents: list[str]
    crop: str | None
    in_scope: bool
    clarification: str | None
    plan: list[str]
    evidence: dict[str, ToolResult]
    pack: list[dict[str, Any]]      # numbered evidence [{id, kind, label, content, citation}]
    risks: list[RiskFlag]
    draft: Draft | None
    problems: list[str]             # verifier feedback for the next synthesis attempt
    verified: bool
    attempts: int
    answer_local: str
    answer_en: str
    citations: list[Citation]
    skip_speech: bool
    audio_out: bytes | None
    audio_out_mime: str
    llm_used: list[str]
    trace: list[str]
