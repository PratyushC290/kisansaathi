"""Mandi (market) prices from Agmarknet via data.gov.in, plus trends from OUR stored history.

data.gov.in only serves the latest day, so `jobs/snapshot_prices.py` saves each day's rows to
the price_history table; trends are computed from those real snapshots (never synthesised).
Prices are ₹ per quintal (100 kg).

Note: data.gov.in's commodity filter is a loose text match ("Wheat" also returns "Wheat Atta"), so rows are
always re-filtered to exact commodity names here.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from statistics import mean

from .. import db
from ..config import settings
from ..http import cached_fetch, get_json
from ..models import ToolResult

SOURCE = "Agmarknet daily mandi prices (data.gov.in)"
PAGE = 1000


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _rows(j, keep: set[str] | None = None) -> list[dict]:
    """Normalise API records; if `keep` is given, only rows whose commodity is exactly one of those names."""
    out = []
    for r in j.get("records", []):
        if keep and str(r.get("commodity") or r.get("Commodity") or "").strip() not in keep:
            continue
        modal = _num(r.get("modal_price") or r.get("Modal_Price") or r.get("Modal_x0020_Price"))
        if not modal:
            continue
        raw_date = r.get("arrival_date") or r.get("Arrival_Date") or ""
        try:
            d = datetime.strptime(raw_date, "%d/%m/%Y").date()
        except ValueError:
            continue
        g = lambda k, r=r: str(r.get(k) or r.get(k.capitalize()) or "").strip()  # noqa: E731 - names have stray spaces
        out.append({"date": d, "state": g("state"), "district": g("district"), "market": g("market"),
                    "commodity": g("commodity"), "variety": g("variety"), "grade": g("grade"),
                    "min_price": _num(r.get("min_price") or r.get("Min_Price") or r.get("Min_x0020_Price")) or modal,
                    "max_price": _num(r.get("max_price") or r.get("Max_Price") or r.get("Max_x0020_Price")) or modal,
                    "modal_price": modal})
    return out


def fetch_all(commodity: str | None = None, state: str | None = None, keep: set[str] | None = None) -> list[dict]:
    """Page through today's full dataset (used by the snapshot job). Raises on failure.
    Pauses between pages: data.gov.in silently returns empty pages when called in quick bursts."""
    s = settings()
    rows, offset = [], 0
    while True:
        params = {"api-key": s.data_gov_in_api_key, "format": "json", "limit": PAGE, "offset": offset}
        if state:
            params["filters[state.keyword]"] = state
        if commodity:
            params["filters[commodity]"] = commodity
        j = get_json(s.mandi_url, params, timeout=40)
        rows += _rows(j, keep)
        if len(j.get("records", [])) < PAGE:
            return rows
        offset += PAGE
        time.sleep(1.5)


def get_prices(commodity: str, state: str, district: str = "") -> ToolResult:
    """Today's prices for one commodity in the farmer's state, nearest (same-district) markets first."""
    s = settings()
    if not s.data_gov_in_api_key:
        return ToolResult(tool="mandi", ok=False, source=SOURCE, error="DATA_GOV_IN_API_KEY not configured")

    def parse(j):
        rows = _rows(j, {commodity})
        if not rows:
            raise ValueError(f"no {commodity} prices reported in {state} today")
        try:  # store what we saw — every live fetch grows our own history
            db.upsert_prices(rows)
        except Exception:
            pass
        local = [r for r in rows if district and r["district"].lower() == district.lower()]
        rows.sort(key=lambda r: (r not in local, -r["modal_price"]))
        modals = [r["modal_price"] for r in rows]
        return {"commodity": commodity, "state": state, "district": district, "unit": "₹/quintal",
                "scope": "district" if local else "state",
                "scope_note": "" if local or not district else
                f"No {commodity} market in {district} reported today; showing other {state} markets.",
                "arrival_date": max(r["date"] for r in rows).isoformat(),
                "state_avg_modal": round(mean(modals)), "state_max_modal": max(modals),
                "state_min_modal": min(modals), "n_markets": len(rows),
                "markets": [{**r, "date": r["date"].isoformat()} for r in rows[:15]]}

    params = {"api-key": s.data_gov_in_api_key, "format": "json", "limit": PAGE,
              "filters[state.keyword]": state, "filters[commodity]": commodity}
    return cached_fetch("mandi", SOURCE, s.mandi_url, params, parse, ttl_s=3600, timeout=40,
                        cache_key=f"mandi:{commodity}:{state}:{district}".lower())


def get_trend(commodity: str, state: str, market: str | None = None, days: int = 30) -> ToolResult:
    """Price trend from our own saved daily snapshots. Honest about how much history exists."""
    try:
        hist = db.price_history(commodity, state, date.today() - timedelta(days=days))
    except Exception as e:  # noqa: BLE001
        return ToolResult(tool="mandi_trend", ok=False, source="KisanSaathi price history DB", error=str(e))
    if market:
        hist = [h for h in hist if h.market.lower() == market.lower()] or hist
    by_day: dict[date, list[float]] = {}
    for h in hist:
        by_day.setdefault(h.date, []).append(h.modal_price)
    series = [{"date": d.isoformat(), "avg_modal": round(mean(v)), "n_markets": len(v)} for d, v in sorted(by_day.items())]
    data = {"commodity": commodity, "state": state, "market": market, "series": series,
            "history_days": len(series), "since": series[0]["date"] if series else None}
    if len(series) >= 3:
        first = mean(p["avg_modal"] for p in series[: max(1, len(series) // 3)])
        last = mean(p["avg_modal"] for p in series[-max(1, len(series) // 3):])
        data["change_pct"] = round((last - first) / first * 100, 1)
        data["direction"] = "rising" if data["change_pct"] > 3 else "falling" if data["change_pct"] < -3 else "flat"
    else:
        data["direction"] = "insufficient_history"
    return ToolResult(tool="mandi_trend", ok=True, data=data, source="KisanSaathi price history (daily Agmarknet snapshots)",
                      fetched_at=datetime.now())
