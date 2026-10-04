"""Peer-group resolution.

PRD 12 defines the stock peer group as industry plus market-cap bucket plus
geographic market. We resolve in that order of preference and fall back to the
documented size band when a sector group is unavailable or too thin, which is the
behaviour PRD 12 explicitly permits. Whatever group is used is named on every metric
so the audit trail shows what the percentile was measured against.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"

MIN_SECTOR_PEERS = 10


@lru_cache(maxsize=1)
def _peers() -> dict:
    p = DATA / "peers.json"
    if not p.exists():
        return {"groups": {}, "generated_at": None, "source": None}
    return json.loads(p.read_text())


@lru_cache(maxsize=1)
def _sectors() -> dict[str, str]:
    p = DATA / "sectors.json"
    return json.loads(p.read_text()) if p.exists() else {}


# The exchange's own sector taxonomy, mapped onto the peer groups we built. The
# curated map is more precise where it has an opinion, so it wins; this extends
# coverage to every other listed company instead of dropping them into "all
# registrants", which is a far weaker comparison.
EXCHANGE_SECTOR_MAP: dict[str, str] = {
    "technology": "Technology",
    "finance": "Financials",
    "health care": "Health Care",
    "consumer discretionary": "Consumer Discretionary",
    "consumer staples": "Consumer Staples",
    "consumer non-durables": "Consumer Staples",
    "consumer durables": "Consumer Discretionary",
    "consumer services": "Consumer Discretionary",
    "energy": "Energy",
    "basic industries": "Materials",
    "capital goods": "Industrials",
    "transportation": "Industrials",
    "public utilities": "Utilities",
    "utilities": "Utilities",
    "real estate": "Real Estate",
    "telecommunications": "Communication Services",
}


def sector_for(ticker: str, exchange_sector: str | None = None,
               exchange_industry: str | None = None) -> str | None:
    curated = _sectors().get(ticker.upper())
    if curated:
        return curated
    industry = (exchange_industry or "").lower()
    if "semiconductor" in industry:
        return "Semiconductors"
    if exchange_sector:
        return EXCHANGE_SECTOR_MAP.get(exchange_sector.strip().lower())
    return None


def size_band(revenue: float | None) -> str | None:
    if not revenue:
        return None
    if revenue < 2e9:
        return "1-2bn"
    if revenue < 5e9:
        return "2-5bn"
    if revenue < 15e9:
        return "5-15bn"
    if revenue < 50e9:
        return "15-50bn"
    return "50bn-plus"


class PeerGroup:
    """Resolved peer set for one candidate, with a human-readable label."""

    def __init__(self, ticker: str, revenue: float | None,
                 exchange_sector: str | None = None, exchange_industry: str | None = None):
        self.ticker = ticker.upper()
        self.revenue = revenue
        self.sector = sector_for(ticker, exchange_sector, exchange_industry)
        self.band = size_band(revenue)
        self._groups = _peers().get("groups", {})
        self.key, self.label, self.n = self._resolve()

    def _resolve(self) -> tuple[str | None, str, int]:
        if self.sector:
            key = f"sector:{self.sector}"
            g = self._groups.get(key)
            if g and g.get("n", 0) >= MIN_SECTOR_PEERS:
                return key, f"{self.sector}, SEC registrants above $1bn revenue", g["n"]
        if self.band:
            key = f"size:{self.band}"
            g = self._groups.get(key)
            if g:
                return key, f"SEC registrants, revenue {self.band.replace('-', ' to ').replace('bn', 'bn')}", g["n"]
        g = self._groups.get("ALL")
        if g:
            return "ALL", "All SEC registrants above $1bn revenue", g["n"]
        return None, "No peer set available, scored against documented threshold bands", 0

    def distribution(self, metric: str) -> list[float]:
        if not self.key:
            return []
        return self._groups.get(self.key, {}).get("distributions", {}).get(metric, [])

    def meta(self) -> dict:
        src = _peers()
        return {
            "key": self.key,
            "label": self.label,
            "n": self.n,
            "sector": self.sector,
            "size_band": self.band,
            "generated_at": src.get("generated_at"),
            "source": src.get("source"),
            "source_url": src.get("source_url"),
            "periods": src.get("periods"),
        }
