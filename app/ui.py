"""KisanSaathi Streamlit app.   Run:  streamlit run app/ui.py

Tabs: Ask (voice/text -> agent) · My farm (7-day risks & actions) · Mandi (prices & trend) · Profile.
Every number on screen comes from a live API, our DB of real snapshots, or the cited rules.
"""
from __future__ import annotations

import html
import sys
from datetime import date, timedelta
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.i18n import EXAMPLES, risk_name, t  # noqa: E402
from kisansaathi import db, health  # noqa: E402
from kisansaathi.agent.graph import run  # noqa: E402
from kisansaathi.dashboard import crop_outlook  # noqa: E402
from kisansaathi.models import LANGUAGES, CropPlan, FarmerProfile  # noqa: E402
from kisansaathi.tools import crop_stage, geocode, mandi, soil, weather  # noqa: E402
from kisansaathi.translate import translate_all  # noqa: E402

st.set_page_config(page_title="KisanSaathi", page_icon="🌾", layout="centered")

# Status colours (reserved for severity, always shown with icon + word) and chart ink.
SEV = {"low": ("#fab219", "#0b0b0b", "⚠"), "medium": ("#ec835a", "#0b0b0b", "⚠"), "high": ("#d03b3b", "#ffffff", "⛔")}
SEV_WORD = {"en": {"low": "Low", "medium": "Medium", "high": "High"},
            "hi": {"low": "कम", "medium": "मध्यम", "high": "अधिक"},
            "mr": {"low": "कमी", "medium": "मध्यम", "high": "जास्त"}}

st.markdown("""
<style>
.block-container {padding-top: 1.2rem; max-width: 760px;}
div.stButton > button {min-height: 3rem; font-size: 1.05rem; border-radius: 12px;}
.answer {font-size: 1.15rem; line-height: 1.6; padding: 1rem 1.1rem; border-radius: 14px;
         border: 1px solid rgba(11,11,11,.10); background: var(--secondary-background-color);}
.badge {display:inline-block; padding:2px 10px; border-radius:999px; font-size:.85rem; margin:2px 4px 2px 0;
        border:1px solid rgba(11,11,11,.12);}
.cal {width:100%; border-collapse:separate; border-spacing:2px; font-size:.82rem;}
.cal th {font-weight:600; color:#52514e; padding:4px; text-align:center;}
.cal td {padding:6px 4px; text-align:center; border-radius:6px; background:rgba(137,135,129,.08);}
.cal td.lbl {text-align:left; background:none; color:inherit; white-space:nowrap;}
.muted {color:#898781; font-size:.85rem;}
@media (max-width: 640px) { .cal {font-size:.72rem;} }
</style>""", unsafe_allow_html=True)


# ------------------------------------------------------------------ cached data access
@st.cache_data(ttl=300, show_spinner=False)
def _health():
    return health.check_all()


@st.cache_data(ttl=600, show_spinner=False)
def _forecast(lat, lon):
    return weather.get_forecast(lat, lon)


@st.cache_data(ttl=86400, show_spinner=False)
def _soil(lat, lon):
    return soil.get_soil(lat, lon)


@st.cache_data(ttl=1800, show_spinner=False)
def _prices(crop, state_, district):
    res = None
    for name in crop_stage.crops()[crop]["agmarknet"]:
        res = mandi.get_prices(name, state_, district)
        if res.ok:
            return res, name
    return res, crop_stage.crops()[crop]["agmarknet"][0]


@st.cache_resource(show_spinner=False)
def _warm():
    """Load the embedding model + keyword index once at startup, not on the first question.
    On a fresh host (e.g. Streamlit Cloud, no Docker build step) the guide index is built here first."""
    from kisansaathi.rag.ingest import get_collection
    from kisansaathi.rag.ingest import main as build_index
    if get_collection().count() == 0:
        with st.spinner("First start: indexing the official crop guides (a few minutes)…"):
            build_index()
    from kisansaathi.tools.knowledge import retrieve
    retrieve("warm up", None, 1)
    return True


def crop_name(key: str, lang: str) -> str:
    return crop_stage.crops()[key]["names"].get(lang) or crop_stage.crops()[key]["names"]["en"]


def stamp(res, lang) -> str:
    if not res or not res.ok:
        return f"<span class='badge'>✗ {t(lang, 'unavailable')}</span>"
    when = res.fetched_at.strftime("%d %b %H:%M") if res.fetched_at else ""
    if res.is_cached:
        return f"<span class='badge' style='background:#fab219;color:#0b0b0b'>◐ {t(lang, 'cached')} · {when}</span>"
    return f"<span class='muted'>{res.source} · {t(lang, 'data_as_of')} {when}</span>"


# ------------------------------------------------------------------ sidebar
ss = st.session_state
ss.setdefault("ui_lang", "hi")
ss.setdefault("history", [])

with st.sidebar:
    ss.ui_lang = st.selectbox("🌐 भाषा / Language", list(LANGUAGES), format_func=lambda c: LANGUAGES[c],
                              index=list(LANGUAGES).index(ss.ui_lang))
    L = ss.ui_lang
    farmers = db.list_farmers()
    options = [None, *[f.id for f in farmers]]
    by_id = {f.id: f for f in farmers}
    if "farmer_id" in ss and ss.farmer_id in options:
        default = options.index(ss.farmer_id)
    else:
        default = 1 if farmers else 0
    fid = st.selectbox(t(L, "choose_farmer"), options, index=default,
                       format_func=lambda i: t(L, "new_farmer") if i is None else
                       f"{by_id[i].name or 'Farmer'} — {by_id[i].place or by_id[i].district}")
    ss.farmer_id = fid
    with st.expander(t(L, "status"), expanded=False):
        for h in _health():
            icon = {"ok": "🟢", "degraded": "🟠", "down": "🔴"}[h["status"]]
            st.markdown(f"{icon} **{h['name']}** <span class='muted'>{h['detail'] or str(h['ms']) + ' ms'}</span>",
                        unsafe_allow_html=True)
        if st.button("↻", help="Re-check"):
            _health.clear()
            st.rerun()
    stats = db.usage_stats()
    st.caption(f"{t(L, 'usage')}: {stats['queries']} {t(L, 'queries')} · {stats['farmers']} {t(L, 'farmers')}")

farmer: FarmerProfile | None = by_id.get(fid)
L = ss.ui_lang

st.title("🌾 KisanSaathi")
st.caption(t(L, "tagline"))


# ------------------------------------------------------------------ profile editor
def profile_editor(existing: FarmerProfile | None):
    st.subheader(t(L, "profile_new") if existing is None else t(L, "tab_profile"))
    c1, c2 = st.columns(2)
    name = c1.text_input(t(L, "name"), value=existing.name if existing else "")
    lang = c2.selectbox(t(L, "language"), list(LANGUAGES), format_func=lambda c: LANGUAGES[c],
                        index=list(LANGUAGES).index(existing.language if existing else L))
    loc = ss.get("farm_loc") or ({"lat": existing.lat, "lon": existing.lon, "place": existing.place,
                             "district": existing.district, "state": existing.state} if existing else None)
    q = st.text_input(t(L, "place"), value=(loc or {}).get("place", ""))
    b1, b2 = st.columns(2)
    if b1.button("🔎 " + t(L, "find"), width="stretch") and q:
        res = geocode.search(q)
        ss.geo_results = res.data if res.ok else []
        if not res.ok:
            st.error(res.error)
    with b2:
        try:
            from streamlit_geolocation import streamlit_geolocation
            gps = streamlit_geolocation()
            if gps and gps.get("latitude"):
                rev = geocode.reverse(gps["latitude"], gps["longitude"])
                if rev.ok:
                    ss.farm_loc = {"lat": gps["latitude"], "lon": gps["longitude"], **rev.data}
                    loc = ss.farm_loc
                else:
                    st.warning(rev.error)
        except Exception:  # noqa: BLE001 - GPS is optional
            pass
    if ss.get("geo_results"):
        opts = ss.geo_results
        i = st.radio(t(L, "pick_place"), range(len(opts)),
                     format_func=lambda k: f"{opts[k]['name']}, {opts[k]['district']}, {opts[k]['state']}")
        o = opts[i]
        ss.farm_loc = loc = {"lat": o["lat"], "lon": o["lon"], "place": o["name"], "district": o["district"], "state": o["state"]}
    if loc:
        st.success(f"📍 {loc.get('place')}, {loc.get('district')}, {loc.get('state')} ({loc['lat']:.3f}, {loc['lon']:.3f})")

    keys = list(crop_stage.crops())
    chosen = st.multiselect(t(L, "crops"), keys, default=[c.name for c in existing.crops] if existing else [],
                            format_func=lambda k: crop_name(k, L))
    plans = []
    for k in chosen:
        prev = next((c.sowing_date for c in existing.crops if c.name == k), None) if existing else None
        d = st.date_input(f"{t(L, 'sowing')} {crop_name(k, L)}", value=prev or date.today() - timedelta(days=30),
                          min_value=date.today() - timedelta(days=400), max_value=date.today() + timedelta(days=120),
                          key=f"sow_{k}")
        plans.append(CropPlan(name=k, sowing_date=d))
    if st.button("💾 " + t(L, "save"), type="primary", width="stretch", disabled=not loc):
        prof = FarmerProfile(id=existing.id if existing else None, name=name, lat=loc["lat"], lon=loc["lon"],
                             place=loc.get("place", ""), district=loc.get("district", ""), state=loc.get("state", ""),
                             language=lang, crops=plans)
        ss.farmer_id = db.save_farmer(prof)
        ss.ui_lang = lang
        ss.pop("farm_loc", None)
        ss.pop("geo_results", None)
        st.success(t(L, "saved"))
        st.rerun()


if farmer is None:
    profile_editor(None)
    st.stop()

_warm()
tab_ask, tab_farm, tab_mandi, tab_prof = st.tabs([t(L, "tab_ask"), t(L, "tab_farm"), t(L, "tab_mandi"), t(L, "tab_profile")])


# ------------------------------------------------------------------ Ask
def show_answer(item: dict):
    ans = item["answer"]
    badge = (f"<span class='badge' style='background:#0ca30c;color:#fff'>✓ {t(L, 'verified')}</span>" if ans.verified
             and "Data-only" not in "".join(ans.trace) else f"<span class='badge'>ℹ {t(L, 'not_verified')}</span>")
    st.markdown(f"**🧑‍🌾 {html.escape(item['q'])}**")
    body = html.escape(ans.answer_local).replace("\n", "<br>")
    st.markdown(f"<div class='answer'>{body}</div>{badge}<span class='muted'> {ans.latency_ms / 1000:.1f}s · "
                f"{ans.llm_used}</span>", unsafe_allow_html=True)
    if ans.audio_bytes:
        st.audio(ans.audio_bytes, format=item.get("mime") or "audio/mp3")
    with st.expander(f"📚 {t(L, 'sources')} ({len(ans.citations)})"):
        for c in ans.citations:
            link = f"[{c.label}]({c.url})" if c.url else c.label
            cached = " · ◐ " + t(L, "cached") if c.is_cached else ""
            st.markdown(f"**[{c.id}]** {link} <span class='muted'>{c.detail}{cached}</span>", unsafe_allow_html=True)
    with st.expander(f"🧭 {t(L, 'how')}"):
        st.code("\n".join(ans.trace), language=None)
    if ans.answer_en and ans.language != "en" and ans.answer_en != ans.answer_local:
        with st.expander(f"🔤 {t(L, 'english')}"):
            st.write(ans.answer_en)


with tab_ask:
    lang = L  # the language picked in the sidebar drives examples, the answer and the voice reply
    asker = farmer.model_copy(update={"language": L})
    ex_crop = crop_name(farmer.crops[0].name, lang) if farmer.crops else ""
    examples = [e.format(crop=ex_crop) for e in EXAMPLES.get(lang, EXAMPLES["en"])]
    audio = st.audio_input(t(L, "ask_voice"))
    with st.form("ask", clear_on_submit=True, border=False):
        typed = st.text_input(t(L, "ask_text"), placeholder=examples[0])
        go = st.form_submit_button("➤ " + t(L, "ask_btn"), type="primary", width="stretch")
    pick = st.pills(t(L, "examples"), examples, selection_mode="single", key=f"ex_{len(ss.history)}")
    question = typed if go and typed else pick or ss.pop("pending_q", None)
    audio_bytes = audio.getvalue() if audio is not None and ss.get("last_audio") != hash(audio.getvalue()) else None
    if question or audio_bytes:
        if audio_bytes:
            ss.last_audio = hash(audio_bytes)
        with st.status(t(L, "thinking"), expanded=True) as box:
            shown = [0]

            def progress(trace: list[str]):
                for line in trace[shown[0]:]:
                    st.write(line)
                shown[0] = len(trace)

            ans = run(asker, question or "", audio=audio_bytes, audio_mime="audio/wav", on_step=progress)
            box.update(label=f"{'✓' if ans.verified else 'ℹ'} {ans.latency_ms / 1000:.1f}s", state="complete", expanded=False)
        q_shown = question or next((x.split("“", 1)[1].rstrip("”") for x in ans.trace if x.startswith("✓ Heard")), "🎤")
        ss.history.insert(0, {"q": q_shown, "answer": ans,
                              "mime": "audio/wav" if ans.audio_bytes and ans.audio_bytes[:4] == b"RIFF" else "audio/mp3"})
    for item in ss.history[:5]:
        show_answer(item)
        st.divider()


# ------------------------------------------------------------------ My farm
def risk_calendar(days: list[dict], flags, tr: dict[str, str]) -> str:
    sev_word = SEV_WORD.get(L, SEV_WORD["en"])
    types = list(dict.fromkeys(f.type for f in flags))
    head = "".join(f"<th>{date.fromisoformat(d['date']):%a<br>%d}</th>" for d in days)
    rows = []
    for ty in types:
        cells = []
        for d in days:
            hit = [f for f in flags if f.type == ty and f.day.isoformat() == d["date"]]
            if hit:
                worst = max(hit, key=lambda f: ["low", "medium", "high"].index(f.severity))
                bg, ink, icon = SEV[worst.severity]
                tip = html.escape(f"{tr.get(worst.message, worst.message)}\nSource: {worst.citation}")
                cells.append(f"<td style='background:{bg};color:{ink}' title='{tip}'>{icon} {sev_word[worst.severity]}</td>")
            else:
                cells.append("<td>·</td>")
        rows.append(f"<tr><td class='lbl'>{html.escape(risk_name(L, ty))}</td>{''.join(cells)}</tr>")
    return f"<table class='cal'><tr><th></th>{head}</tr>{''.join(rows)}</table>"


with tab_farm:
    fc = _forecast(farmer.lat, farmer.lon)
    st.markdown(stamp(fc, L), unsafe_allow_html=True)
    if not fc.ok:
        st.error(f"{t(L, 'forecast')}: {t(L, 'unavailable')} — {fc.error}")
    else:
        with st.expander(f"🌦️ {t(L, 'forecast')}", expanded=False):
            st.dataframe([{"day": f"{date.fromisoformat(d['date']):%a %d %b}", "max °C": d["tmax_c"], "min °C": d["tmin_c"],
                           "rain mm": d["rain_mm"], "rain %": d["rain_prob_pct"], "wind km/h": d["wind_max_kmh"],
                           "humidity %": d["rh_mean_pct"]} for d in fc.data["days"]], hide_index=True, width="stretch")
    for plan in farmer.crops:
        out = crop_outlook(fc, plan)
        stg = out["stage"]
        st.subheader(f"{crop_name(plan.name, L)}")
        if stg:
            c1, c2, c3 = st.columns(3)
            c1.metric(t(L, "stage"), stg.get("label", stg["stage"]))
            c2.metric(t(L, "days_after"), stg["days_after_sowing"])
            if stg.get("days_to_harvest") is not None:
                c3.metric(t(L, "to_harvest"), stg["days_to_harvest"])
            st.caption(f"Stage model: {stg.get('stage_source', '') or crop_stage.crops()[plan.name]['stage_source']}")
        if not out["forecast_ok"]:
            continue
        st.markdown(f"**{t(L, 'risk_cal')}**")
        if out["flags"]:
            tr = translate_all([f.message for f in out["flags"]], L)
            st.markdown(risk_calendar(fc.data["days"], out["flags"], tr), unsafe_allow_html=True)
            with st.expander("Details & sources"):
                for f in out["flags"]:
                    st.markdown(f"- **{f.day:%a %d %b}** — {tr.get(f.message, f.message)}  \n  <span class='muted'>{f.citation}</span>",
                                unsafe_allow_html=True)
        else:
            st.info(t(L, "no_risks"))
        w = out["windows"]
        st.markdown(f"**{t(L, 'windows')}**")
        if w.get("spray"):
            sp = w["spray"]
            st.markdown(f"🧴 **{t(L, 'best_spray')}:** {date.fromisoformat(sp['date']):%a %d %b}, {sp['hours']} "
                        f"<span class='muted'>(rain {sp['rain_prob_pct']}%, wind ≤ {sp['wind_max_kmh']} km/h)</span>",
                        unsafe_allow_html=True)
        else:
            st.markdown(f"🧴 {t(L, 'no_spray')}")
        if w.get("water"):
            wt = w["water"]
            st.markdown(f"💧 **{t(L, 'water')}:** " + t(L, "water_need", need=wt["crop_water_need_mm"], eff=wt["effective_rain_mm"])
                        + f" <span class='muted'>(ET0 {wt['et0_total_mm']} mm × Kc {wt['kc']}, FAO-56)</span>",
                        unsafe_allow_html=True)
        if w.get("harvest"):
            st.markdown(f"🌾 **{t(L, 'harvest')}:** " + ", ".join(f"{date.fromisoformat(d):%a %d}" for d in w["harvest"]["dry_days"]))
    sl = _soil(farmer.lat, farmer.lon)
    st.subheader(f"🟫 {t(L, 'soil')}")
    st.markdown(stamp(sl, L), unsafe_allow_html=True)
    if sl.ok:
        s = sl.data
        c1, c2, c3 = st.columns(3)
        c1.metric("pH", s["ph"])
        c2.metric("Organic C (g/kg)", s["organic_carbon_g_per_kg"])
        c3.metric("Texture", s["texture"] or "—")
        st.caption(f"Clay {s['clay_pct']}% · Sand {s['sand_pct']}% · Silt {s['silt_pct']}% · N {s['nitrogen_g_per_kg']} g/kg · "
                   f"CEC {s['cec_cmol_per_kg']} cmol/kg · {s['depth']} {('· ' + s['note']) if s.get('note') else ''}")


# ------------------------------------------------------------------ Mandi
with tab_mandi:
    if not farmer.crops:
        st.info(t(L, "crops"))
    else:
        crop = st.radio(t(L, "crops"), [c.name for c in farmer.crops], format_func=lambda k: crop_name(k, L), horizontal=True)
        res, commodity = _prices(crop, farmer.state, farmer.district)
        st.markdown(f"**{t(L, 'mandi_today')}** — {commodity}, {farmer.state}")
        st.markdown(stamp(res, L), unsafe_allow_html=True)
        if res and res.ok:
            d = res.data
            top = d["markets"][0]
            c1, c2, c3 = st.columns(3)
            c1.metric(f"{t(L, 'nearest')}: {top['market']}", f"₹{top['modal_price']:,.0f}")
            c2.metric(t(L, "state_avg"), f"₹{d['state_avg_modal']:,.0f}")
            c3.metric(t(L, "markets"), d["n_markets"])
            st.caption(f"{t(L, 'per_q')} · arrival date {d['arrival_date']}" + (f" · {d['scope_note']}" if d["scope_note"] else ""))
            st.dataframe([{"market": m["market"], "district": m["district"], "variety": m["variety"], "min": m["min_price"],
                           "max": m["max_price"], "modal": m["modal_price"], "date": m["date"]} for m in d["markets"]],
                         hide_index=True, width="stretch")
        elif res:
            st.warning(f"{t(L, 'unavailable')}: {res.error}")
        tr = mandi.get_trend(commodity, farmer.state, days=60)
        st.markdown(f"**{t(L, 'trend')}**")
        if tr.ok and tr.data["history_days"] >= 2:
            import plotly.graph_objects as go
            ser = tr.data["series"]
            fig = go.Figure(go.Scatter(x=[p["date"] for p in ser], y=[p["avg_modal"] for p in ser], mode="lines+markers",
                                       line=dict(color="#2a78d6", width=2), marker=dict(size=8),
                                       hovertemplate="%{x|%d %b}: ₹%{y:,.0f}/q<extra></extra>"))
            fig.update_layout(height=260, margin=dict(l=8, r=8, t=8, b=8), hovermode="x unified",
                              yaxis=dict(title=t(L, "per_q"), gridcolor="rgba(137,135,129,.25)", zeroline=False),
                              xaxis=dict(showgrid=False), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.caption(t(L, "history_since", d=tr.data["since"], n=tr.data["history_days"]) +
                       (f" · {tr.data['direction']} {tr.data.get('change_pct', '')}%" if tr.data.get("change_pct") is not None else ""))
            with st.expander("Table"):
                st.dataframe(ser, hide_index=True, width="stretch")
        else:
            st.info(t(L, "no_history"))
        if st.button("🤔 " + t(L, "ask_sell"), width="stretch"):
            ss.pending_q = EXAMPLES.get(L, EXAMPLES["en"])[1].format(crop=crop_name(crop, L))
            st.toast("→ " + t(L, "tab_ask"))
            st.rerun()


with tab_prof:
    profile_editor(farmer)
