"""Which source answers which question, and what to do when none can.

The hierarchy is fixed and deliberate. A filing outranks an aggregator, an
aggregator outranks a scraper, and nothing outranks saying "we do not know".

    1  SEC EDGAR .................. US filings, tier 1
    2  U.S. Treasury .............. the curve, tier 1
    3  Nasdaq ..................... US quotes and spreads, tier 1
    4  FMP ........................ global search, profiles, fundamentals, tier 2
    5  Twelve Data ................ global quotes and history, tier 2
    6  OpenFIGI ................... identity resolution, tier 1 for identifiers
    7  Yahoo ...................... corroboration and last resort, tier 2

A provider with no key is absent rather than broken: the router drops it, the
health endpoint names it, and the interface disables what it cannot do. It never
substitutes a weaker source silently for a stronger one without saying so.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from .base import Capability, Instrument
from .fmp import FMP
from .openfigi import OpenFIGI
from .twelvedata import TwelveData

_fmp = FMP()
_twelve = TwelveData()
_figi = OpenFIGI()

#: Every pluggable provider, in preference order within each capability.
REGISTRY = [_fmp, _twelve, _figi]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def providers_for(capability: str) -> list:
    return [p for p in REGISTRY if capability in p.capabilities()]


def capabilities() -> dict[str, list[str]]:
    """What can actually be answered right now, by whom."""
    out: dict[str, list[str]] = {}
    for cap in Capability:
        out[cap.value] = [p.name for p in providers_for(cap.value)]
    return out


def status() -> dict:
    """Provider health, for /api/health and for the coverage page."""
    rows = [p.status() for p in REGISTRY]
    caps = capabilities()
    # SEC, Treasury, Nasdaq and Yahoo are keyless and always attempted; they
    # report their own health inside their modules.
    return {
        "checked_at": _now(),
        "providers": rows,
        "capabilities": caps,
        "global_search": bool(caps.get(Capability.SEARCH.value)),
        "global_quotes": bool(caps.get(Capability.QUOTE.value)),
        "identifier_resolution": bool(caps.get(Capability.RESOLVE.value)),
        "degraded": [p["name"] for p in rows if not p["available"]],
    }


def search(query: str, limit: int = 20) -> dict:
    """Search every source that can, and keep the matches distinguishable.

    Results are not merged into one row per ticker. AAPL on Nasdaq and AAPL on
    a European venue are different instruments, and collapsing them is how a
    reader ends up scoring the wrong one.
    """
    results: list[Instrument] = []
    used: list[str] = []
    for p in providers_for(Capability.SEARCH.value):
        try:
            found = p.search(query, limit=limit)
        except Exception:
            continue
        if found:
            used.append(p.name)
            results.extend(found)

    seen: set[tuple[str, str]] = set()
    unique: list[Instrument] = []
    for r in results:
        key = (r.display_symbol, r.exchange)
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)

    by_symbol: dict[str, int] = {}
    for r in unique:
        by_symbol[r.display_symbol] = by_symbol.get(r.display_symbol, 0) + 1

    return {
        "query": query,
        "results": [r.to_dict() for r in unique[:limit]],
        "providers_used": used,
        "ambiguous": sorted(s for s, n in by_symbol.items() if n > 1),
        "searched_global": bool(used),
        "note": (
            "No global search provider is configured, so this covers the local "
            "registry and SEC filers only."
            if not used else
            f"Searched {', '.join(used)}."
        ),
    }


#: OpenFIGI exchange codes for the venues a reader is most likely to mean,
#: best first. Ambiguity is still reported; this only decides what to show at
#: the top and what to use in the worked example.
_VENUE_RANK = {
    "UW": 0, "UN": 1, "UQ": 2, "UP": 3, "US": 4, "UA": 5,   # United States
    "LN": 10,                                               # London
    "JT": 12, "JE": 13,                                     # Tokyo
    "HK": 14, "SP": 15, "NA": 16, "IS": 17, "IN": 18,       # HK, Singapore, Amsterdam, India
    "GR": 20, "GY": 21, "FP": 22, "SW": 23,                 # Continental Europe
}
_US_VENUES = {"UW", "UN", "UQ", "UP", "US", "UA"}


def _venue_sort(i: Instrument) -> tuple:
    return (_VENUE_RANK.get(i.exchange, 99), i.exchange or "zz")


def resolve(ident: str, exchange: str = "") -> dict:
    """Turn an identifier into one instrument, or say it is ambiguous.

    A ticker that exists on several venues is never silently resolved to one of
    them: the caller is told to choose, because picking for them is how you
    score Toyota's Tokyo line and report it as the ADR.
    """
    id_type = "TICKER"
    cleaned = ident.strip().upper()
    if ":" in cleaned:
        cleaned, exchange = cleaned.split(":", 1)
    if len(cleaned) == 12 and cleaned[:2].isalpha() and cleaned[2:].isalnum():
        id_type = "ID_ISIN"
    elif len(cleaned) == 12 and cleaned.startswith("BBG"):
        id_type = "ID_BB_GLOBAL"

    matches: list[Instrument] = []
    try:
        matches = _figi.resolve(cleaned, id_type=id_type, exchange=exchange)
    except Exception:
        matches = []

    if len(matches) == 1:
        return {"resolved": matches[0].to_dict(), "ambiguous": False, "candidates": []}
    if len(matches) > 1:
        matches.sort(key=_venue_sort)
        for m in matches:
            m.is_primary_listing = m.exchange in _US_VENUES
        venues = [m.exchange for m in matches if m.exchange]
        seen_v: list[str] = []
        for v in venues:
            if v not in seen_v:
                seen_v.append(v)
        suggest = seen_v[0] if seen_v else ""
        return {
            "resolved": None,
            "ambiguous": True,
            "candidates": [m.to_dict() for m in matches[:25]],
            "exchanges": seen_v,
            "note": (
                f"{cleaned} trades on {len(seen_v)} venues. Qualify it, for example "
                f"{cleaned}:{suggest}, rather than letting the engine choose."
            ),
        }
    return {
        "resolved": None, "ambiguous": False, "candidates": [],
        "note": f"No identifier service could resolve {cleaned}.",
    }
