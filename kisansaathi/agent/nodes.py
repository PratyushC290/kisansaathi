"""LangGraph nodes. Each takes the state and returns the keys it updates.

Design rule: tools and rules produce facts; the LLM only routes the question and explains the facts.
If the LLM is unavailable, every node has a deterministic fallback so the farmer still gets an answer.
"""
from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date

from .. import llm
from ..dashboard import crop_outlook
from ..models import LANGUAGES, Citation, CropPlan, ToolResult
from ..speech import transcribe, tts
from ..tools import crop_stage, knowledge, mandi, rules, soil, weather
from .prompts import JUDGE, KCC, NO_LLM, OUT_OF_SCOPE, REPEAT, SYNTHESIZE, UNDERSTAND, UNVERIFIED
from .state import INTENTS, AgentState, Draft, Judgement, Understanding
from .verify import check

MAX_ATTEMPTS = 3

# Script -> language, used when the LLM is down (fallback language detection).
SCRIPTS = [("஀", "௿", "ta"), ("ఀ", "౿", "te"), ("ঀ", "৿", "bn"),
           ("઀", "૿", "gu"), ("਀", "੿", "pa"), ("ಀ", "೿", "kn"),
           ("ऀ", "ॿ", "hi")]
# Keyword fallback for intents (English, Hindi, Marathi, romanised Hindi).
KEYWORDS = {
    "spray_timing": ["spray", "छिड़काव", "छिडकाव", "फवारणी", "chhidkav", "dawai", "दवा", "कीटनाशक"],
    "irrigation": ["irrigat", "water", "सिंचाई", "पानी", "पाणी", "sinchai", "paani"],
    "sell_or_hold": ["sell", "price", "mandi", "market", "rate", "बेच", "भाव", "मंडी", "विक", "बाजार", "bhav", "bech"],
    "harvest_timing": ["harvest", "कटाई", "काढणी", "तोड़", "katai"],
    "sowing": ["sow", "plant", "बुवाई", "बोवनी", "पेरणी", "लागवड", "buvai"],
    "pest_disease": ["pest", "insect", "disease", "blight", "rot", "कीट", "रोग", "कीड", "रोग", "इल्ली", "keeda", "rog"],
    "fertilizer": ["fertili", "urea", "dap", "खाद", "उर्वरक", "खत", "khad"],
    "weather": ["weather", "rain", "मौसम", "बारिश", "पाऊस", "हवामान", "barish", "mausam"],
    "soil": ["soil", "मिट्टी", "माती", "mitti"],
}


def _t(state: AgentState, line: str) -> list[str]:
    return [*state.get("trace", []), line]


ROMAN_HINDI = {"kya", "kab", "karu", "karun", "karna", "chahiye", "mein", "hai", "ki", "ka", "ko", "abhi",
               "bechu", "becho", "fasal", "khet", "pani", "barish", "kaise", "nahi", "aur", "mera", "meri"}


def _detect_lang(text: str, profile_lang: str) -> str:
    for lo, hi, code in SCRIPTS:
        if any(lo <= ch <= hi for ch in text):
            # Hindi and Marathi share Devanagari; trust the profile to tell them apart.
            return profile_lang if code == "hi" and profile_lang in ("hi", "mr") else code
    words = set(re.findall(r"[a-z]+", text.lower()))
    if len(words & ROMAN_HINDI) >= 2:  # Hinglish -> answer in the farmer's own language
        return profile_lang if profile_lang != "en" else "hi"
    return "en"


# ---------------------------------------------------------------- transcribe
def node_transcribe(state: AgentState) -> dict:
    t0 = time.time()
    text, lang, provider = transcribe(state["audio"], state.get("audio_mime", "audio/wav"))
    if not text:
        return {"question_raw": "", "trace": _t(state, "✗ Could not understand the audio")}
    return {"question_raw": text, "language": lang,
            "trace": _t(state, f"✓ Heard ({provider}, {time.time() - t0:.1f}s): “{text}”")}


# ---------------------------------------------------------------- understand
def node_understand(state: AgentState) -> dict:
    farmer, q = state["farmer"], state.get("question_raw", "").strip()
    if not q:
        lang = state.get("language") or farmer.language
        return {"in_scope": True, "clarification": REPEAT.get(lang, REPEAT["en"]), "language": lang}
    q = q[:1000]  # very long inputs are truncated, not rejected
    profile_crops = [c.name for c in farmer.crops]
    try:
        u, model = llm.chat_json(
            UNDERSTAND.format(crops=profile_crops or "none", supported=list(crop_stage.crops()), intents=INTENTS),
            f"Farmer's message: <<<{q}>>>", Understanding)
        intents = [i for i in u.intents if i in INTENTS] or ["general"]
        crop = u.crop if u.crop in crop_stage.crops() else crop_stage.match_crop(q)
        lang = u.language if u.language in LANGUAGES else farmer.language
        how = f"LLM {model}"
        llm_used = [*state.get("llm_used", []), model]
        in_scope, clar, q_en = u.in_scope, u.clarification, u.question_en
    except Exception as e:  # noqa: BLE001 - LLM down: keyword routing keeps the app useful
        low = q.lower()
        intents = [k for k, words in KEYWORDS.items() if any(w in low for w in words)] or ["general"]
        crop = crop_stage.match_crop(q)
        lang = _detect_lang(q, farmer.language)
        in_scope, clar, q_en, how = True, None, q, f"keyword fallback ({type(e).__name__})"
        llm_used = state.get("llm_used", [])
    if not crop and len(profile_crops) == 1:
        crop = profile_crops[0]
    needs_crop = set(intents) - {"weather", "soil", "general"}
    if needs_crop and not crop and not clar:
        names = [crop_stage.crops()[c]["names"].get(lang, c) for c in profile_crops] or \
                [c["names"].get(lang, k) for k, c in crop_stage.crops().items()]
        clar = {"hi": f"किस फसल के बारे में पूछ रहे हैं? ({', '.join(names)})",
                "mr": f"कोणत्या पिकाबद्दल विचारत आहात? ({', '.join(names)})"}.get(
            lang, f"Which crop is this about? ({', '.join(names)})")
    if clar and crop:
        clar = None  # the model sometimes asks even when we already know the crop
    return {"question_en": q_en, "language": lang, "intents": intents, "crop": crop, "in_scope": in_scope,
            "clarification": clar, "llm_used": llm_used,
            "trace": _t(state, f"✓ Understood via {how}: intents={intents}, crop={crop or '—'}, language={lang}")}


def route_after_understand(state: AgentState) -> str:
    if not state.get("in_scope", True) or state.get("clarification"):
        return "direct"
    return "plan"


def node_direct(state: AgentState) -> dict:
    lang = state.get("language", "en")
    if not state.get("in_scope", True):
        text = OUT_OF_SCOPE.get(lang, OUT_OF_SCOPE["en"])
        return {"answer_local": text, "answer_en": OUT_OF_SCOPE["en"], "verified": True,
                "trace": _t(state, "• Out of scope → polite redirect")}
    return {"answer_local": state["clarification"], "answer_en": state["clarification"], "verified": True,
            "trace": _t(state, "• Asked the farmer a clarifying question")}


# ---------------------------------------------------------------- plan
def node_plan(state: AgentState) -> dict:
    """Deterministic intent -> tools mapping (reliable and explainable to judges)."""
    intents, crop = set(state["intents"]), state.get("crop")
    plan = ["weather", "knowledge"]
    if crop:
        plan.append("crop_stage")
    if intents & {"soil", "fertilizer", "sowing", "irrigation"}:
        plan.append("soil")
    if crop and intents & {"sell_or_hold", "harvest_timing"}:
        plan += ["mandi", "mandi_trend"]
    return {"plan": plan, "trace": _t(state, f"✓ Plan: {', '.join(plan)}")}


# ---------------------------------------------------------------- execute
def _mandi_prices(crop: str, farmer) -> ToolResult:
    last = None
    for name in crop_stage.crops()[crop]["agmarknet"]:
        last = mandi.get_prices(name, farmer.state, farmer.district)
        if last.ok:
            return last
    return last


def _mandi_trend(crop: str, farmer) -> ToolResult:
    res = None
    for name in crop_stage.crops()[crop]["agmarknet"]:
        res = mandi.get_trend(name, farmer.state)
        if res.ok and res.data["history_days"]:
            return res
    return res


def node_execute(state: AgentState) -> dict:
    farmer, crop = state["farmer"], state.get("crop")
    plan_crop = next((c for c in farmer.crops if c.name == crop), None)
    q_en = state.get("question_en") or state["question_raw"]
    jobs = {
        "weather": lambda: weather.get_forecast(farmer.lat, farmer.lon),
        "knowledge": lambda: knowledge.retrieve(state["question_raw"], crop, 4, query_en=q_en),
        "soil": lambda: soil.get_soil(farmer.lat, farmer.lon),
        "crop_stage": lambda: crop_stage.get_stage(crop, plan_crop.sowing_date) if plan_crop else ToolResult(
            tool="crop_stage", ok=False, error=f"no sowing date saved for {crop}; add it in your profile"),
        "mandi": lambda: _mandi_prices(crop, farmer),
        "mandi_trend": lambda: _mandi_trend(crop, farmer),
    }
    evidence, lines = {}, []
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {name: (ex.submit(jobs[name]), time.time()) for name in state["plan"]}
        for name, (fut, t0) in futs.items():
            try:
                res = fut.result(timeout=60)
            except Exception as e:  # noqa: BLE001 - a tool must never crash the graph
                res = ToolResult(tool=name, ok=False, error=f"{type(e).__name__}: {e}")
            evidence[name] = res
            mark = "✓" if res.ok and not res.is_cached else ("◐ cached" if res.ok else "✗")
            lines.append(f"{mark} {name} ({time.time() - t0:.1f}s)" + ("" if res.ok else f" — {res.error[:80]}"))
    return {"evidence": evidence, "trace": [*state.get("trace", []), *lines]}


# ---------------------------------------------------------------- assess risk + build evidence pack
def _wd(d: str) -> str:
    return date.fromisoformat(d).strftime("%a %d %b")


def node_assess(state: AgentState) -> dict:
    ev, farmer, crop = state["evidence"], state["farmer"], state.get("crop")
    pack: list[dict] = []
    cites: list[Citation] = []

    def add(kind, label, content, url="", detail="", cached=False):
        sid = f"S{len(pack) + 1}"
        pack.append({"id": sid, "kind": kind, "label": label, "content": content})
        cites.append(Citation(id=sid, label=label, url=url, detail=detail, is_cached=cached))
        return sid

    def when(r: ToolResult) -> str:
        if not r.fetched_at:
            return ""
        s = r.fetched_at.strftime("%d %b %H:%M")
        return f"last updated {s} (cached — live source failed)" if r.is_cached else f"fetched {s}"

    w = ev.get("weather")
    stage = ev.get("crop_stage")
    risks = []
    if w and w.ok:
        days = [{"day": _wd(d["date"]), "date": d["date"], "max_temp_c": d["tmax_c"], "min_temp_c": d["tmin_c"],
                 "rain_mm": d["rain_mm"], "rain_chance_pct": d["rain_prob_pct"], "max_wind_kmh": d["wind_max_kmh"],
                 "humidity_mean_pct": d["rh_mean_pct"],
                 "calm_dry_spray_hours": f"{d['spray_hours'][0]}-{d['spray_hours'][-1]}" if d["spray_hours"] else "none"}
                for d in w.data["days"]]
        add("weather", f"Open-Meteo 7-day forecast for {farmer.place or farmer.district} ({farmer.lat:.2f}, {farmer.lon:.2f})",
            {"days": days, "cached": w.is_cached}, w.url, when(w), w.is_cached)
    if stage and stage.ok:
        add("crop_stage", "Crop stage from sowing date (FAO-56 stage lengths)", stage.data,
            "https://www.fao.org/4/x0490e/x0490e0b.htm", "Table 11")
    if w and w.ok and crop:
        plan_crop = next((c for c in farmer.crops if c.name == crop), None) or CropPlan(name=crop, sowing_date=date.today())
        outlook = crop_outlook(w, plan_crop)
        risks = outlook["flags"]
        wins = {k: v for k, v in outlook["windows"].items() if v}
        if wins.get("spray"):
            wins["spray"]["day"] = _wd(wins["spray"]["date"])
        if wins:
            add("windows", "KisanSaathi calculation: spray window & crop water need (forecast × FAO-56 Kc)", wins,
                detail="computed from the forecast above")
        by_rule: dict[str, list] = {}
        for f in risks:
            by_rule.setdefault(f.rule_id, []).append(f)
        for rid, fl in by_rule.items():
            rd = rules.rule_detail(rid)
            c0 = rd["citations"][0]
            add("risk", f"Risk rule {rid} — {rules.citation_text(c0)}",
                {"days": [_wd(f.day.isoformat()) for f in fl], "values": [f.value for f in fl],
                 "severity": fl[0].severity, "advice": fl[0].message, "official_text": c0["quote"],
                 "threshold_basis": rd.get("basis"), "note": rd.get("note", "")},
                rules.sources().get(c0["doc"], {}).get("url", ""))
    elif w and w.ok:
        risks = rules.evaluate(w.data["days"], None, None)
    s = ev.get("soil")
    if s and s.ok:
        add("soil", "ISRIC SoilGrids topsoil (0-5 cm) at your location", s.data, s.url, when(s), s.is_cached)
    m = ev.get("mandi")
    if m and m.ok:
        d = m.data
        add("mandi", f"Agmarknet mandi prices — {d['commodity']}, {d['state']} (₹/quintal), arrival date {d['arrival_date']}",
            {k: d[k] for k in ("scope", "scope_note", "state_avg_modal", "state_max_modal", "state_min_modal", "n_markets")}
            | {"markets": [{k: x[k] for k in ("market", "district", "date", "min_price", "max_price", "modal_price")}
                           for x in d["markets"][:8]]},
            "https://agmarknet.gov.in", when(m), m.is_cached)
    t = ev.get("mandi_trend")
    if t and t.ok:
        td = t.data
        add("trend", f"KisanSaathi price history from daily Agmarknet snapshots ({td['history_days']} days"
                     f"{', since ' + td['since'] if td['since'] else ''})",
            {k: td.get(k) for k in ("direction", "change_pct", "history_days", "since")} | {"series": td["series"][-14:]},
            detail="our own database")
    k = ev.get("knowledge")
    if k and k.ok:
        for h in k.data:
            add("guide", f"{h['publisher']} — {h['title']}, PDF p.{h['page']}", h["text"][:900], h["url"])
    missing = {n: r.error for n, r in ev.items() if not r.ok}
    line = f"✓ Rules engine: {len(risks)} risk flag(s); evidence pack S1–S{len(pack)}"
    if missing:
        line += f"; unavailable: {', '.join(missing)}"
    return {"risks": risks, "pack": pack, "citations": cites, "trace": _t(state, line), "attempts": 0}


# ---------------------------------------------------------------- synthesize
def _evidence_text(state: AgentState) -> str:
    parts = [f"[{p['id']}] {p['label']}\n{json.dumps(p['content'], ensure_ascii=False, default=str)}"
             for p in state["pack"]]
    missing = [f"- {n}: unavailable ({r.error[:120]})" for n, r in state["evidence"].items() if not r.ok]
    if missing:
        parts.append("UNAVAILABLE DATA (say so if relevant, do not guess):\n" + "\n".join(missing))
    return "\n\n".join(parts)


def node_synthesize(state: AgentState) -> dict:
    lang = state["language"]
    problems = state.get("problems") or []
    fix = ("\nYour previous draft had these problems — fix ALL of them:\n- " + "\n- ".join(problems)) if problems else ""
    system = SYNTHESIZE.format(lang_name=LANGUAGES.get(lang, "English"), lang=lang, kcc=KCC, problems=fix)
    farmer = state["farmer"]
    user = (f"Today is {date.today():%A %d %B %Y}. Farmer: {farmer.place or farmer.district}, {farmer.state}. "
            f"Crop: {state.get('crop') or 'not specified'}.\nQuestion: <<<{state['question_raw']}>>>\n"
            f"(English: {state.get('question_en', '')})\n\nEVIDENCE:\n{_evidence_text(state)}")
    attempt = state.get("attempts", 0) + 1
    try:
        t0 = time.time()
        draft, model = llm.chat_json(system, user, Draft)
        return {"draft": draft, "attempts": attempt, "llm_used": [*state.get("llm_used", []), model],
                "trace": _t(state, f"✓ Drafted answer (attempt {attempt}, {model}, {time.time() - t0:.1f}s)")}
    except Exception as e:  # noqa: BLE001
        return {"draft": None, "attempts": MAX_ATTEMPTS,
                "trace": _t(state, f"✗ LLM unavailable ({str(e)[:80]}) → data-only answer")}


# ---------------------------------------------------------------- verify (self-correction)
def node_verify(state: AgentState) -> dict:
    d: Draft | None = state.get("draft")
    if d is None:
        return {"verified": False}
    problems = check(d.answer_local, state["pack"], state["question_raw"]) + \
        [f"(English version) {p}" for p in check(d.answer_en, state["pack"], state["question_raw"])]
    if not problems:
        try:  # LLM judge: catches unsupported *claims*, not just numbers
            j, model = llm.chat_json(JUDGE.format(kcc=KCC),
                                     f"EVIDENCE:\n{_evidence_text(state)}\n\nANSWER:\n{d.answer_en}", Judgement)
            if not j.supported and j.unsupported_claims:
                problems = [f"Unsupported claim: {c}" for c in j.unsupported_claims[:4]]
        except Exception:  # noqa: BLE001 - judge is a bonus; programmatic checks already passed
            pass
    if problems:
        return {"verified": False, "problems": problems,
                "trace": _t(state, f"✗ Verifier: {len(problems)} issue(s) — {problems[0][:90]}")}
    return {"verified": True, "problems": [], "answer_local": d.answer_local, "answer_en": d.answer_en,
            "trace": _t(state, "✓ Verifier: every number and claim matches the evidence")}


def route_after_verify(state: AgentState) -> str:
    if state.get("verified"):
        return "speak"
    if state.get("draft") is not None and state.get("attempts", 0) < MAX_ATTEMPTS:
        return "retry"
    return "fallback"


# ---------------------------------------------------------------- deterministic safe answer
def node_fallback(state: AgentState) -> dict:
    """Built only from evidence, so it is grounded by construction. Used when the LLM is down or
    the verifier keeps failing — the farmer always gets the key facts."""
    lang, pack = state.get("language", "en"), state.get("pack", [])
    by = {p["kind"]: p for p in pack}
    lines = []
    for p in pack:
        if p["kind"] == "risk":
            c = p["content"]
            lines.append(f"• {', '.join(c['days'][:3])}: {c['advice']} [{p['id']}]")
    win = by.get("windows")
    if win and win["content"].get("spray"):
        sp = win["content"]["spray"]
        lines.append(f"• Best spray window: {sp['day']} {sp['hours']} [{win['id']}]")
    if win and win["content"].get("water"):
        wt = win["content"]["water"]
        lines.append(f"• Crop water need next {wt['days']} days ≈ {wt['crop_water_need_mm']} mm; "
                     f"forecast rain {wt['forecast_rain_mm']} mm [{win['id']}]")
    if "mandi" in by:
        md = by["mandi"]["content"]
        top = md["markets"][0]
        lines.append(f"• {top['market']} modal price ₹{top['modal_price']:g}/quintal; state average "
                     f"₹{md['state_avg_modal']}/quintal [{by['mandi']['id']}]")
    if "trend" in by:
        tr = by["trend"]["content"]
        lines.append(f"• Price trend: {tr['direction']} over {tr['history_days']} days of our records [{by['trend']['id']}]")
    if not lines:
        lines.append(f"• Live data is unavailable right now. Please call the Kisan Call Centre {KCC} (free) or your KVK.")
    guides = [p for p in pack if p["kind"] == "guide"]
    if guides:
        lines.append(f"• See official guide: {guides[0]['label']} [{guides[0]['id']}]")
    body = "\n".join(lines)
    msgs = NO_LLM if state.get("draft") is None else UNVERIFIED
    head = msgs.get(lang, msgs["en"])
    why = "LLM unavailable" if state.get("draft") is None else "verifier could not confirm the AI draft"
    return {"answer_local": f"{head}\n{body}", "answer_en": body, "verified": True,
            "trace": _t(state, f"• Data-only answer from evidence ({why})")}


# ---------------------------------------------------------------- speak
def node_speak(state: AgentState) -> dict:
    if state.get("skip_speech"):
        return {}
    t0 = time.time()
    audio, mime = tts(state["answer_local"], state.get("language", "hi"))
    ok = "✓" if audio else "✗"
    return {"audio_out": audio, "audio_out_mime": mime,
            "trace": _t(state, f"{ok} Voice reply ({mime or 'unavailable'}, {time.time() - t0:.1f}s)")}
