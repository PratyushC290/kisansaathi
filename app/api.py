"""FastAPI wrapper around the same core (for integrations: WhatsApp/IVR bots, other apps).

Run:  uvicorn app.api:app --port 8000
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kisansaathi import db, health  # noqa: E402
from kisansaathi.agent.graph import run  # noqa: E402
from kisansaathi.dashboard import crop_outlook  # noqa: E402
from kisansaathi.models import FarmerProfile  # noqa: E402
from kisansaathi.tools import weather  # noqa: E402

app = FastAPI(title="KisanSaathi API", version="0.1")


class AskBody(BaseModel):
    farmer: FarmerProfile | None = None
    farmer_id: int | None = None
    question: str
    speak: bool = False


def _farmer(body_farmer: FarmerProfile | None, farmer_id: int | None) -> FarmerProfile:
    if body_farmer:
        return body_farmer
    f = next((x for x in db.list_farmers(1000) if x.id == farmer_id), None)
    if not f:
        raise HTTPException(404, "farmer not found; pass `farmer` or a valid `farmer_id`")
    return f


def _out(ans):
    d = ans.model_dump(mode="json", exclude={"audio_bytes"})
    d["audio_b64"] = base64.b64encode(ans.audio_bytes).decode() if ans.audio_bytes else None
    return d


@app.get("/health")
def get_health():
    checks = health.check_all()
    return {"status": "ok" if all(c["status"] != "down" for c in checks) else "degraded", "checks": checks}


@app.post("/ask")
def ask(body: AskBody):
    return _out(run(_farmer(body.farmer, body.farmer_id), body.question, speak=body.speak))


@app.post("/ask/voice")
async def ask_voice(farmer_id: int = Form(...), audio: UploadFile = File(...)):
    data = await audio.read()
    return _out(run(_farmer(None, farmer_id), "", audio=data, audio_mime=audio.content_type or "audio/wav"))


@app.get("/risk/{farmer_id}")
def risk(farmer_id: int):
    f = _farmer(None, farmer_id)
    fc = weather.get_forecast(f.lat, f.lon)
    if not fc.ok:
        raise HTTPException(503, f"forecast unavailable: {fc.error}")
    return {"forecast_fetched_at": fc.fetched_at, "is_cached": fc.is_cached,
            "crops": [{**crop_outlook(fc, c), "flags": [x.model_dump(mode="json") for x in crop_outlook(fc, c)["flags"]]}
                      for c in f.crops]}
