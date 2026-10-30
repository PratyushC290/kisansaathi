"""Topsoil properties from ISRIC SoilGrids v2 (250 m global soil maps, free).

SoilGrids stores integers scaled by `d_factor` (e.g. pH*10) — we divide by it.
Built-up areas are masked (null), so if the exact point is empty we try points ~2–5 km away.
"""
from __future__ import annotations

from ..config import settings
from ..http import cached_fetch
from ..models import ToolResult

PROPS = ["phh2o", "soc", "clay", "sand", "silt", "nitrogen", "cec"]
OFFSETS = [(0, 0), (0.02, 0), (-0.02, 0), (0, 0.02), (0, -0.02), (0.045, 0.045), (-0.045, -0.045)]


def _texture(clay, sand, silt):
    # Simplified USDA texture triangle, enough for advice ("heavy clay soil holds water").
    if clay is None or sand is None:
        return None
    if clay >= 40:
        return "clay"
    if sand >= 70:
        return "sandy"
    if clay >= 27:
        return "clay loam"
    if (silt or 0) >= 50:
        return "silt loam"
    return "loam"


def _parse(j):
    out = {}
    for layer in j["properties"]["layers"]:
        f = layer["unit_measure"]["d_factor"]
        unit = layer["unit_measure"]["target_units"]
        for d in layer["depths"]:
            if d["label"] == "0-5cm":
                v = d["values"]["mean"]
                out[layer["name"]] = {"value": None if v is None else round(v / f, 2), "unit": unit}
    if all(v["value"] is None for v in out.values()):
        raise ValueError("no soil data at this point (built-up or water)")
    g = lambda k: out.get(k, {}).get("value")  # noqa: E731
    return {"depth": "0-5 cm", "ph": g("phh2o"), "organic_carbon_g_per_kg": g("soc"),
            "clay_pct": g("clay"), "sand_pct": g("sand"), "silt_pct": g("silt"),
            "nitrogen_g_per_kg": g("nitrogen"), "cec_cmol_per_kg": g("cec"),
            "texture": _texture(g("clay"), g("sand"), g("silt"))}


def get_soil(lat: float, lon: float) -> ToolResult:
    last = None
    for dlat, dlon in OFFSETS:
        la, lo = round(lat + dlat, 3), round(lon + dlon, 3)
        params = [("lon", lo), ("lat", la)] + [("property", p) for p in PROPS] + [("depth", "0-5cm"), ("value", "mean")]
        res = cached_fetch("soil", "ISRIC SoilGrids v2", settings().soil_url, params, _parse,
                           ttl_s=30 * 86400, timeout=20)
        if res.ok:
            if (dlat, dlon) != (0, 0):
                res.data["note"] = f"nearest farmland sample at {la}, {lo}"
            return res
        last = res
        if "no soil data" not in res.error:
            break  # upstream down, not a masked pixel — don't hammer it
    return last
