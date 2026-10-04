"""U.S. Treasury par yield curve adapter.

PRD 36 is pointed about this: do not use one universal 4% rate forever. The team's
4% figure is an illustrative planning assumption, not a market fact. This module
fetches the daily par yield curve so the present value of each of Laura's ten
payments is discounted at a yield appropriate to its own maturity.
"""

from __future__ import annotations

import csv
import io
import time
from datetime import date
from pathlib import Path
from typing import Any

import httpx

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"
CACHE_DIR.mkdir(exist_ok=True)
CACHE_FILE = CACHE_DIR / "treasury_curve.json"
TTL = 12 * 3600

CSV_URL = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all?type=daily_treasury_yield_curve&_format=csv"
)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
}

TENORS: list[tuple[str, float]] = [
    ("1 Mo", 1 / 12), ("2 Mo", 2 / 12), ("3 Mo", 0.25), ("6 Mo", 0.5),
    ("1 Yr", 1.0), ("2 Yr", 2.0), ("3 Yr", 3.0), ("5 Yr", 5.0),
    ("7 Yr", 7.0), ("10 Yr", 10.0), ("20 Yr", 20.0), ("30 Yr", 30.0),
]

SOURCE_URL = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?type=daily_treasury_yield_curve"


def _fetch() -> dict | None:
    for year in (date.today().year, date.today().year - 1):
        try:
            r = httpx.get(CSV_URL.format(year=year), headers=HEADERS, timeout=30.0, follow_redirects=True)
            if r.status_code != 200 or not r.text.strip().startswith("Date"):
                continue
            rows = list(csv.DictReader(io.StringIO(r.text)))
            if not rows:
                continue
            latest = rows[0]
            points = []
            for label, years in TENORS:
                raw = (latest.get(label) or "").strip()
                if not raw:
                    continue
                try:
                    points.append({"tenor": label, "years": years, "yield_pct": float(raw)})
                except ValueError:
                    continue
            if len(points) < 5:
                continue
            return {
                "as_of": latest.get("Date"),
                "points": points,
                "source": "U.S. Department of the Treasury, daily par yield curve",
                "source_url": SOURCE_URL,
                "authority_tier": 1,
            }
        except (httpx.HTTPError, csv.Error):
            continue
    return None


# Used only if Treasury is unreachable. Carries its own as-of date so the interface
# can show that the curve is stale rather than presenting it as today's market.
FALLBACK = {
    "as_of": None,
    "points": [{"tenor": f"{y:g} Yr", "years": y, "yield_pct": 4.0} for y in (1, 2, 3, 5, 7, 10, 20, 30)],
    "source": "Flat 4% planning assumption, the team's illustrative figure",
    "source_url": "",
    "authority_tier": 5,
    "degraded": True,
    "note": "Treasury could not be reached, so every maturity is discounted at the team's illustrative 4%. PRD 36 warns against treating this as a market fact.",
}


def get_curve() -> dict:
    import json
    if CACHE_FILE.exists() and time.time() - CACHE_FILE.stat().st_mtime < TTL:
        try:
            return json.loads(CACHE_FILE.read_text())
        except (OSError, ValueError):
            pass
    curve = _fetch()
    if curve is None:
        return dict(FALLBACK)
    try:
        CACHE_FILE.write_text(json.dumps(curve))
    except OSError:
        pass
    return curve


def yield_for(years: float, curve: dict | None = None) -> float:
    """Linearly interpolated par yield, as a decimal, for a given maturity in years."""
    curve = curve or get_curve()
    pts = sorted(curve.get("points", []), key=lambda p: p["years"])
    if not pts:
        return 0.04
    if years <= pts[0]["years"]:
        return pts[0]["yield_pct"] / 100.0
    if years >= pts[-1]["years"]:
        return pts[-1]["yield_pct"] / 100.0
    for a, b in zip(pts, pts[1:]):
        if a["years"] <= years <= b["years"]:
            span = b["years"] - a["years"]
            if span <= 0:
                return b["yield_pct"] / 100.0
            t = (years - a["years"]) / span
            return (a["yield_pct"] + (b["yield_pct"] - a["yield_pct"]) * t) / 100.0
    return pts[-1]["yield_pct"] / 100.0
