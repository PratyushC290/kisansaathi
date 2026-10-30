"""7-day farm outlook without any LLM: risk calendar + action windows, computed from live data and rules.

Used directly by the UI ("My Farm") and as evidence for the agent.
"""
from __future__ import annotations

from datetime import date

from .models import CropPlan, ToolResult
from .tools import crop_stage, rules

BLOCKING_SPRAY = {"no_spray_rain", "no_spray_wind", "heavy_rain"}
RAIN_DAY_MM = 2.5  # IMD rainy-day threshold
EFFECTIVE_RAIN = 0.8  # share of light/moderate rain that reaches the root zone (FAO-56 rule of thumb for effective rainfall)


def windows(days: list[dict], flags, stage: dict | None) -> dict:
    blocked = {(f.day.isoformat()) for f in flags if f.type in BLOCKING_SPRAY}
    enriched = rules.enrich_days(days)
    spray = [d for d in enriched if d["date"] not in blocked and d["spray_hour_count"] >= 3]
    best = max(spray[:5], key=lambda d: (d["spray_hour_count"], -d["rain_prob_pct"]), default=None) if spray else None

    out: dict = {"spray": None, "water": None, "harvest": None}
    if best:
        hrs = best["spray_hours"]
        out["spray"] = {"date": best["date"], "hours": f"{hrs[0]}–{hrs[-1]}", "calm_dry_hours": len(hrs),
                        "rain_prob_pct": best["rain_prob_pct"], "wind_max_kmh": best["wind_max_kmh"]}
    if stage and stage.get("kc"):
        kc = stage["kc"]
        etc = round(sum((d.get("et0_mm") or 0) * kc for d in days), 1)
        rain = round(sum(d.get("rain_mm") or 0 for d in days), 1)
        eff = round(rain * EFFECTIVE_RAIN, 1)
        out["water"] = {"days": len(days), "kc": kc, "et0_total_mm": round(sum(d.get("et0_mm") or 0 for d in days), 1),
                        "crop_water_need_mm": etc, "forecast_rain_mm": rain, "effective_rain_mm": eff,
                        "deficit_mm": round(max(0.0, etc - eff), 1)}
    if stage and stage.get("stage") == "late":
        dry = [d["date"] for d in days if (d.get("rain_mm") or 0) < RAIN_DAY_MM]
        out["harvest"] = {"dry_days": dry, "days_to_harvest": stage.get("days_to_harvest")}
    return out


def crop_outlook(forecast: ToolResult, plan: CropPlan, on: date | None = None) -> dict:
    st = crop_stage.get_stage(plan.name, plan.sowing_date, on)
    stage = st.data if st.ok else None
    if not forecast.ok:
        return {"crop": plan.name, "stage": stage, "flags": [], "windows": {}, "forecast_ok": False}
    days = forecast.data["days"]
    flags = rules.evaluate(days, plan.name, stage["stage"] if stage else None)
    return {"crop": plan.name, "stage": stage, "flags": flags, "windows": windows(days, flags, stage),
            "forecast_ok": True}
