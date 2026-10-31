"""Rules engine: thresholds fire exactly at the documented values, and every rule is cited."""
from datetime import date, timedelta

from kisansaathi.tools import crop_stage, rules


def day(**kw):
    base = {"date": "2026-11-01", "tmax_c": 25.0, "tmin_c": 15.0, "rain_mm": 0.0, "rain_prob_pct": 5,
            "wind_max_kmh": 5.0, "et0_mm": 4.0, "rh_mean_pct": 50, "rh_hours_above_85": 0,
            "soil_moisture_3_9cm": 0.3, "spray_hours": ["08:00", "09:00", "10:00"]}
    return base | kw


def ids(flags):
    return {f.rule_id for f in flags}


def test_every_rule_has_a_real_citation():
    docs = rules.sources()
    for r in rules.rules():
        assert r["citations"], r["id"]
        for c in r["citations"]:
            assert c["doc"] in docs and c["page"] > 0 and c["quote"], r["id"]
        assert r["basis"] in {"quoted", "operational", "mixed"}
        if r["basis"] != "quoted":
            assert r.get("note"), f"{r['id']} must explain its operational threshold"


def test_wheat_heat_only_at_grain_filling():
    hot = [day(tmax_c=29.0)]
    assert "wheat_heat_grain_fill" in ids(rules.evaluate(hot, "wheat", "mid"))
    assert "wheat_heat_grain_fill" not in ids(rules.evaluate(hot, "wheat", "init"))
    assert "wheat_heat_grain_fill" not in ids(rules.evaluate([day(tmax_c=28.0)], "wheat", "mid"))  # 28 is still OK


def test_rain_blocks_spraying_and_counts_tomorrow():
    assert "spray_rain_24h" in ids(rules.evaluate([day(rain_mm=3.0)], "onion", "mid"))
    two = [day(), day(date="2026-11-02", rain_mm=6.0)]
    flagged = [f for f in rules.evaluate(two, "onion", "mid") if f.rule_id == "spray_rain_24h"]
    assert [f.day.isoformat() for f in flagged] == ["2026-11-01", "2026-11-02"]


def test_onion_stemphylium_needs_long_wetness():
    assert "onion_stemphylium" in ids(rules.evaluate([day(tmax_c=26, tmin_c=16, rh_hours_above_85=16)], "onion", "mid"))
    assert "onion_stemphylium" not in ids(rules.evaluate([day(tmax_c=26, tmin_c=16, rh_hours_above_85=15)], "onion", "mid"))


def test_stage_rule_and_forecast_rule():
    assert "onion_stop_irrigation" in ids(rules.evaluate([day()], "onion", "late"))
    dry = [day(date=f"2026-11-0{i}") for i in range(1, 8)]
    assert "soy_dry_spell" in ids(rules.evaluate(dry, "soybean", "mid"))


def test_rules_do_not_leak_across_crops():
    assert "potato_heat" not in ids(rules.evaluate([day(tmax_c=35)], "onion", "mid"))


def test_crop_stage_and_kc():
    st = crop_stage.get_stage("wheat", date.today() - timedelta(days=70)).data
    assert st["stage"] == "mid" and st["kc"] == 1.15
    # Indian-variety durations (cited in crops.yaml), not FAO's 210 days for onion
    on = crop_stage.get_stage("onion", date.today() - timedelta(days=30)).data
    assert on["total_days"] == 120 and on["days_to_harvest"] == 90
    assert crop_stage.get_stage("wheat", date.today() + timedelta(days=3)).data["stage"] == "not_sown"
    assert crop_stage.match_crop("गेहूं में पानी कब दूं") == "wheat"
    assert crop_stage.match_crop("कांदा") == "onion"


def test_fixture_forecast_produces_flags(forecast_days):
    flags = rules.evaluate(forecast_days, "onion", "mid")
    assert all(f.citation for f in flags)


def test_always_on_low_rule_shows_once_not_every_day(forecast_days):
    hot = [day(date=f"2026-11-0{i + 1}", tmax_c=33.0) for i in range(7)]
    heat = [f for f in rules.evaluate(hot, "tomato", "mid") if f.rule_id == "tomato_heat"]
    assert len(heat) == 1 and "7 of the next 7 days" in heat[0].message
    some = [day(date=f"2026-11-0{i + 1}", tmax_c=33.0 if i < 2 else 25.0) for i in range(7)]
    assert len([f for f in rules.evaluate(some, "tomato", "mid") if f.rule_id == "tomato_heat"]) == 2
    per_rule = {}
    for f in rules.evaluate(forecast_days, "tomato", "mid"):
        per_rule[f.rule_id] = per_rule.get(f.rule_id, 0) + 1
    assert per_rule.get("tomato_heat", 0) <= 1
