"""Provider interfaces and the canonical instrument.

The engine used to reach for SEC, Nasdaq or Yahoo directly, which meant adding
a market meant editing the engine, and a missing key meant a traceback rather
than a smaller set of capabilities. Everything a provider can answer is declared
here, so the router can say what is reachable today and the interface can say
what it cannot do.

A ticker is not an identity. AAPL is one company on Nasdaq and something else
on a dozen other venues, and 7203 means Toyota only once you have said TSE. The
Instrument below is what the engine passes around instead.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class AssetClass(str, Enum):
    COMMON_STOCK = "common_stock"
    ADR = "adr"
    REIT = "reit"
    BROAD_EQUITY_ETF = "broad_equity_etf"
    INTERNATIONAL_EQUITY_ETF = "international_equity_etf"
    SECTOR_ETF = "sector_etf"
    BOND_ETF = "bond_etf"
    DEFINED_MATURITY_BOND_ETF = "defined_maturity_bond_etf"
    CASH_EQUIVALENT = "cash_equivalent"
    TREASURY = "treasury"
    CORPORATE_BOND = "corporate_bond"
    OTHER_FIXED_INCOME = "other_fixed_income"
    UNSUPPORTED = "unsupported"


class Freshness(str, Enum):
    LIVE = "LIVE"
    CACHED = "CACHED"
    STALE = "STALE"
    SNAPSHOT = "SNAPSHOT"


@dataclass
class Instrument:
    """One security, named well enough that it cannot be confused with another."""

    display_symbol: str
    provider_symbol: str = ""
    name: str = ""
    exchange: str = ""
    mic: str = ""
    country: str = ""
    currency: str = "USD"
    asset_class: str = AssetClass.UNSUPPORTED.value
    figi: str | None = None
    isin: str | None = None
    cusip: str | None = None
    cik: str | None = None
    is_primary_listing: bool = True
    provider: str = ""
    provenance: list[dict] = field(default_factory=list)

    @property
    def qualified(self) -> str:
        """Exchange-qualified form, which is the only form that is unambiguous."""
        return f"{self.display_symbol}:{self.exchange}" if self.exchange else self.display_symbol

    def to_dict(self) -> dict:
        return {
            "display_symbol": self.display_symbol,
            "provider_symbol": self.provider_symbol or self.display_symbol,
            "qualified_symbol": self.qualified,
            "name": self.name,
            "exchange": self.exchange,
            "mic": self.mic,
            "country": self.country,
            "currency": self.currency,
            "asset_class": self.asset_class,
            "figi": self.figi,
            "isin": self.isin,
            "cusip": self.cusip,
            "cik": self.cik,
            "is_primary_listing": self.is_primary_listing,
            "provider": self.provider,
            "provenance": self.provenance,
        }


@dataclass
class Observation:
    """A number with everything needed to check it.

    PRD 11 asks for a source, an as-of and a confidence on every figure. A bare
    float cannot carry that, so nothing a provider returns is a bare float.
    """

    value: Any
    units: str = ""
    currency: str | None = None
    period: str | None = None          # reporting period the value describes
    as_of: str | None = None           # when the value was true
    retrieved_at: str | None = None     # when we fetched it
    source: str = ""
    source_url: str = ""
    authority_tier: int = 3
    freshness: str = Freshness.LIVE.value
    kind: str = "reported"              # reported | derived | estimated | overridden

    def to_dict(self) -> dict:
        return {
            "value": self.value, "units": self.units, "currency": self.currency,
            "period": self.period, "as_of": self.as_of, "retrieved_at": self.retrieved_at,
            "source": self.source, "source_url": self.source_url,
            "authority_tier": self.authority_tier, "freshness": self.freshness,
            "kind": self.kind,
        }


class Capability(str, Enum):
    SEARCH = "search"
    RESOLVE = "resolve"
    PROFILE = "profile"
    QUOTE = "quote"
    HISTORY = "history"
    FUNDAMENTALS = "fundamentals"
    FUND_DATA = "fund_data"
    CURVE = "curve"


@runtime_checkable
class Provider(Protocol):
    """What any source must be able to say about itself."""

    name: str
    authority_tier: int

    def available(self) -> bool: ...
    def capabilities(self) -> set[str]: ...
    def status(self) -> dict: ...


class BaseProvider:
    """Shared plumbing: a provider that has no key is absent, not broken."""

    name = "base"
    authority_tier = 3
    env_key: str | None = None
    _caps: set[str] = set()

    def __init__(self) -> None:
        self.key = os.environ.get(self.env_key or "", "").strip() or None
        self._last_error: str | None = None
        self._last_success: str | None = None

    def available(self) -> bool:
        return self.env_key is None or bool(self.key)

    def capabilities(self) -> set[str]:
        return set(self._caps) if self.available() else set()

    def status(self) -> dict:
        return {
            "name": self.name,
            "available": self.available(),
            "authority_tier": self.authority_tier,
            "capabilities": sorted(self.capabilities()),
            "requires": self.env_key,
            "configured": bool(self.key) if self.env_key else True,
            "last_error": self._last_error,
            "last_success": self._last_success,
            "reason": None if self.available() else f"{self.env_key} is not set",
        }
