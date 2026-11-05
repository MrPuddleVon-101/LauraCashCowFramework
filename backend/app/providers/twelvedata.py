"""Twelve Data: global quotes, history and exchange reference data.

Tier 2. Used for the markets Nasdaq does not cover and for the exchange list
behind the coverage page, so a claim about what is supported can be checked
rather than asserted.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .base import BaseProvider, Capability, Instrument

BASE = "https://api.twelvedata.com"
TIMEOUT = 12.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class TwelveData(BaseProvider):
    name = "Twelve Data"
    authority_tier = 2
    env_key = "TWELVE_DATA_API_KEY"
    _caps = {Capability.QUOTE.value, Capability.HISTORY.value,
             Capability.SEARCH.value, Capability.RESOLVE.value}

    def _get(self, path: str, **params):
        if not self.available():
            return None
        params["apikey"] = self.key
        try:
            r = httpx.get(f"{BASE}/{path}", params=params, timeout=TIMEOUT)
            r.raise_for_status()
            body = r.json()
            # The API answers 200 with a status field on rate limits and errors.
            if isinstance(body, dict) and body.get("status") == "error":
                self._last_error = str(body.get("message"))[:200]
                return None
            self._last_success = _now()
            self._last_error = None
            return body
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            return None

    def search(self, query: str, limit: int = 20) -> list[Instrument]:
        body = self._get("symbol_search", symbol=query, outputsize=limit) or {}
        out: list[Instrument] = []
        for r in (body.get("data") or [])[:limit]:
            out.append(Instrument(
                display_symbol=str(r.get("symbol") or "").upper(),
                provider_symbol=str(r.get("symbol") or "").upper(),
                name=r.get("instrument_name") or "",
                exchange=r.get("exchange") or "",
                mic=r.get("mic_code") or "",
                country=r.get("country") or "",
                currency=r.get("currency") or "",
                provider=self.name,
                provenance=[{"provider": self.name, "retrieved_at": _now(),
                             "endpoint": "symbol_search"}],
            ))
        return out

    def quote(self, symbol: str, exchange: str = "") -> dict | None:
        params = {"symbol": symbol}
        if exchange:
            params["exchange"] = exchange
        body = self._get("quote", **params)
        if not isinstance(body, dict) or "close" not in body:
            return None
        return {
            "price": float(body["close"]),
            "currency": body.get("currency"),
            "exchange": body.get("exchange"),
            "as_of": body.get("datetime"),
            "retrieved_at": _now(),
            "source": self.name,
        }
