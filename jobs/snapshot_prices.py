"""Daily job: save today's Agmarknet prices for our crops into price_history (our own time series).

data.gov.in only serves the latest day, so this is how trends exist at all. Runs via GitHub Actions
(.github/workflows/daily_snapshot.yml) and can be run by hand:  python -m jobs.snapshot_prices
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kisansaathi import db  # noqa: E402
from kisansaathi.config import settings  # noqa: E402
from kisansaathi.tools import crop_stage, mandi  # noqa: E402


def main() -> int:
    if not settings().data_gov_in_api_key:
        print("DATA_GOV_IN_API_KEY not set", file=sys.stderr)
        return 1
    total_new, failures = 0, 0
    for key, crop in crop_stage.crops().items():
        for name in crop["agmarknet"]:
            try:
                rows = mandi.fetch_all(commodity=name)  # all states: farmers anywhere in India benefit
            except Exception as e:  # noqa: BLE001
                failures += 1
                print(f"!! {name}: {e}", file=sys.stderr)
                continue
            new = db.upsert_prices(rows)
            total_new += new
            print(f"{key:8s} {name:24s} rows={len(rows):5d} new={new}")
    lo, hi, n = db.history_span()
    print(f"history: {n} rows from {lo} to {hi}; new today {total_new}; failures {failures}")
    return 0 if failures == 0 or total_new else 2


if __name__ == "__main__":
    sys.exit(main())
