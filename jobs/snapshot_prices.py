"""Daily job: save today's Agmarknet prices for our crops into price_history (our own time series).

data.gov.in only serves the latest day, so this is how trends exist at all. Runs via GitHub Actions
(.github/workflows/daily_snapshot.yml) and can be run by hand:  python -m jobs.snapshot_prices

Gentle on the API: one query per crop (its commodity names are filtered exactly afterwards), a pause between
crops, and one slow retry if a query comes back empty (that's how data.gov.in throttles bursts).
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kisansaathi import db  # noqa: E402
from kisansaathi.config import settings  # noqa: E402
from kisansaathi.tools import crop_stage, mandi  # noqa: E402

PAUSE_S, RETRY_PAUSE_S = 3, 15


def main() -> int:
    if not settings().data_gov_in_api_key:
        print("DATA_GOV_IN_API_KEY not set", file=sys.stderr)
        return 1
    before = db.history_span()[2]
    empty, failures = [], 0
    for key, crop in crop_stage.crops().items():
        names = set(crop["agmarknet"])
        rows = []
        for query in crop["agmarknet"]:  # usually the first name already returns all variants
            for attempt in (1, 2):
                try:
                    rows = mandi.fetch_all(commodity=query, keep=names)  # all states
                except Exception as e:  # noqa: BLE001
                    failures += 1
                    print(f"!! {key} {query}: {type(e).__name__}", file=sys.stderr)
                    rows = []
                if rows or attempt == 2:
                    break
                time.sleep(RETRY_PAUSE_S)
            time.sleep(PAUSE_S)
            if rows:
                break
        if rows:
            db.upsert_prices(rows)
            found = sorted({r["commodity"] for r in rows})
            print(f"{key:8s} rows={len(rows):5d} states={len({r['state'] for r in rows}):2d} names={found}")
        else:
            empty.append(key)
            print(f"{key:8s} no rows today")
    lo, hi, n = db.history_span()
    print(f"history: {n} rows ({n - before} new) from {lo} to {hi}; empty: {empty or 'none'}; failures: {failures}")
    return 0 if n > before or not failures else 2


if __name__ == "__main__":
    sys.exit(main())
