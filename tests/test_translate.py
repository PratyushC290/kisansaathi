"""My Farm translation: numbers must survive, failures fall back to English, risk names cover every rule type."""
from app.i18n import RISK
from kisansaathi import cache, llm, translate
from kisansaathi.tools import rules


def test_every_rule_type_has_hindi_and_marathi_names():
    types = {r["type"] for r in rules.rules()}
    for lang in ("hi", "mr"):
        assert types <= set(RISK[lang]), types - set(RISK[lang])


def test_translation_keeps_numbers_or_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(cache, "get_fresh", lambda k: None)
    monkeypatch.setattr(cache, "set_fresh", lambda *a, **k: None)
    monkeypatch.setattr(llm, "available", lambda: ["stub"])
    monkeypatch.setattr(llm, "chat_json", lambda *a, **k: (translate._Batch(
        translations=["तापमान 33 °C है", "तापमान 99 °C है"]), "stub"))
    out = translate.translate_all(["Temperature is 33 °C", "Temperature is 34 °C"], "hi")
    assert out == {"Temperature is 33 °C": "तापमान 33 °C है"}  # the one that changed a number is dropped
    assert translate.translate_all(["Temperature is 33 °C"], "en") == {}
