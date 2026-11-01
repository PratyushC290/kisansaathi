"""New-farmer onboarding in the Streamlit UI (regression: picking a searched place crashed because our session
key 'loc' collided with the geolocation widget's key)."""
from streamlit.testing.v1 import AppTest

from kisansaathi import db, health
from kisansaathi.models import ToolResult
from kisansaathi.tools import geocode

PLACE = {"name": "Lasalgaon", "lat": 20.14, "lon": 74.24, "district": "Nashik", "state": "Maharashtra"}


def test_searching_and_picking_a_place_works(monkeypatch):
    monkeypatch.setattr(db, "list_farmers", lambda: [])
    monkeypatch.setattr(db, "usage_stats", lambda: {"queries": 0, "farmers": 0})
    monkeypatch.setattr(health, "check_all", lambda: [])
    monkeypatch.setattr(geocode, "search", lambda q: ToolResult(tool="geocode", ok=True, data=[PLACE]))
    at = AppTest.from_file("../app/ui.py", default_timeout=60).run()
    assert not at.exception
    at.text_input[1].set_value("Lasalgaon")
    next(b for b in at.button if "🔎" in b.label).click()
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert any("Lasalgaon" in s.value for s in at.success)


def test_sidebar_language_drives_examples_and_answer_language(monkeypatch):
    from datetime import date

    from kisansaathi.models import CropPlan, FarmerProfile, ToolResult
    from kisansaathi.tools import mandi, soil, weather

    farmer = FarmerProfile(id=1, lat=20.14, lon=74.24, place="Lasalgaon", district="Nashik", state="Maharashtra",
                           language="hi", crops=[CropPlan(name="onion", sowing_date=date(2026, 9, 1))])
    down = ToolResult(tool="x", ok=False, error="test")
    for mod, fn in ((weather, "get_forecast"), (soil, "get_soil"), (mandi, "get_prices"), (mandi, "get_trend")):
        monkeypatch.setattr(mod, fn, lambda *a, **k: down)
    monkeypatch.setattr(db, "list_farmers", lambda: [farmer])
    monkeypatch.setattr(db, "usage_stats", lambda: {"queries": 0, "farmers": 1})
    monkeypatch.setattr(db, "price_history", lambda *a, **k: [])
    monkeypatch.setattr(health, "check_all", lambda: [])
    at = AppTest.from_file("../app/ui.py", default_timeout=90).run()
    assert not at.exception, [e.value for e in at.exception]
    sidebar = next(b for b in at.selectbox if "Language" in b.label)
    sidebar.set_value("en").run()
    assert not at.exception, [e.value for e in at.exception]
    shown = " ".join(str(getattr(w, "options", "")) for w in at.get("pills"))
    assert "Should I spray" in shown and "छिड़काव" not in shown
