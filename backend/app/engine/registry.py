"""Local fund registry and security classification. PRD 56 service 1.

No keyless public API exposes ETF holdings, expense ratios or defined maturity dates,
so those facts live in data/etf_registry.json with the issuer page each row should be
checked against. PRD 11 would place an issuer factsheet in tier 1, but a figure
transcribed into a file and not re-read today is not the same thing as reading the
factsheet, so the registry is treated as tier 2 and the interface says so.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from .normalize import Source

DATA = Path(__file__).resolve().parents[2] / "data"

AssetType = Literal[
    "stock", "broad_us_equity", "international_equity", "thematic_sector",
    "defined_maturity_bond", "perpetual_bond", "cash_equivalent", "treasury", "unknown",
]

ASSET_TYPE_LABELS: dict[str, str] = {
    "stock": "Individual stock",
    "broad_us_equity": "Broad U.S. equity ETF",
    "international_equity": "International equity ETF",
    "thematic_sector": "Sector or thematic ETF",
    "defined_maturity_bond": "Defined maturity bond ETF",
    "perpetual_bond": "Perpetual bond ETF",
    "cash_equivalent": "Cash equivalent",
    "treasury": "U.S. Treasury security",
    "unknown": "Unclassified",
}

# Which roles make sense for which asset type. PRD 7 forbids scoring a Treasury and a
# growth stock against the same objective.
ROLES_FOR_TYPE: dict[str, list[str]] = {
    "stock": ["SG", "CG", "LG"],
    "broad_us_equity": ["CG", "LG", "SG"],
    "international_equity": ["ID", "CG", "LG"],
    "thematic_sector": ["SG", "CG"],
    "defined_maturity_bond": ["LM", "DA", "LR"],
    "perpetual_bond": ["DA", "LR", "LM"],
    "cash_equivalent": ["LR", "DA"],
    "treasury": ["LM", "LR", "DA"],
    "unknown": ["CG", "SG", "ID", "LM", "LR", "LG", "DA"],
}


@lru_cache(maxsize=1)
def _registry() -> dict:
    p = DATA / "etf_registry.json"
    if not p.exists():
        return {"_meta": {}, "funds": {}}
    return json.loads(p.read_text())


def registry_meta() -> dict:
    return _registry().get("_meta", {})


def get_fund(ticker: str, live: dict | None = None) -> dict | None:
    """The registry row, with expense ratio and scale replaced by live figures.

    Transcribed numbers drift. The registry had SGOV at a 0.09% expense ratio when
    the fund now charges 0.05% after its waiver, and AVUS at roughly half its real
    size. Anything the exchange reports directly is taken from the exchange; the
    registry keeps what no public endpoint carries, which is holdings, sector and
    country weights, and the maturity structure.
    """
    fund = _registry().get("funds", {}).get(ticker.upper())
    if fund is None:
        return None
    out = dict(fund)
    out.setdefault("as_of", registry_meta().get("as_of"))
    out["provenance"] = registry_meta().get("provenance", "seed")
    out["ticker"] = ticker.upper()

    if live:
        if live.get("expense_ratio") is not None:
            if out.get("expense_ratio") != live["expense_ratio"]:
                out["expense_ratio_registry"] = out.get("expense_ratio")
            out["expense_ratio"] = live["expense_ratio"]
            out["expense_ratio_source"] = "exchange"
        if live.get("market_cap"):
            out["aum_registry"] = out.get("aum_usd")
            out["aum_usd"] = live["market_cap"]
            out["aum_source"] = "exchange"
        if live.get("beta") is not None:
            out["beta_reported"] = live["beta"]
        if live.get("week52_high") and live.get("week52_low"):
            out["week52_high"] = live["week52_high"]
            out["week52_low"] = live["week52_low"]
    return out


def fund_source(ticker: str) -> Source:
    fund = _registry().get("funds", {}).get(ticker.upper()) or {}
    return Source(
        name=f"{fund.get('issuer', 'Fund issuer')} factsheet, transcribed to the local registry",
        url=fund.get("source_url", ""),
        source_type="issuer",
        authority_tier=2,
        publication_date=registry_meta().get("as_of"),
        claim_supported="Expense ratio, holdings, weights, maturity structure",
    )


def list_funds() -> list[dict]:
    out = []
    for ticker, fund in _registry().get("funds", {}).items():
        out.append({
            "ticker": ticker,
            "name": fund.get("name"),
            "category": fund.get("category"),
            "asset_type_label": ASSET_TYPE_LABELS.get(fund.get("category", ""), "Fund"),
            "expense_ratio": fund.get("expense_ratio"),
            "maturity_year": fund.get("maturity_year"),
        })
    return sorted(out, key=lambda x: x["ticker"])


def classify(ticker: str, live: dict | None = None) -> tuple[AssetType, dict | None]:
    """Resolve a symbol to an asset type and, where one exists, its registry row.

    The registry is checked first because an ETF ticker can collide with a company
    ticker in the SEC list, and the registry row is the more specific answer.
    """
    ticker = ticker.strip().upper()
    fund = get_fund(ticker, live)
    if fund:
        return fund.get("category", "unknown"), fund
    return "stock", None
