"""Security Quality Scores for funds and fixed income. PRD 18 to 24.

Four models live here because the PRD is explicit that they cannot share one:

    Broad equity ETF        PRD 18, 100 points
    International ETF       PRD 19, 100 points
    Sector or thematic ETF  PRD 20, 100 points
    Bond, Treasury and cash PRD 21 to 24

The broad and international models score underlying fundamental quality by looking
through to the fund's actual holdings and pulling each company's filed figures,
rather than taking the issuer's word for the portfolio's quality.
"""

from __future__ import annotations

import math
from typing import Any

from ..providers import sec
from ..providers.market import RiskProfile
from .normalize import ScoreCard, Source, score_against_bands
from .registry import fund_source, get_fund

ISSUER = Source(
    name="Fund issuer factsheet, transcribed to the local registry",
    source_type="issuer",
    authority_tier=2,
    claim_supported="Expense ratio, holdings, weights and maturity structure",
)
NASDAQ = Source(
    name="Nasdaq market data", url="https://www.nasdaq.com/market-activity",
    source_type="exchange", authority_tier=1,
)
SEC_LOOKTHROUGH = Source(
    name="SEC EDGAR company facts, aggregated across fund holdings",
    url="https://data.sec.gov/api/xbrl/companyfacts/",
    source_type="filing", authority_tier=1,
)


def hhi(weights: list[float]) -> float:
    """Herfindahl-Hirschman index over percentage weights, returned in 0..10000."""
    return sum(w * w for w in weights)


def effective_holdings(weights: list[float]) -> float | None:
    """The number of equally weighted positions that would give the same HHI."""
    h = hhi(weights)
    return (10_000 / h) if h > 0 else None


# --- look-through to underlying companies -----------------------------------------

def lookthrough_fundamentals(top_holdings: list[list], limit: int = 10) -> dict:
    """Weighted fundamentals of the fund's largest holdings, from their own filings.

    PRD 18 category C asks for the underlying fundamental quality of an ETF rather
    than a count of how many names it holds. We resolve each holding against SEC
    EDGAR and weight what comes back by its position size. Foreign holdings without a
    US filing are skipped and the coverage figure reports how much of the sampled
    weight actually resolved.
    """
    rows: list[dict] = []
    sampled = 0.0
    resolved = 0.0
    for entry in (top_holdings or [])[:limit]:
        if not entry or len(entry) < 2:
            continue
        ticker, weight = str(entry[0]), float(entry[1])
        sampled += weight
        f = sec.get_company_fundamentals(ticker)
        if not f or not f.ratios.get("revenue"):
            continue
        resolved += weight
        rows.append({"ticker": ticker, "weight": weight, "ratios": f.ratios, "name": f.name})

    if not rows:
        return {"coverage_pct": 0.0, "sampled_weight": sampled, "holdings": [], "weighted": {}}

    total_w = sum(r["weight"] for r in rows)

    def wavg(key: str) -> float | None:
        pairs = [(r["weight"], r["ratios"].get(key)) for r in rows]
        pairs = [(w, v) for w, v in pairs if v is not None and math.isfinite(v)]
        if not pairs:
            return None
        wsum = sum(w for w, _ in pairs)
        return sum(w * v for w, v in pairs) / wsum if wsum else None

    return {
        "coverage_pct": round(resolved / sampled * 100, 1) if sampled else 0.0,
        "sampled_weight": round(sampled, 2),
        "resolved_weight": round(resolved, 2),
        "holdings_resolved": len(rows),
        "weighted": {
            "revenue_cagr_3y": wavg("revenue_cagr_3y"),
            "operating_income_growth": wavg("operating_income_growth"),
            "roe": wavg("roe"),
            "roic": wavg("roic"),
            "fcf_margin": wavg("fcf_margin"),
            "operating_margin": wavg("operating_margin"),
            "net_debt_to_ebitda": wavg("net_debt_to_ebitda"),
            "interest_coverage": wavg("interest_coverage"),
        },
        "holdings": [
            {"ticker": r["ticker"], "name": r["name"], "weight": r["weight"],
             "roe": r["ratios"].get("roe"), "fcf_margin": r["ratios"].get("fcf_margin"),
             "revenue_cagr_3y": r["ratios"].get("revenue_cagr_3y")}
            for r in rows
        ],
    }


# --- shared metric blocks ----------------------------------------------------------

def _cost_and_liquidity(card: ScoreCard, fund: dict, quote: dict | None, rp: RiskProfile | None,
                        as_of: str, cost_cat: str, liq_cat: str, weights: dict[str, float]) -> None:
    card.measure(
        "expense_ratio", "Expense ratio", weights["expense"], cost_cat,
        fund.get("expense_ratio"),
        bands=[(0.02, 100), (0.05, 94), (0.10, 85), (0.18, 72), (0.30, 55), (0.50, 35), (0.80, 15), (1.2, 4)],
        higher_is_better=False, units="% per year", as_of=as_of, source=ISSUER,
        interpretation="Charged every year Laura holds the fund, which compounds against her over the run to 2033.",
    )
    card.measure(
        "tracking_difference", "Tracking difference", weights["tracking_diff"], cost_cat, None,
        as_of=as_of,
        interpretation="Issuer reported tracking statistics are the tier 1 source and are not yet in the local registry.",
    )
    card.measure(
        "tracking_error", "Tracking error", weights["tracking_err"], cost_cat, None,
        as_of=as_of,
        interpretation="Same gap as tracking difference. Both should be read off the issuer factsheet before a committee decision.",
    )
    card.measure(
        "turnover", "Portfolio turnover", weights["turnover"], cost_cat,
        fund.get("turnover_pct"),
        bands=[(2, 100), (8, 90), (18, 76), (35, 58), (60, 38), (100, 18), (200, 4)],
        higher_is_better=False, units="% per year", as_of=as_of, source=ISSUER,
        interpretation="Turnover creates trading costs inside the fund that never appear in the expense ratio.",
    )

    spread = (quote or {}).get("spread_bps")
    spread_note = (quote or {}).get("spread_note") or ""
    card.measure(
        "bid_ask", "Bid ask spread", weights["spread"], liq_cat, spread,
        bands=[(0.5, 100), (2, 92), (5, 82), (10, 70), (20, 54), (40, 32), (80, 12)],
        higher_is_better=False, units="bps", as_of=as_of, source=NASDAQ,
        interpretation=spread_note or "Both a trading cost and a direct read on how liquid the fund really is.",
    )
    card.measure(
        "aum", "Assets under management", weights["aum"], liq_cat,
        (fund.get("aum_usd") or 0) / 1e9 or None,
        bands=[(0.05, 10), (0.2, 35), (0.5, 55), (2, 72), (10, 86), (50, 96), (200, 100)],
        units="$bn", as_of=as_of, source=ISSUER,
        interpretation="Scale reduces the chance of closure and generally tightens spreads.",
    )
    card.measure(
        "market_depth", "Trading liquidity", weights["depth"], liq_cat,
        None if not rp else (rp.years_covered * 20 if rp.years_covered else None),
        bands=[(5, 20), (20, 45), (40, 62), (60, 76), (80, 88), (100, 96)],
        units="months of price history", as_of=as_of, source=NASDAQ,
        interpretation="Length of continuous trading history, used as a standing proxy until issuer volume data is wired in.",
    )


def _historical_risk(card: ScoreCard, rp: RiskProfile | None, as_of: str, cat: str,
                     w_dd: float, w_sd: float, w_beta: float) -> None:
    card.measure(
        "max_drawdown", "Maximum drawdown", w_dd, cat,
        rp.max_drawdown_pct if rp else None,
        bands=[(-70, 5), (-55, 20), (-42, 36), (-32, 52), (-24, 68), (-17, 82), (-10, 94), (-4, 100)],
        units="%", as_of=as_of, source=NASDAQ,
        interpretation="Worst peak to trough fall over the period on file.",
    )
    card.measure(
        "volatility", "Annualised volatility", w_sd, cat,
        rp.annual_volatility_pct if rp else None,
        bands=[(2, 100), (8, 90), (13, 78), (17, 66), (22, 50), (30, 30), (45, 10)],
        higher_is_better=False, units="%", as_of=as_of, source=NASDAQ,
        interpretation="Dispersion of daily returns, annualised.",
    )
    card.measure(
        "beta", "Beta to the S&P 500", w_beta, cat,
        rp.beta if rp else None,
        bands=[(0.2, 95), (0.6, 88), (0.85, 78), (1.0, 68), (1.2, 52), (1.5, 30), (2.0, 10)],
        higher_is_better=False, units="x", as_of=as_of, source=NASDAQ,
    )


def _underlying_quality(card: ScoreCard, lt: dict, as_of: str, cat: str, weights: dict[str, float]) -> None:
    w = lt.get("weighted", {})
    coverage = lt.get("coverage_pct", 0.0)
    note = (
        f"Weighted across the top holdings that file with the SEC, covering "
        f"{coverage:.0f}% of the sampled weight."
    )
    card.measure(
        "underlying_growth", "Underlying earnings growth", weights["growth"], cat,
        w.get("operating_income_growth") if coverage >= 30 else None,
        bands=[(-20, 10), (-5, 32), (3, 50), (10, 66), (20, 80), (35, 92)],
        units="%", as_of=as_of, source=SEC_LOOKTHROUGH, interpretation=note,
    )
    card.measure(
        "underlying_profitability", "Underlying return on equity", weights["profit"], cat,
        w.get("roe") if coverage >= 30 else None,
        bands=[(0, 8), (6, 30), (12, 50), (18, 66), (26, 80), (40, 93)],
        units="%", as_of=as_of, source=SEC_LOOKTHROUGH, interpretation=note,
    )
    card.measure(
        "underlying_fcf", "Underlying free cash flow margin", weights["fcf"], cat,
        w.get("fcf_margin") if coverage >= 30 else None,
        bands=[(-5, 8), (2, 28), (7, 48), (12, 64), (18, 78), (28, 92)],
        units="%", as_of=as_of, source=SEC_LOOKTHROUGH, interpretation=note,
    )
    card.measure(
        "underlying_balance_sheet", "Underlying balance sheet", weights["balance"], cat,
        w.get("net_debt_to_ebitda") if coverage >= 30 else None,
        bands=[(-1.5, 98), (0, 88), (1, 76), (2, 62), (3, 46), (4.5, 26), (6, 8)],
        higher_is_better=False, units="x net debt to EBITDA",
        as_of=as_of, source=SEC_LOOKTHROUGH, interpretation=note,
    )
    if weights.get("stability"):
        card.measure(
            "underlying_stability", "Underlying earnings stability", weights["stability"], cat,
            w.get("operating_margin") if coverage >= 30 else None,
            bands=[(0, 15), (6, 38), (12, 55), (20, 70), (30, 85), (45, 95)],
            units="% weighted operating margin", as_of=as_of, source=SEC_LOOKTHROUGH,
            interpretation="Margin level is used as the durability proxy across the look-through sample.",
        )


# --- PRD 18: broad equity ETF -----------------------------------------------------

BROAD_CATEGORIES = {
    "methodology": 18.0, "diversification": 22.0, "underlying": 20.0,
    "valuation": 10.0, "cost": 15.0, "liquidity": 10.0, "risk": 5.0,
}
BROAD_LABELS = {
    "methodology": "Methodology and exposure design",
    "diversification": "Diversification and concentration",
    "underlying": "Underlying fundamental quality",
    "valuation": "Valuation",
    "cost": "Cost and implementation efficiency",
    "liquidity": "Liquidity and scale",
    "risk": "Historical risk efficiency",
}


def build_broad_etf(ticker: str, fund: dict, rp: RiskProfile | None, quote: dict | None) -> dict:
    card = ScoreCard("Broad equity ETF SQS", BROAD_CATEGORIES)
    as_of = fund.get("as_of") or ""
    src = fund_source(ticker)
    lt = lookthrough_fundamentals(fund.get("top_holdings", []))

    # A. Methodology and exposure design, 18
    tracks_index = fund.get("index_tracking")
    method_score = 78.0 if tracks_index else 68.0
    evidence = [fund.get("methodology", "")]
    if fund.get("benchmark"):
        evidence.append(f"Benchmark: {fund['benchmark']}.")
    card.qualitative("methodology_quality", "Methodology quality", 8.0, "methodology",
                     method_score, [e for e in evidence if e], source=src, as_of=as_of)
    card.measure(
        "market_coverage", "Market coverage", 4.0, "methodology",
        fund.get("holdings_count"),
        bands=[(50, 25), (200, 50), (500, 68), (1500, 85), (3000, 95), (6000, 100)],
        units="holdings", as_of=as_of, source=src,
        interpretation="How much of the investable market the fund actually reaches.",
    )
    card.measure(
        "rebalancing", "Rebalancing process", 3.0, "methodology",
        fund.get("turnover_pct"),
        bands=[(1, 85), (5, 92), (15, 80), (30, 62), (60, 40), (120, 18)],
        units="% turnover", as_of=as_of, source=src,
        interpretation="Enough turnover to maintain the exposure, not so much that it leaks value in costs.",
    )
    card.qualitative("transparency", "Transparency", 3.0, "methodology",
                     85.0 if tracks_index else 65.0,
                     ["Published index methodology and daily holdings disclosure."] if tracks_index
                     else ["Systematic but actively managed, so the exact selection rules are described rather than published as an index."],
                     source=src, as_of=as_of)

    # B. Diversification and concentration, 22
    # PRD 18 is explicit that a fund with 3,000 stocks can still be concentrated.
    card.measure(
        "top10_concentration", "Top ten concentration", 7.0, "diversification",
        fund.get("top10_weight"),
        bands=[(8, 100), (15, 90), (22, 78), (30, 62), (38, 44), (50, 22), (65, 6)],
        higher_is_better=False, units="%", as_of=as_of, source=src,
        interpretation="The share of Laura's money that ten decisions would move.",
    )
    card.measure(
        "largest_holding", "Largest single holding", 4.0, "diversification",
        fund.get("largest_holding_weight"),
        bands=[(0.5, 100), (1.5, 92), (3, 80), (5, 64), (7, 46), (10, 24), (15, 6)],
        higher_is_better=False, units="%", as_of=as_of, source=src,
    )
    sector_weights = list((fund.get("sector_weights") or {}).values())
    sector_hhi = hhi(sector_weights) if sector_weights else None
    card.measure(
        "sector_concentration", "Sector concentration", 5.0, "diversification",
        sector_hhi,
        bands=[(900, 100), (1200, 90), (1600, 76), (2100, 58), (2800, 38), (4000, 16), (6000, 4)],
        higher_is_better=False, units="HHI", as_of=as_of, source=src,
        interpretation=(
            f"Herfindahl index across {len(sector_weights)} sectors. "
            f"Largest sector is {max(fund['sector_weights'], key=fund['sector_weights'].get)} "
            f"at {max(sector_weights):.1f}%." if sector_weights else ""
        ),
    )
    card.measure(
        "cap_breadth", "Market cap breadth", 3.0, "diversification",
        fund.get("holdings_count"),
        bands=[(100, 30), (500, 55), (1500, 78), (3000, 92), (5000, 100)],
        units="holdings", as_of=as_of, source=src,
    )
    country_weights = list((fund.get("country_weights") or {}).values())
    card.measure(
        "geographic_breadth", "Geographic breadth", 3.0, "diversification",
        hhi(country_weights) if country_weights else None,
        bands=[(800, 100), (1500, 86), (3000, 66), (5000, 44), (7500, 24), (10000, 10)],
        higher_is_better=False, units="HHI", as_of=as_of, source=src,
        interpretation="A single country fund scores 10000 here by construction, which is the point.",
    )

    # C. Underlying fundamental quality, 20
    _underlying_quality(card, lt, as_of, "underlying",
                        {"growth": 5.0, "profit": 5.0, "fcf": 4.0, "balance": 3.0, "stability": 3.0})

    # D. Valuation, 10
    card.measure("forward_pe", "Forward price to earnings", 4.0, "valuation", None, as_of=as_of,
                 interpretation="Aggregate consensus estimates for the portfolio are an issuer or data vendor figure and are not wired in.")
    card.measure(
        "earnings_yield", "Underlying free cash flow margin as a value proxy", 4.0, "valuation",
        lt.get("weighted", {}).get("fcf_margin") if lt.get("coverage_pct", 0) >= 30 else None,
        bands=[(0, 15), (5, 38), (10, 55), (15, 70), (22, 85), (32, 95)],
        units="%", as_of=as_of, source=SEC_LOOKTHROUGH,
        interpretation="Cash generation of the underlying businesses, pending a portfolio level yield from the issuer.",
    )
    card.measure("relative_valuation", "Valuation against category history", 2.0, "valuation", None,
                 as_of=as_of, interpretation="Requires a category valuation history series that is not in the local registry.")

    # E, F. Cost and liquidity
    _cost_and_liquidity(card, fund, quote, rp, as_of, "cost", "liquidity", {
        "expense": 5.0, "tracking_diff": 5.0, "tracking_err": 3.0, "turnover": 2.0,
        "spread": 4.0, "aum": 3.0, "depth": 3.0,
    })

    # G. Historical risk efficiency, 5
    _historical_risk(card, rp, as_of, "risk", 2.0, 2.0, 1.0)

    result = card.finalise()
    result["category_labels"] = BROAD_LABELS
    result["lookthrough"] = lt
    result["derived"] = {
        "sector_hhi": sector_hhi,
        "country_hhi": hhi(country_weights) if country_weights else None,
        "effective_holdings": effective_holdings(
            [w for _, w in (fund.get("top_holdings") or [])]
        ),
    }
    result["overlays"] = []
    return result


# --- PRD 19: international equity ETF ---------------------------------------------

INTL_CATEGORIES = {
    "country_div": 12.0, "sector_div": 8.0, "holdings_conc": 8.0, "dm_em": 5.0,
    "underlying": 15.0, "growth": 10.0, "valuation": 10.0, "currency": 8.0,
    "political": 5.0, "cost": 8.0, "liquidity": 6.0, "risk": 5.0,
}
INTL_LABELS = {
    "country_div": "Country diversification", "sector_div": "Sector diversification",
    "holdings_conc": "Holdings concentration", "dm_em": "Developed and emerging mix",
    "underlying": "Underlying fundamental quality", "growth": "Growth",
    "valuation": "Valuation", "currency": "Currency risk structure",
    "political": "Political and regulatory diversification", "cost": "Expense and tracking",
    "liquidity": "Liquidity and scale", "risk": "Historical risk",
}


def build_international_etf(ticker: str, fund: dict, rp: RiskProfile | None, quote: dict | None) -> dict:
    card = ScoreCard("International equity ETF SQS", INTL_CATEGORIES)
    as_of = fund.get("as_of") or ""
    src = fund_source(ticker)
    lt = lookthrough_fundamentals(fund.get("top_holdings", []))

    countries = fund.get("country_weights") or {}
    cweights = list(countries.values())
    country_hhi = hhi(cweights) if cweights else None
    card.measure(
        "country_diversification", "Country diversification", 12.0, "country_div",
        country_hhi,
        bands=[(700, 100), (1000, 90), (1400, 78), (2000, 62), (3000, 42), (5000, 20), (8000, 5)],
        higher_is_better=False, units="HHI", as_of=as_of, source=src,
        interpretation=(
            f"Across {len(countries)} country lines. Largest is "
            f"{max(countries, key=countries.get)} at {max(cweights):.1f}%." if countries else ""
        ),
    )
    sweights = list((fund.get("sector_weights") or {}).values())
    card.measure(
        "sector_diversification", "Sector diversification", 8.0, "sector_div",
        hhi(sweights) if sweights else None,
        bands=[(900, 100), (1200, 90), (1600, 76), (2100, 58), (2800, 38), (4000, 16)],
        higher_is_better=False, units="HHI", as_of=as_of, source=src,
    )
    card.measure(
        "holdings_concentration", "Holdings concentration", 8.0, "holdings_conc",
        fund.get("top10_weight"),
        bands=[(6, 100), (10, 92), (15, 82), (22, 66), (30, 46), (42, 22), (60, 5)],
        higher_is_better=False, units="% in top ten", as_of=as_of, source=src,
    )
    em = fund.get("emerging_weight")
    card.measure(
        "developed_emerging", "Developed and emerging composition", 5.0, "dm_em", em,
        bands=[(0, 55), (10, 78), (22, 92), (35, 80), (60, 55), (100, 32)],
        units="% emerging", as_of=as_of, source=src,
        interpretation=(
            "A moderate emerging weight adds genuine diversification. An all emerging fund "
            "concentrates political and currency risk rather than spreading it."
        ),
    )

    _underlying_quality(card, lt, as_of, "underlying",
                        {"growth": 4.0, "profit": 5.0, "fcf": 3.0, "balance": 3.0, "stability": 0.0})
    card.measure(
        "growth", "Portfolio growth", 10.0, "growth",
        lt.get("weighted", {}).get("revenue_cagr_3y") if lt.get("coverage_pct", 0) >= 30 else None,
        bands=[(-5, 12), (0, 32), (4, 50), (8, 66), (14, 82), (22, 94)],
        units="% weighted revenue CAGR", as_of=as_of, source=SEC_LOOKTHROUGH,
        interpretation="Many non US holdings do not file with the SEC, so coverage here is usually partial and the data confidence score reflects that.",
    )
    card.measure(
        "valuation", "Valuation", 10.0, "valuation",
        lt.get("weighted", {}).get("fcf_margin") if lt.get("coverage_pct", 0) >= 30 else None,
        bands=[(0, 20), (5, 42), (10, 58), (16, 72), (24, 86), (34, 95)],
        units="% weighted FCF margin", as_of=as_of, source=SEC_LOOKTHROUGH,
    )

    hedged = fund.get("currency_hedged")
    card.qualitative(
        "currency", "Currency risk structure", 8.0, "currency",
        45.0 if not hedged else 72.0,
        [
            "The fund is unhedged, so Laura carries the full move in the dollar against these currencies."
            if not hedged else "The fund hedges its currency exposure back to the dollar.",
            "PRD 19 requires currency risk to be shown explicitly rather than buried inside volatility.",
        ],
        source=src, as_of=as_of,
    )
    card.measure(
        "political", "Political and regulatory diversification", 5.0, "political",
        country_hhi,
        bands=[(700, 100), (1200, 85), (2000, 66), (3500, 42), (6000, 18), (9000, 5)],
        higher_is_better=False, units="HHI", as_of=as_of, source=src,
    )

    _cost_and_liquidity(card, fund, quote, rp, as_of, "cost", "liquidity", {
        "expense": 4.0, "tracking_diff": 2.0, "tracking_err": 1.0, "turnover": 1.0,
        "spread": 3.0, "aum": 2.0, "depth": 1.0,
    })
    _historical_risk(card, rp, as_of, "risk", 2.0, 2.0, 1.0)

    result = card.finalise()
    result["category_labels"] = INTL_LABELS
    result["lookthrough"] = lt
    result["derived"] = {"country_hhi": country_hhi, "emerging_weight": em, "currency_hedged": hedged}
    result["overlays"] = [
        "Currency exposure is scored as its own category rather than being absorbed into volatility, per PRD 19."
    ]
    return result


# --- PRD 20: sector or thematic ETF -----------------------------------------------

THEMATIC_CATEGORIES = {
    "theme": 20.0, "underlying": 20.0, "runway": 15.0, "valuation": 15.0,
    "stock_conc": 10.0, "sector_conc": 5.0, "cost": 5.0, "liquidity": 5.0, "risk": 5.0,
}
THEMATIC_LABELS = {
    "theme": "Theme purity and methodology", "underlying": "Underlying company quality",
    "runway": "Growth runway", "valuation": "Valuation", "stock_conc": "Stock concentration",
    "sector_conc": "Sector concentration", "cost": "Expense ratio", "liquidity": "Liquidity",
    "risk": "Historical risk",
}


def build_thematic_etf(ticker: str, fund: dict, rp: RiskProfile | None, quote: dict | None) -> dict:
    card = ScoreCard("Sector or thematic ETF SQS", THEMATIC_CATEGORIES)
    as_of = fund.get("as_of") or ""
    src = fund_source(ticker)
    lt = lookthrough_fundamentals(fund.get("top_holdings", []))

    card.qualitative(
        "theme_purity", "Theme purity and methodology", 20.0, "theme", 70.0,
        [fund.get("methodology", ""), f"Stated theme: {fund.get('theme', 'not stated')}."],
        source=src, as_of=as_of,
    )
    _underlying_quality(card, lt, as_of, "underlying",
                        {"growth": 6.0, "profit": 6.0, "fcf": 4.0, "balance": 4.0, "stability": 0.0})
    card.measure(
        "runway", "Growth runway", 15.0, "runway",
        lt.get("weighted", {}).get("revenue_cagr_3y") if lt.get("coverage_pct", 0) >= 30 else None,
        bands=[(-5, 10), (2, 30), (8, 50), (15, 68), (25, 84), (40, 95)],
        units="% weighted revenue CAGR", as_of=as_of, source=SEC_LOOKTHROUGH,
    )
    card.measure(
        "valuation", "Valuation", 15.0, "valuation",
        lt.get("weighted", {}).get("fcf_margin") if lt.get("coverage_pct", 0) >= 30 else None,
        bands=[(0, 18), (5, 38), (11, 55), (18, 70), (26, 84), (36, 94)],
        units="% weighted FCF margin", as_of=as_of, source=SEC_LOOKTHROUGH,
    )
    # PRD 20: a thematic fund cannot earn a broad fund's diversification score simply
    # for holding fifty names.
    card.measure(
        "stock_concentration", "Stock concentration", 10.0, "stock_conc",
        fund.get("top10_weight"),
        bands=[(20, 95), (30, 82), (40, 68), (50, 52), (62, 34), (75, 16), (90, 4)],
        higher_is_better=False, units="% in top ten", as_of=as_of, source=src,
    )
    sweights = list((fund.get("sector_weights") or {}).values())
    card.measure(
        "sector_concentration", "Sector concentration", 5.0, "sector_conc",
        hhi(sweights) if sweights else None,
        bands=[(1500, 80), (3000, 60), (5000, 42), (7500, 24), (10000, 10)],
        higher_is_better=False, units="HHI", as_of=as_of, source=src,
        interpretation="A single sector fund reaches 10000 by design. The score records the fact rather than forgiving it.",
    )
    card.measure(
        "expense_ratio", "Expense ratio", 5.0, "cost", fund.get("expense_ratio"),
        bands=[(0.05, 100), (0.12, 88), (0.22, 72), (0.35, 55), (0.55, 34), (0.85, 14)],
        higher_is_better=False, units="% per year", as_of=as_of, source=src,
    )
    card.measure(
        "liquidity", "Liquidity", 5.0, "liquidity", (quote or {}).get("spread_bps"),
        bands=[(0.5, 100), (2, 90), (5, 78), (12, 62), (25, 42), (50, 18)],
        higher_is_better=False, units="bps", as_of=as_of, source=NASDAQ,
        interpretation=(quote or {}).get("spread_note") or "",
    )
    _historical_risk(card, rp, as_of, "risk", 2.0, 2.0, 1.0)

    result = card.finalise()
    result["category_labels"] = THEMATIC_LABELS
    result["lookthrough"] = lt
    result["derived"] = {"theme": fund.get("theme")}
    result["overlays"] = [
        "Thematic funds receive a stronger portfolio overlap test than broad funds, applied in the look-through engine."
    ]
    return result


# --- PRD 21 to 24: fixed income and cash ------------------------------------------

BOND_CATEGORIES = {
    "credit": 30.0, "yield": 18.0, "structure": 18.0, "rates": 12.0,
    "liquidity": 10.0, "reinvestment": 7.0, "issuer_div": 5.0,
}
BOND_LABELS = {
    "credit": "Credit and payment quality", "yield": "Yield and relative value",
    "structure": "Structural certainty", "rates": "Interest rate risk",
    "liquidity": "Liquidity", "reinvestment": "Reinvestment and inflation risk",
    "issuer_div": "Issuer diversification",
}

CASH_CATEGORIES = {
    "preservation": 35.0, "yield": 25.0, "liquidity": 20.0,
    "maturity": 10.0, "counterparty": 5.0, "friction": 5.0,
}
CASH_LABELS = {
    "preservation": "Capital preservation", "yield": "Yield", "liquidity": "Liquidity",
    "maturity": "Maturity certainty", "counterparty": "Counterparty and issuer quality",
    "friction": "Transaction friction",
}


def build_bond(ticker: str, fund: dict, rp: RiskProfile | None, quote: dict | None,
               target_year: int | None = None) -> dict:
    """PRD 21 and 22. The bond model prioritises payment certainty, not maximum yield."""
    card = ScoreCard("Fixed income SQS", BOND_CATEGORIES)
    as_of = fund.get("as_of") or ""
    src = fund_source(ticker)
    is_treasury = "treasury" in (fund.get("credit_quality") or "").lower()
    has_maturity = bool(fund.get("has_maturity_date"))
    maturity_year = fund.get("maturity_year")

    card.qualitative(
        "credit_quality", "Credit quality", 15.0, "credit",
        98.0 if is_treasury else 70.0,
        [f"Stated credit quality: {fund.get('credit_quality', 'not stated')}.",
         "US Treasury obligations receive the model's highest sovereign credit treatment."
         if is_treasury else "Not a direct sovereign obligation, so issuer strength carries weight."],
        source=src, as_of=as_of,
    )
    card.qualitative(
        "issuer_strength", "Issuer financial strength", 5.0, "credit",
        97.0 if is_treasury else 65.0,
        ["Backed by the full faith and credit of the United States."] if is_treasury
        else ["Issuer strength should be read from the latest rating action before purchase."],
        source=src, as_of=as_of,
    )
    card.qualitative(
        "seniority", "Seniority and structural protection", 5.0, "credit",
        95.0 if is_treasury else 60.0,
        ["Direct sovereign obligation with no structural subordination."] if is_treasury else [],
        source=src, as_of=as_of,
    )
    card.qualitative(
        "rating_outlook", "Rating outlook and deterioration risk", 5.0, "credit",
        88.0 if is_treasury else 55.0,
        ["No material near term deterioration risk for a Treasury obligation held to maturity."]
        if is_treasury else [],
        source=src, as_of=as_of,
    )

    ytm = fund.get("sec_yield_pct")
    card.measure(
        "ytm", "Yield to maturity", 8.0, "yield", ytm,
        bands=[(0.5, 10), (1.5, 28), (2.5, 45), (3.5, 62), (4.5, 78), (6, 92), (8, 100)],
        units="%", as_of=as_of, source=src,
        interpretation="The yield is what secures the payment. It is not the thing being maximised.",
    )
    # A government bond has no spread over a government bond: the measure is
    # undefined here, not zero. Feeding it a literal 0.0 ran it down the band that
    # rewards a little credit pickup and marked a Treasury down to 60 for having no
    # credit risk, which is backwards. Under the PRD 60 rule a not-applicable metric
    # hands its weight back to the rest of its own category instead.
    card.measure(
        "spread", "Spread over comparable government", 6.0, "yield", None,
        bands=[(0, 60), (0.5, 72), (1.2, 82), (2.5, 70), (5, 40)],
        units="pp", as_of=as_of, source=src,
        not_applicable=is_treasury,
        na_reason="A Treasury is the reference rate, so it has no spread over itself. "
                  "The weight moves to the other yield measures.",
        interpretation="" if is_treasury else "",
    )
    card.measure(
        "ytw", "Yield to worst", 4.0, "yield",
        ytm if (is_treasury and not fund.get("callable")) else None,
        bands=[(0.5, 10), (1.5, 28), (2.5, 45), (3.5, 62), (4.5, 78), (6, 92)],
        units="%", as_of=as_of, source=src,
        interpretation="With no call feature, yield to worst equals yield to maturity." if is_treasury and not fund.get("callable") else "",
    )

    # Structural certainty is where a defined maturity fund separates from a rolling one.
    if has_maturity and maturity_year and target_year:
        gap = abs(maturity_year - target_year)
        maturity_score = score_against_bands(float(gap), [(0, 100), (1, 72), (2, 45), (3, 22), (5, 6)])
        maturity_note = (
            f"Terminates {fund.get('termination_date')}, against a required payment at the start of {target_year}. "
            + ("The proceeds arrive before the payment is due." if maturity_year <= target_year
               else "The fund terminates after the payment is due, which is a Red Gate condition for a liability matcher.")
        )
    elif has_maturity:
        maturity_score = 85.0
        maturity_note = f"Defined termination date of {fund.get('termination_date')}."
    else:
        maturity_score = 12.0
        maturity_note = (
            "No maturity date. The fund rolls its holdings continuously, so its value on any "
            "particular future date is unknown. PRD 23 treats this as disqualifying for liability matching."
        )
    card.qualitative("maturity_structure", "Maturity structure", 8.0, "structure",
                     maturity_score, [maturity_note], source=src, as_of=as_of)
    card.qualitative("call_risk", "Call risk", 5.0, "structure",
                     95.0 if not fund.get("callable") else 40.0,
                     ["Not callable, so the expected cash flow cannot be withdrawn early."]
                     if not fund.get("callable") else ["Callable, which can remove the cash flow before it is needed."],
                     source=src, as_of=as_of)
    card.qualitative("prepayment", "Prepayment and sinking fund features", 3.0, "structure",
                     92.0 if is_treasury else 55.0,
                     ["Treasury notes and bonds carry no prepayment or sinking fund features."] if is_treasury else [],
                     source=src, as_of=as_of)
    card.qualitative("currency", "Currency", 2.0, "structure", 100.0,
                     ["Denominated in US dollars, matching the currency of Laura's obligation."],
                     source=src, as_of=as_of)

    duration = fund.get("average_duration_years")
    if target_year:
        years_to = max(0.0, target_year - 2026)
        mismatch = abs((duration or 0) - years_to)
        dur_score = score_against_bands(mismatch, [(0, 100), (1, 84), (2, 64), (4, 38), (7, 14), (12, 4)])
        dur_note = (
            f"Duration of {duration:.1f} years against {years_to:.0f} years until the {target_year} payment. "
            "Matching duration to the horizon is what immunises the payment against rate moves."
            if duration else ""
        )
    else:
        dur_score = score_against_bands(duration or 0, [(0.2, 92), (2, 84), (5, 70), (8, 55), (12, 36), (18, 15), (25, 5)])
        dur_note = "Scored on its own terms because no target payment year was supplied."
    card.qualitative("duration", "Duration", 8.0, "rates", dur_score, [dur_note] if dur_note else [],
                     source=src, as_of=as_of)
    card.qualitative("convexity", "Convexity", 2.0, "rates", 70.0 if is_treasury else 55.0,
                     ["Standard positive convexity for a non callable government bond."] if is_treasury else [],
                     source=src, as_of=as_of)
    card.measure(
        "rate_sensitivity", "Rate sensitivity", 2.0, "rates",
        rp.annual_volatility_pct if rp else None,
        bands=[(0.5, 100), (2, 90), (4, 76), (7, 58), (11, 36), (16, 14)],
        higher_is_better=False, units="% annualised volatility", as_of=as_of, source=NASDAQ,
    )

    card.measure(
        "bid_ask", "Bid ask spread", 6.0, "liquidity", (quote or {}).get("spread_bps"),
        bands=[(0.5, 100), (2, 90), (5, 78), (12, 60), (25, 38), (50, 14)],
        higher_is_better=False, units="bps", as_of=as_of, source=NASDAQ,
        interpretation=(quote or {}).get("spread_note") or "",
    )
    card.measure(
        "issue_size", "Issue size and trading activity", 4.0, "liquidity",
        (fund.get("aum_usd") or 0) / 1e9 or None,
        bands=[(0.05, 20), (0.15, 45), (0.4, 62), (1.5, 78), (8, 92), (40, 100)],
        units="$bn", as_of=as_of, source=src,
    )

    card.qualitative(
        "reinvestment_risk", "Reinvestment risk", 4.0, "reinvestment",
        78.0 if has_maturity else 45.0,
        ["Coupons must be reinvested at unknown future rates, but the principal repayment is dated."]
        if has_maturity else ["Both coupon and principal timing are undefined, so reinvestment risk is continuous."],
        source=src, as_of=as_of,
    )
    card.qualitative(
        "inflation", "Real return exposure", 3.0, "reinvestment", 40.0,
        ["Nominal instrument. Laura's ten payments are fixed at $50,000 and are not inflation adjusted "
         "for competition purposes, so a nominal bond matches the obligation it is funding."],
        source=src, as_of=as_of,
    )
    card.measure(
        "issuer_diversification", "Issuer diversification", 5.0, "issuer_div",
        float(fund.get("holdings_count") or 0) or None,
        bands=[(1, 45), (5, 62), (12, 75), (40, 86), (200, 95), (2000, 100)],
        units="holdings", as_of=as_of, source=src,
        interpretation="Single issuer concentration is acceptable when the issuer is the US Treasury." if is_treasury else "",
    )

    result = card.finalise()
    result["category_labels"] = BOND_LABELS
    result["derived"] = {
        "has_maturity_date": has_maturity,
        "maturity_year": maturity_year,
        "termination_date": fund.get("termination_date"),
        "duration_years": duration,
        "sec_yield_pct": ytm,
        "is_treasury": is_treasury,
        "target_year": target_year,
    }
    result["overlays"] = (
        ["Defined maturity structure: this fund terminates and distributes, so it can carry a dated liability."]
        if has_maturity else
        ["Perpetual structure: PRD 23 requires a Red Gate review or failure if this is proposed as a liability matcher."]
    )
    result["lookthrough"] = {"coverage_pct": 0.0, "holdings": [], "weighted": {}}
    return result


def build_cash(ticker: str, fund: dict, rp: RiskProfile | None, quote: dict | None) -> dict:
    """PRD 24. Cash and Treasury bill model."""
    card = ScoreCard("Cash and Treasury bill SQS", CASH_CATEGORIES)
    as_of = fund.get("as_of") or ""
    src = fund_source(ticker)
    is_treasury = "treasury" in (fund.get("credit_quality") or "").lower()

    card.measure(
        "preservation", "Capital preservation", 35.0, "preservation",
        rp.max_drawdown_pct if rp else None,
        bands=[(-5, 20), (-2.5, 50), (-1.2, 75), (-0.6, 90), (-0.25, 97), (-0.05, 100)],
        units="% maximum drawdown", as_of=as_of, source=NASDAQ,
        interpretation="The whole job of this sleeve is that the money is there when it is needed.",
    )
    card.measure(
        "yield", "Yield", 25.0, "yield", fund.get("sec_yield_pct"),
        bands=[(0.1, 10), (1, 30), (2, 48), (3, 64), (4, 80), (5, 92), (6.5, 100)],
        units="%", as_of=as_of, source=src,
    )
    card.measure(
        "liquidity", "Liquidity", 20.0, "liquidity", (quote or {}).get("spread_bps"),
        bands=[(0.3, 100), (1, 94), (3, 84), (7, 68), (15, 46), (30, 20)],
        higher_is_better=False, units="bps", as_of=as_of, source=NASDAQ,
        interpretation=(quote or {}).get("spread_note") or "",
    )
    card.measure(
        "maturity_certainty", "Maturity certainty", 10.0, "maturity",
        fund.get("average_maturity_years"),
        bands=[(0.05, 100), (0.25, 94), (0.6, 84), (1.2, 68), (2.5, 44), (5, 18)],
        higher_is_better=False, units="years", as_of=as_of, source=src,
    )
    card.qualitative(
        "counterparty", "Counterparty and issuer quality", 5.0, "counterparty",
        97.0 if is_treasury else 65.0,
        ["Direct US Treasury obligations."] if is_treasury else [],
        source=src, as_of=as_of,
    )
    card.measure(
        "friction", "Transaction friction", 5.0, "friction", fund.get("expense_ratio"),
        bands=[(0.02, 100), (0.06, 90), (0.10, 80), (0.18, 62), (0.30, 38), (0.5, 15)],
        higher_is_better=False, units="% per year", as_of=as_of, source=src,
    )

    result = card.finalise()
    result["category_labels"] = CASH_LABELS
    result["derived"] = {"sec_yield_pct": fund.get("sec_yield_pct"), "is_treasury": is_treasury}
    result["overlays"] = []
    result["lookthrough"] = {"coverage_pct": 0.0, "holdings": [], "weighted": {}}
    return result
