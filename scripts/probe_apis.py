"""Check every live data source for one demo location and print shape + timing.

Run before a demo:  python scripts/probe_apis.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kisansaathi import llm  # noqa: E402
from kisansaathi.tools import geocode, knowledge, mandi, soil, weather  # noqa: E402

LAT, LON = 20.14, 74.24  # Lasalgaon, Nashik (Asia's largest onion market)


def probe(name, fn):
    t0 = time.time()
    try:
        r = fn()
        ok = getattr(r, "ok", True)
        info = r.error if not ok else str(r.data)[:110] if hasattr(r, "data") else str(r)[:110]
    except Exception as e:  # noqa: BLE001
        ok, info = False, repr(e)
    print(f"{'🟢' if ok else '🔴'} {name:22s} {time.time() - t0:5.1f}s  {info}")
    return ok


results = [
    probe("weather", lambda: weather.get_forecast(LAT, LON)),
    probe("geocode", lambda: geocode.search("Lasalgaon")),
    probe("reverse geocode", lambda: geocode.reverse(LAT, LON)),
    probe("soil", lambda: soil.get_soil(LAT, LON)),
    probe("mandi", lambda: mandi.get_prices("Onion", "Maharashtra", "Nashik")),
    probe("knowledge", lambda: knowledge.retrieve("when to stop irrigation in onion", "onion", 2)),
    probe("llm", lambda: llm.chat("Reply with the single word OK.", "ping")),
]
print(f"\n{sum(results)}/{len(results)} sources OK")
sys.exit(0 if all(results) else 1)
