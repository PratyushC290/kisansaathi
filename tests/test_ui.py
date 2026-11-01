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
