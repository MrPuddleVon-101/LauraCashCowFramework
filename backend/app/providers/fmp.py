"""Financial Modeling Prep: global search, profiles and fundamentals.

Tier 2. It aggregates filings rather than publishing them, so for a US filer
SEC EDGAR stays authoritative and this corroborates. For a company that does not
file with the SEC it is often the only structured source, and the interface says
so on the row rather than presenting it as a filing.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .base import AssetClass, BaseProvider, Capability, Instrument

BASE = "https://financialmodelingprep.com/api/v3"
TIMEOUT = 12.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class FMP(BaseProvider):
    name = "Financial Modeling Prep"
    authority_tier = 2
    env_key = "FMP_API_KEY"
    _caps = {Capability.SEARCH.value, Capability.PROFILE.value,
             Capability.FUNDAMENTALS.value, Capability.QUOTE.value,
             Capability.FUND_DATA.value}

    def _get(self, path: str, **params):
        if not self.available():
            return None
        params["apikey"] = self.key
        try:
            r = httpx.get(f"{BASE}/{path}", params=params, timeout=TIMEOUT)
            r.raise_for_status()
            self._last_success = _now()
            self._last_error = None
            return r.json()
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            return None

    def search(self, query: str, limit: int = 20) -> list[Instrument]:
        rows = self._get("search", query=query, limit=limit) or []
        out: list[Instrument] = []
        for r in rows:
            out.append(Instrument(
                display_symbol=str(r.get("symbol") or "").upper(),
                provider_symbol=str(r.get("symbol") or "").upper(),
                name=r.get("name") or "",
                exchange=r.get("exchangeShortName") or r.get("stockExchange") or "",
                currency=r.get("currency") or "",
                provider=self.name,
                provenance=[{"provider": self.name, "retrieved_at": _now(), "endpoint": "search"}],
            ))
        return out

    def profile(self, symbol: str) -> Instrument | None:
        rows = self._get(f"profile/{symbol}") or []
        if not rows:
            return None
        r = rows[0]
        return Instrument(
            display_symbol=str(r.get("symbol") or symbol).upper(),
            provider_symbol=str(r.get("symbol") or symbol).upper(),
            name=r.get("companyName") or "",
            exchange=r.get("exchangeShortName") or "",
            country=r.get("country") or "",
            currency=r.get("currency") or "",
            isin=r.get("isin"),
            cusip=r.get("cusip"),
            cik=str(r.get("cik")) if r.get("cik") else None,
            asset_class=(AssetClass.BROAD_EQUITY_ETF.value if r.get("isEtf")
                         else AssetClass.COMMON_STOCK.value),
            is_primary_listing=not bool(r.get("isAdr")),
            provider=self.name,
            provenance=[{"provider": self.name, "retrieved_at": _now(), "endpoint": "profile"}],
        )
