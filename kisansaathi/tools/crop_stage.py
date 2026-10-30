"""Crop stage + water need from sowing date, using FAO-56 stage lengths and Kc (data/crops.yaml)."""
from __future__ import annotations

from datetime import date
from functools import lru_cache

import yaml

from ..config import DATA_DIR
from ..models import ToolResult

ORDER = ["init", "dev", "mid", "late"]


@lru_cache
def crops() -> dict:
    return yaml.safe_load((DATA_DIR / "crops.yaml").read_text())["crops"]


def match_crop(text: str) -> str | None:
    """Find a supported crop mentioned in free text, in any language (key, English or local name)."""
    t = text.lower()
    for key, c in crops().items():
        for name in [key, *c["names"].values()]:
            for part in str(name).lower().replace("(", "/").replace(")", "").split("/"):
                if part.strip() and part.strip() in t:
                    return key
    return None


def kc_for(crop: str, stage: str, day_in_stage: int) -> float:
    """FAO-56 Kc curve: flat in init and mid, linear in dev (ini->mid) and late (mid->end)."""
    c = crops()[crop]
    kc, st = c["kc"], c["stages"]
    if stage == "init":
        return kc["ini"]
    if stage == "mid":
        return kc["mid"]
    if stage == "dev":
        return round(kc["ini"] + (kc["mid"] - kc["ini"]) * day_in_stage / st["dev"], 2)
    return round(kc["mid"] + (kc["end"] - kc["mid"]) * day_in_stage / st["late"], 2)


def get_stage(crop: str, sowing_date: date, on: date | None = None) -> ToolResult:
    on = on or date.today()
    if crop not in crops():
        return ToolResult(tool="crop_stage", ok=False, error=f"unsupported crop '{crop}'")
    c = crops()[crop]
    das = (on - sowing_date).days  # days after sowing/transplanting
    total = sum(c["stages"].values())
    if das < 0:
        return ToolResult(tool="crop_stage", ok=True, source=f"FAO-56 ({c['stage_source']})",
                          data={"crop": crop, "stage": "not_sown", "days_after_sowing": das,
                                "label": f"sowing planned in {-das} days", "total_days": total})
    start = 0
    for s in ORDER:
        length = c["stages"][s]
        if das < start + length:
            day_in = das - start
            return ToolResult(tool="crop_stage", ok=True, source=f"FAO-56 ({c['stage_source']})", data={
                "crop": crop, "stage": s, "label": c["stage_labels"][s], "days_after_sowing": das,
                "day_in_stage": day_in, "stage_length": length, "total_days": total,
                "days_to_harvest": total - das, "kc": kc_for(crop, s, day_in), "kc_source": c["kc_source"]})
        start += length
    return ToolResult(tool="crop_stage", ok=True, source=f"FAO-56 ({c['stage_source']})", data={
        "crop": crop, "stage": "harvested", "label": "past typical harvest time", "days_after_sowing": das,
        "total_days": total, "days_to_harvest": 0})
