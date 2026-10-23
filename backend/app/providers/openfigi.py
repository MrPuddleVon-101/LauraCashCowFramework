"""OpenFIGI: turning an identifier into an identity.

A FIGI distinguishes the Tokyo line of Toyota from the ADR, which a ticker
cannot. Used to resolve ambiguity rather than to price anything, so it carries
no market data and no opinion.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from .base import BaseProvider, Capability, Instrument

URL = "https://api.openfigi.com/v3/mapping"
TIMEOUT = 12.0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class OpenFIGI(BaseProvider):
    name = "OpenFIGI"
    authority_tier = 1          # an identifier registry, not an opinion
    env_key = "OPENFIGI_API_KEY"
    _caps = {Capability.RESOLVE.value}

    def available(self) -> bool:
        # OpenFIGI answers without a key at a lower rate limit, so this provider
        # is usable unkeyed. The key only raises the ceiling.
        return True

    def status(self) -> dict:
        s = super().status()
        s["configured"] = bool(self.key)
        s["reason"] = None if self.key else "No key: usable at the anonymous rate limit."
        return s

    def resolve(self, ident: str, id_type: str = "TICKER",
                exchange: str = "") -> list[Instrument]:
        job: dict = {"idType": id_type, "idValue": ident}
        if exchange:
            job["exchCode"] = exchange
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["X-OPENFIGI-APIKEY"] = self.key
        try:
            r = httpx.post(URL, json=[job], headers=headers, timeout=TIMEOUT)
            r.raise_for_status()
            body = r.json()
            self._last_success = _now()
            self._last_error = None
        except Exception as exc:
            self._last_error = f"{type(exc).__name__}: {exc}"
            return []
        out: list[Instrument] = []
        for block in body or []:
            for d in (block.get("data") or []):
                out.append(Instrument(
                    display_symbol=str(d.get("ticker") or ident).upper(),
                    provider_symbol=str(d.get("ticker") or ident).upper(),
                    name=d.get("name") or "",
                    exchange=d.get("exchCode") or "",
                    mic=d.get("micCode") or "",
                    figi=d.get("figi"),
                    asset_class=d.get("securityType2") or "",
                    provider=self.name,
                    provenance=[{"provider": self.name, "retrieved_at": _now(),
                                 "endpoint": "mapping", "id_type": id_type}],
                ))
        return out
