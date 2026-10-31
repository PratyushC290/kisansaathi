"""Deterministic risk engine: data/rules.yaml thresholds x live forecast x crop stage -> RiskFlags.

No LLM here on purpose: these flags are reproducible, testable and each carries its citation,
so the LLM only has to *explain* them, never invent them.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache

import yaml

from ..config import DATA_DIR
from ..models import RiskFlag

# A low-severity day rule that fires on most days is a weekly condition, not a daily alert: show it once.
COLLAPSE_LOW_IF_DAYS = 5
PER_DAY_TYPES = {"no_spray_rain", "no_spray_wind", "heavy_rain"}  # dashboard.windows() blocks spraying per day
SEV_RANK = {"low": 0, "medium": 1, "high": 2}


@lru_cache
def rules() -> list[dict]:
    return yaml.safe_load((DATA_DIR / "rules.yaml").read_text())["rules"]


@lru_cache
def sources() -> dict:
    docs = yaml.safe_load((DATA_DIR / "sources.yaml").read_text())["documents"]
    return {d["id"]: d for d in docs}


def citation_text(c: dict) -> str:
    d = sources().get(c["doc"], {})
    return f"{d.get('publisher', c['doc'])} — {d.get('title', '')}, PDF p.{c['page']}"


def _check(v, op, target) -> bool:
    if v is None:
        return False
    if op == "between":
        return target[0] <= v <= target[1]
    return {">": v > target, ">=": v >= target, "<": v < target, "<=": v <= target, "==": v == target}[op]


def enrich_days(days: list[dict]) -> list[dict]:
    """Add derived fields the rules use (mean temp, rain in next 24 h, number of spray-friendly hours)."""
    out = []
    for i, d in enumerate(days):
        e = dict(d)
        if d.get("tmax_c") is not None and d.get("tmin_c") is not None:
            e["tmean_c"] = round((d["tmax_c"] + d["tmin_c"]) / 2, 1)
        nxt = days[i + 1]["rain_mm"] if i + 1 < len(days) else 0
        e["rain_next24_mm"] = round((d.get("rain_mm") or 0) + (nxt or 0) * 0.5, 1)  # today + half of tomorrow
        e["spray_hour_count"] = len(d.get("spray_hours", []))
        out.append(e)
    return out


def evaluate(days: list[dict], crop: str | None, stage: str | None) -> list[RiskFlag]:
    days = enrich_days(days)
    agg = {"rain_total_mm": round(sum(d.get("rain_mm") or 0 for d in days), 1),
           "max_tmax_c": max((d["tmax_c"] for d in days if d.get("tmax_c") is not None), default=None),
           "min_tmin_c": min((d["tmin_c"] for d in days if d.get("tmin_c") is not None), default=None)}
    flags: list[RiskFlag] = []
    for r in rules():
        if "all" not in r["crops"] and crop not in r["crops"]:
            continue
        if r.get("stages") and stage not in r["stages"]:
            continue
        cites = r.get("citations", [])
        cite = "; ".join(citation_text(c) for c in cites)

        def flag(day: date, value, r=r, cite=cite):
            return RiskFlag(day=day, type=r["type"], severity=r["severity"], rule_id=r["id"],
                            value=value, citation=cite,
                            message=r["message"].format(value=value) + " " + r.get("action", ""))

        if r["scope"] == "stage":
            if days:
                flags.append(flag(date.fromisoformat(days[0]["date"]), None))
        elif r["scope"] == "forecast":
            if all(_check(agg.get(f), op, v) for f, op, v in r["all"]):
                flags.append(flag(date.fromisoformat(days[0]["date"]), agg.get(r["value_field"])))
        else:
            hits = [d for d in days if all(_check(d.get(f), op, v) for f, op, v in r["all"])]
            if r["severity"] == "low" and r["type"] not in PER_DAY_TYPES and len(hits) >= COLLAPSE_LOW_IF_DAYS:
                worst = max(hits, key=lambda d: d.get(r["value_field"]) or 0)
                f = flag(date.fromisoformat(hits[0]["date"]), worst.get(r["value_field"]))
                f.message += f" (expected on {len(hits)} of the next {len(days)} days)"
                flags.append(f)
            else:
                flags += [flag(date.fromisoformat(d["date"]), d.get(r["value_field"])) for d in hits]
    flags.sort(key=lambda f: (f.day, -SEV_RANK[f.severity]))
    return flags


def rule_detail(rule_id: str) -> dict | None:
    return next((r for r in rules() if r["id"] == rule_id), None)
