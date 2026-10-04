"""Portfolio look-through. PRD 32 and 33.

The point Morningstar makes, and the PRD repeats, is that holding three funds can
disguise one concentrated bet. If Laura owns an ETF containing NVIDIA, a second ETF
containing NVIDIA, and NVIDIA directly, her real exposure is the sum of all three.
This module resolves every position down to issuer level and reports what she
actually owns, before and after a proposed trade.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .peers import sector_for
from .registry import get_fund


@dataclass
class Position:
    ticker: str
    value: float
    role: str = ""
    asset_type: str = ""
    label: str = ""

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker, "value": self.value, "role": self.role,
            "asset_type": self.asset_type, "label": self.label,
        }


def _expand(position: Position, total: float) -> tuple[dict[str, float], dict[str, float], dict[str, float], float]:
    """Resolve one position into issuer, sector and country weights of the whole portfolio.

    Returns the three maps plus the share of the position that could not be resolved
    to named issuers, which is reported rather than silently dropped.
    """
    share = position.value / total * 100 if total else 0.0
    issuers: dict[str, float] = {}
    sectors: dict[str, float] = {}
    countries: dict[str, float] = {}

    fund = get_fund(position.ticker)
    if not fund:
        # An individual holding is its own issuer.
        issuers[position.ticker] = share
        sec = sector_for(position.ticker)
        if sec:
            sectors[sec] = share
        countries["United States"] = share
        return issuers, sectors, countries, 0.0

    top = fund.get("top_holdings") or []
    named = 0.0
    for entry in top:
        if not entry or len(entry) < 2:
            continue
        tkr, w = str(entry[0]), float(entry[1])
        contribution = share * w / 100.0
        issuers[tkr] = issuers.get(tkr, 0.0) + contribution
        named += w

    # Sector and country weights are published for the whole fund, so they apply to
    # the full position even though only the top holdings are named.
    for s, w in (fund.get("sector_weights") or {}).items():
        sectors[s] = sectors.get(s, 0.0) + share * w / 100.0
    for c, w in (fund.get("country_weights") or {}).items():
        countries[c] = countries.get(c, 0.0) + share * w / 100.0

    unnamed = max(0.0, share * (100.0 - named) / 100.0)
    return issuers, sectors, countries, unnamed


def hhi(weights: dict[str, float]) -> float:
    return round(sum(w * w for w in weights.values()), 1)


def _merge(target: dict[str, float], source: dict[str, float]) -> None:
    for k, v in source.items():
        target[k] = target.get(k, 0.0) + v


def analyse(positions: list[Position]) -> dict:
    total = sum(p.value for p in positions)
    issuers: dict[str, float] = {}
    sectors: dict[str, float] = {}
    countries: dict[str, float] = {}
    unresolved = 0.0

    for p in positions:
        i, s, c, u = _expand(p, total)
        _merge(issuers, i)
        _merge(sectors, s)
        _merge(countries, c)
        unresolved += u

    def top(d: dict[str, float], n: int = 12) -> list[dict]:
        return [
            {"key": k, "weight": round(v, 3)}
            for k, v in sorted(d.items(), key=lambda kv: -kv[1])[:n]
        ]

    return {
        "total_value": round(total, 2),
        "positions": [p.to_dict() for p in positions],
        "issuer_exposure": top(issuers, 15),
        "sector_exposure": top(sectors, 15),
        "country_exposure": top(countries, 15),
        "issuer_hhi": hhi(issuers),
        "sector_hhi": hhi(sectors),
        "country_hhi": hhi(countries),
        "unresolved_weight_pct": round(unresolved, 2),
        "unresolved_note": (
            "Weight inside funds beyond the named top holdings. Sector and country figures "
            "still cover it because those are published for the whole fund."
        ),
        "_issuers": issuers,
        "_sectors": sectors,
        "_countries": countries,
    }


def overlap(a: dict[str, float], b: dict[str, float]) -> float:
    """PRD 32 overlap coefficient: sum of min(weightA, weightB) over normalised weights.

    0 percent means no common exposure. 100 percent means economically identical.
    """
    ta, tb = sum(a.values()), sum(b.values())
    if ta <= 0 or tb <= 0:
        return 0.0
    na = {k: v / ta for k, v in a.items()}
    nb = {k: v / tb for k, v in b.items()}
    return round(sum(min(na.get(k, 0.0), nb.get(k, 0.0)) for k in set(na) | set(nb)) * 100, 1)


def candidate_overlap(candidate_ticker: str, portfolio: dict) -> dict:
    """How much of a candidate's economic exposure Laura already owns."""
    fund = get_fund(candidate_ticker)
    if fund:
        cand: dict[str, float] = {t: w for t, w in
                                  ((str(e[0]), float(e[1])) for e in (fund.get("top_holdings") or []) if len(e) >= 2)}
        cand_sectors = dict(fund.get("sector_weights") or {})
        cand_countries = dict(fund.get("country_weights") or {})
    else:
        cand = {candidate_ticker.upper(): 100.0}
        sec = sector_for(candidate_ticker)
        cand_sectors = {sec: 100.0} if sec else {}
        cand_countries = {"United States": 100.0}

    return {
        "issuer_overlap_pct": overlap(cand, portfolio.get("_issuers", {})),
        "sector_overlap_pct": overlap(cand_sectors, portfolio.get("_sectors", {})),
        "country_overlap_pct": overlap(cand_countries, portfolio.get("_countries", {})),
        "candidate_issuers": [
            {"key": k, "weight": round(v, 2)} for k, v in sorted(cand.items(), key=lambda kv: -kv[1])[:10]
        ],
        "shared_issuers": [
            {
                "key": k,
                "candidate_weight": round(cand.get(k, 0.0), 2),
                "already_held_pct": round(portfolio.get("_issuers", {}).get(k, 0.0), 2),
            }
            for k in sorted(cand, key=lambda x: -cand[x])
            if portfolio.get("_issuers", {}).get(k, 0.0) > 0
        ][:10],
    }


def simulate_trade(positions: list[Position], candidate_ticker: str, candidate_weight_pct: float,
                   sleeve_value: float | None = None) -> dict:
    """Before and after, the comparison PRD 32 requires the app to report.

    `candidate_weight_pct` is the proposed weight of the candidate in the resulting
    portfolio, so existing positions are scaled down to make room for it.
    """
    before = analyse(positions)
    total = before["total_value"] or 0.0
    w = max(0.0, min(99.0, candidate_weight_pct)) / 100.0

    if total <= 0:
        return {"before": before, "after": before, "delta": {}, "overlap": {}}

    # Scale the existing book down so the candidate occupies exactly w of the result.
    scale = (1.0 - w)
    new_positions = [
        Position(p.ticker, p.value * scale, p.role, p.asset_type, p.label) for p in positions
    ]
    existing = next((p for p in new_positions if p.ticker == candidate_ticker.upper()), None)
    added_value = total * w
    if existing:
        existing.value += added_value
    else:
        new_positions.append(Position(candidate_ticker.upper(), added_value, label="Proposed"))

    after = analyse(new_positions)

    def delta(key: str) -> float:
        return round(after[key] - before[key], 1)

    cand_issuer_after = after["_issuers"].get(candidate_ticker.upper())
    return {
        "before": {k: v for k, v in before.items() if not k.startswith("_")},
        "after": {k: v for k, v in after.items() if not k.startswith("_")},
        "delta": {
            "issuer_hhi": delta("issuer_hhi"),
            "sector_hhi": delta("sector_hhi"),
            "country_hhi": delta("country_hhi"),
        },
        "overlap": candidate_overlap(candidate_ticker, before),
        "candidate_weight_pct": round(candidate_weight_pct, 2),
        "largest_lookthrough_issuer": (
            after["issuer_exposure"][0] if after["issuer_exposure"] else None
        ),
        "_after_issuers": after["_issuers"],
        "_after_sectors": after["_sectors"],
    }
