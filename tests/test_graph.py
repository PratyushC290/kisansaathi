"""Graph routing without network or LLM: tools are stubbed, so this tests orchestration & fallbacks."""
from datetime import date, datetime

import pytest

from kisansaathi import llm
from kisansaathi.agent import graph, nodes
from kisansaathi.models import CropPlan, FarmerProfile, ToolResult

FARMER = FarmerProfile(lat=20.14, lon=74.24, place="Lasalgaon", district="Nashik", state="Maharashtra",
                       language="hi", crops=[CropPlan(name="onion", sowing_date=date(2026, 9, 1))])


@pytest.fixture
def offline(monkeypatch, forecast_days):
    def no_llm(*a, **k):
        raise llm.LLMUnavailable("test: no LLM")
    monkeypatch.setattr(llm, "chat", no_llm)
    monkeypatch.setattr(nodes.weather, "get_forecast", lambda lat, lon: ToolResult(
        tool="weather", ok=True, data={"days": forecast_days}, source="test fixture", fetched_at=datetime.now()))
    monkeypatch.setattr(nodes.knowledge, "retrieve", lambda *a, **k: ToolResult(tool="knowledge", ok=False, error="offline"))
    monkeypatch.setattr(nodes.soil, "get_soil", lambda *a: ToolResult(tool="soil", ok=False, error="offline"))
    monkeypatch.setattr(graph.db, "log_query", lambda **k: None)


def test_llm_down_still_answers_from_data(offline):
    ans = graph.run(FARMER, "क्या इस हफ्ते प्याज पर छिड़काव करूं?", speak=False)
    assert ans.answer_local and ans.verified
    assert any("keyword fallback" in t for t in ans.trace)
    assert any("Data-only" in t for t in ans.trace)


def test_all_tools_down_never_crashes(offline, monkeypatch):
    monkeypatch.setattr(nodes.weather, "get_forecast", lambda *a: ToolResult(tool="weather", ok=False, error="down"))
    ans = graph.run(FARMER, "Should I spray onion?", speak=False)
    assert "1800-180-1551" in ans.answer_local


def test_empty_audio_asks_to_repeat(offline, monkeypatch):
    monkeypatch.setattr(nodes, "transcribe", lambda a, m: ("", "", "none"))
    ans = graph.run(FARMER, audio=b"\x00" * 100, speak=False)
    assert ans.clarification


def test_missing_crop_asks_which(offline):
    two = FARMER.model_copy(update={"crops": [*FARMER.crops, CropPlan(name="tomato", sowing_date=date(2026, 8, 1))]})
    ans = graph.run(two, "should I spray this week?", speak=False)
    assert ans.clarification and "Which crop" in ans.answer_local


def test_progress_callback_sees_each_step(offline):
    seen = []
    ans = graph.run(FARMER, "Should I spray onion?", speak=False, on_step=lambda tr: seen.append(len(tr)))
    assert len(seen) >= 4 and seen == sorted(seen) and seen[-1] == len(ans.trace)


def test_answer_language_follows_the_selected_language(offline):
    mr = FARMER.model_copy(update={"language": "mr"})
    assert graph.run(mr, "या आठवड्यात कांद्यावर फवारणी करू का?", speak=False).language == "mr"
    en = FARMER.model_copy(update={"language": "en"})
    assert graph.run(en, "Should I spray onion this week?", speak=False).language == "en"
