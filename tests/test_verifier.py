"""Verifier: catches invented numbers / citations, accepts honest rounding and unit conversion."""
from kisansaathi.agent.verify import check, numbers_in

PACK = [{"id": "S1", "content": {"days": [{"date": "2026-11-02", "rain_mm": 11.1, "max_temp_c": 30.3}]}},
        {"id": "S2", "content": {"modal_price": 2150, "state_avg_modal": 1890}}]


def test_grounded_answer_passes():
    assert check("Don't spray on Mon 2 Nov: about 11 mm rain [S1]. Onion fetches ₹2150/quintal (₹21.5/kg) [S2].", PACK) == []


def test_devanagari_digits_are_checked():
    assert numbers_in("३०.३ डिग्री, ₹२,१५०") == [30.3, 2150.0]
    assert check("सोमवार को ३० डिग्री [S1]।", PACK) == []
    assert check("सोमवार को ४५ मिमी बारिश [S1]।", PACK)


def test_invented_number_is_caught():
    probs = check("Rain of 45 mm expected [S1].", PACK)
    assert any("45" in p for p in probs)


def test_fake_citation_and_uncited_number():
    probs = check("Price is 2150 today. See [S9].", PACK)
    assert any("S9" in p for p in probs) and any("without a citation" in p for p in probs)


def test_helpline_and_small_counts_allowed():
    assert check("Wait 2-3 days and call 1800-180-1551 [S1].", PACK) == []
