"""Smoke tests against the real APIs.  Run: pytest -m live"""
import pytest

from kisansaathi.config import settings
from kisansaathi.tools import geocode, mandi, soil, weather

pytestmark = pytest.mark.live


def test_weather():
    r = weather.get_forecast(20.14, 74.24)
    assert r.ok and len(r.data["days"]) == 7 and r.fetched_at


def test_geocode_village():
    r = geocode.search("Lasalgaon")
    assert r.ok and r.data[0]["state"] == "Maharashtra"


def test_soil_with_urban_fallback():
    r = soil.get_soil(30.90, 75.85)  # Ludhiana city: falls back to nearby farmland
    assert r.ok and 4 < r.data["ph"] < 10


@pytest.mark.skipif(not settings().data_gov_in_api_key, reason="no data.gov.in key")
def test_mandi():
    r = mandi.get_prices("Onion", "Maharashtra", "Nashik")
    assert r.ok and r.data["markets"][0]["modal_price"] > 0
