import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).parent / "fixtures"


def pytest_configure(config):
    config.addinivalue_line("markers", "live: hits real external APIs (run with -m live)")


@pytest.fixture
def forecast_days():
    """A recorded Open-Meteo response (normalised), used ONLY in tests."""
    return json.loads((FIX / "forecast_lasalgaon.json").read_text())["days"]
