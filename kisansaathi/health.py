"""Live status of every upstream dependency (sidebar panel + GET /health). Cheap calls only."""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from . import llm
from .config import settings


def _probe(name: str, url: str, params: dict | None = None, timeout: float = 8) -> dict:
    t0 = time.time()
    try:
        r = httpx.get(url, params=params, timeout=timeout, headers={"User-Agent": settings().user_agent})
        ok = r.status_code < 400
        return {"name": name, "status": "ok" if ok else "down", "ms": int((time.time() - t0) * 1000),
                "detail": "" if ok else f"HTTP {r.status_code}"}
    except Exception as e:  # noqa: BLE001
        return {"name": name, "status": "down", "ms": int((time.time() - t0) * 1000), "detail": type(e).__name__}


def check_all() -> list[dict]:
    s = settings()
    probes = [
        ("Weather (Open-Meteo)", s.weather_url, {"latitude": 20, "longitude": 74, "daily": "temperature_2m_max", "forecast_days": 1}),
        ("Soil (SoilGrids)", s.soil_url, {"lon": 74.24, "lat": 20.14, "property": "phh2o", "depth": "0-5cm", "value": "mean"}),
        ("Geocoding", s.geocode_url, {"name": "Nashik", "count": 1}),
    ]
    with ThreadPoolExecutor(4) as ex:
        out = list(ex.map(lambda p: _probe(*p), probes))
    if s.data_gov_in_api_key:
        out.append(_probe("Mandi prices (data.gov.in)", s.mandi_url,
                          {"api-key": s.data_gov_in_api_key, "format": "json", "limit": 1}, timeout=15))
    else:
        out.append({"name": "Mandi prices (data.gov.in)", "status": "down", "ms": 0, "detail": "API key not set"})
    models = llm.available()
    out.append({"name": "AI model", "status": "ok" if len(models) == 2 else "degraded" if models else "down",
                "ms": 0, "detail": " → ".join(m.split(":")[0] for m in models) or "no key: data-only answers"})
    try:
        from .tools.knowledge import _collection
        n = _collection().count()
        out.append({"name": "Knowledge base", "status": "ok" if n else "down", "ms": 0, "detail": f"{n} passages"})
    except Exception as e:  # noqa: BLE001
        out.append({"name": "Knowledge base", "status": "down", "ms": 0, "detail": type(e).__name__})
    return out
