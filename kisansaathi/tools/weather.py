"""7-day forecast for the farmer's plot from Open-Meteo (free, no key).

Daily values drive the risk rules; hourly values let us find spray windows
(low wind + low rain chance) and long high-humidity spells (fungal risk).
"""
from __future__ import annotations

from collections import defaultdict

from ..config import settings
from ..http import cached_fetch
from ..models import ToolResult

DAILY = ["temperature_2m_max", "temperature_2m_min", "precipitation_sum", "precipitation_probability_max",
         "wind_speed_10m_max", "et0_fao_evapotranspiration", "relative_humidity_2m_mean"]
HOURLY = ["relative_humidity_2m", "wind_speed_10m", "precipitation_probability", "precipitation",
          "soil_moisture_0_to_1cm", "soil_moisture_3_to_9cm", "soil_temperature_6cm"]


def _parse(j):
    d, h = j["daily"], j["hourly"]
    days = []
    by_day = defaultdict(list)
    for i, t in enumerate(h["time"]):
        by_day[t[:10]].append(i)
    for i, day in enumerate(d["time"]):
        hrs = by_day.get(day, [])
        # Daytime spray-friendly hours (06–18): wind < 10 km/h and rain chance < 30 %.
        spray_hours = [h["time"][k][11:16] for k in hrs if 6 <= int(h["time"][k][11:13]) <= 18
                       and (h["wind_speed_10m"][k] or 0) < 10 and (h["precipitation_probability"][k] or 0) < 30]
        sm = [h["soil_moisture_3_to_9cm"][k] for k in hrs if h["soil_moisture_3_to_9cm"][k] is not None]
        rh = [h["relative_humidity_2m"][k] for k in hrs if h["relative_humidity_2m"][k] is not None]
        days.append({
            "date": day,
            "tmax_c": d["temperature_2m_max"][i], "tmin_c": d["temperature_2m_min"][i],
            "rain_mm": d["precipitation_sum"][i], "rain_prob_pct": d["precipitation_probability_max"][i],
            "wind_max_kmh": d["wind_speed_10m_max"][i], "et0_mm": d["et0_fao_evapotranspiration"][i],
            "rh_mean_pct": d["relative_humidity_2m_mean"][i],
            "rh_hours_above_85": sum(1 for v in rh if v >= 85),
            "soil_moisture_3_9cm": round(sum(sm) / len(sm), 3) if sm else None,
            "spray_hours": spray_hours,
        })
    return {"lat": j["latitude"], "lon": j["longitude"], "units": j["daily_units"], "days": days}


def get_forecast(lat: float, lon: float, days: int = 7) -> ToolResult:
    params = {"latitude": round(lat, 2), "longitude": round(lon, 2), "daily": ",".join(DAILY),
              "hourly": ",".join(HOURLY), "timezone": "Asia/Kolkata", "forecast_days": days}
    return cached_fetch("weather", "Open-Meteo forecast", settings().weather_url, params, _parse, ttl_s=3 * 3600)
