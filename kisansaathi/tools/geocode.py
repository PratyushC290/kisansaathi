"""Place name <-> coordinates. Open-Meteo geocoding first, Nominatim (OSM) as fallback."""
from __future__ import annotations

from ..config import settings
from ..http import cached_fetch
from ..models import ToolResult

DAY = 86400


def _om_parse(j):
    return [{"name": r["name"], "lat": r["latitude"], "lon": r["longitude"],
             "district": r.get("admin2", ""), "state": r.get("admin1", "")}
            for r in j.get("results", []) if r.get("country_code") == "IN"]


def _nom_parse(j):
    out = []
    for r in j:
        a = r.get("address", {})
        out.append({"name": r.get("name") or r.get("display_name", "").split(",")[0],
                    "lat": float(r["lat"]), "lon": float(r["lon"]),
                    "district": a.get("state_district") or a.get("county", ""),
                    "state": a.get("state", "")})
    return out


def search(place: str) -> ToolResult:
    """Return candidate locations in India for a village/town/district name."""
    s = settings()
    res = cached_fetch("geocode", "Open-Meteo Geocoding", s.geocode_url,
                       {"name": place, "country_code": "IN", "count": 5, "language": "en"},
                       _om_parse, ttl_s=30 * DAY)
    if res.ok and res.data:
        return res
    # Small villages are often missing from GeoNames; OSM usually has them.
    return cached_fetch("geocode", "OpenStreetMap Nominatim", f"{s.nominatim_url}/search",
                        {"q": place, "format": "json", "countrycodes": "in", "addressdetails": 1, "limit": 5},
                        _nom_parse, ttl_s=30 * DAY)


def reverse(lat: float, lon: float) -> ToolResult:
    """GPS -> district/state (needed to look up nearby mandis)."""
    def parse(j):
        a = j.get("address", {})
        if a.get("country_code") != "in":
            raise ValueError("location is outside India")
        return {"place": a.get("village") or a.get("town") or a.get("city") or a.get("county", ""),
                "district": a.get("state_district") or a.get("county", ""),
                "state": a.get("state", "")}
    return cached_fetch("reverse_geocode", "OpenStreetMap Nominatim", f"{settings().nominatim_url}/reverse",
                        {"lat": round(lat, 3), "lon": round(lon, 3), "format": "json", "zoom": 10},
                        parse, ttl_s=30 * DAY)
