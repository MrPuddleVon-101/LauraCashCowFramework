"""Freeze the engine's output so the interface can be hosted without a backend.

GitHub Pages serves files, not Python, and the interface is useless without the
scoring engine behind it. This runs the real engine over a fixed universe and
writes the answers to disk, so a static host can serve a genuine, fully worked
verdict for every ticker in that list. It is a snapshot, not a live engine: the
manifest carries the date it was taken and the interface says so on its face.

    cd backend && ./.venv/bin/python -m scripts.build_snapshot
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import FRAMEWORK_VERSION  # noqa: E402
from app.engine import evaluate as ev  # noqa: E402
from app.engine.registry import list_funds  # noqa: E402
from app.main import get_client, get_framework, get_liabilities  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"

STOCKS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "COST", "LLY", "JPM",
    "XOM", "CVX", "PG", "KO", "PEP", "CAT", "HD", "CSCO", "VZ", "ABBV", "AMGN",
    "MCD", "UNH", "O", "TSLA", "INTC", "PFE", "BA", "F", "PLTR",
]


def main() -> None:
    (OUT / "eval").mkdir(parents=True, exist_ok=True)

    # A defined maturity fund is pointless without a payment to point it at, and
    # scoring one with no target year reads its fit score as though it matched
    # nothing. Give each one the year it actually matures into.
    maturity = {f["ticker"]: f.get("maturity_year") for f in list_funds()}
    funds = list(maturity)
    tickers = sorted(set(funds) | set(STOCKS))

    (OUT / "framework.json").write_text(json.dumps(get_framework(), default=str))
    (OUT / "client.json").write_text(json.dumps(get_client(), default=str))
    (OUT / "liabilities.json").write_text(json.dumps(get_liabilities(2027), default=str))

    index: list[dict] = []
    failed: list[str] = []
    for i, t in enumerate(tickers, 1):
        try:
            result = ev.evaluate(
                ticker=t, role=None, position_pct=8.0,
                target_payment_year=maturity.get(t),
            )
        except Exception as exc:  # a snapshot is best effort; the live engine is not
            failed.append(f"{t}: {exc}")
            print(f"  [{i}/{len(tickers)}] {t} FAILED {exc}", flush=True)
            continue
        if result.get("error"):
            failed.append(f"{t}: {result.get('message')}")
            print(f"  [{i}/{len(tickers)}] {t} rejected", flush=True)
            continue
        (OUT / "eval" / f"{t}.json").write_text(json.dumps(result, default=str))
        index.append({
            "ticker": t,
            "name": result.get("name") or t,
            "type": result.get("asset_type_label") or "",
            "signal": result["signal"]["signal"],
            "composite": result["scores"]["composite"],
        })
        print(f"  [{i}/{len(tickers)}] {t} {result['signal']['signal']} "
              f"{result['scores']['composite']}", flush=True)

    (OUT / "manifest.json").write_text(json.dumps({
        "generated_on": date.today().isoformat(),
        "framework_version": FRAMEWORK_VERSION,
        "position_pct": 8.0,
        "role": "auto, with dated funds pointed at the year they mature",
        "tickers": sorted(r["ticker"] for r in index),
        "index": sorted(index, key=lambda r: -r["composite"]),
        "failed": failed,
        "note": (
            "Frozen output of the real engine, scored at the default role and an 8% "
            "position. Run the API locally for live prices, any ticker and any role."
        ),
    }, indent=1))
    print(f"\nwrote {len(index)} evaluations to {OUT}")
    if failed:
        print("could not score:", ", ".join(failed))


if __name__ == "__main__":
    main()
