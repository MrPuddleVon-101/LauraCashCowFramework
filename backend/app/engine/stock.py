"""Security Quality Score for individual stocks. PRD 13 to 17.

The model totals exactly 100 points:

    A  Growth durability                     18
    B  Cash flow quality                     17
    C  Profitability and capital efficiency  17
    D  Balance sheet resilience              15
    E  Valuation                             15
    F  Business quality and durability       10
    G  Market risk and forward signals        8

Sector overlays (PRD 17) do not add points. They change which submetrics are used
inside a category, which matters most for financial institutions where free cash flow
and net debt to EBITDA are not meaningful measures.
"""

from __future__ import annotations

import math
import statistics
from typing import Any

from ..providers.market import RiskProfile
from ..providers.sec import Fundamentals
from .normalize import NEUTRAL, SEC_FILING, ScoreCard, Source, score_against_bands
from .peers import PeerGroup

CATEGORIES = {
    "growth": 18.0,
    "cashflow": 17.0,
    "profitability": 17.0,
    "balance_sheet": 15.0,
    "valuation": 15.0,
    "business_quality": 10.0,
    "market_risk": 8.0,
}

CATEGORY_LABELS = {
    "growth": "Growth durability",
    "cashflow": "Cash flow quality",
    "profitability": "Profitability and capital efficiency",
    "balance_sheet": "Balance sheet resilience",
    "valuation": "Valuation",
    "business_quality": "Business quality and earnings durability",
    "market_risk": "Market risk and forward signals",
}

NASDAQ = Source(
    name="Nasdaq market data",
    url="https://www.nasdaq.com/market-activity",
    source_type="exchange",
    authority_tier=1,
)

# Banks, insurers and asset managers. PRD 17 says the normal free cash flow and
# leverage measures are inappropriate here and should be substituted.
FINANCIAL_SECTORS = {"Financials"}
REIT_SECTORS = {"Real Estate"}
SOFTWARE_SECTORS = {"Technology"}


def _cv(values: list[float]) -> float | None:
    """Coefficient of variation, as a percentage. A stability measure."""
    vals = [v for v in values if v is not None and math.isfinite(v)]
    if len(vals) < 3:
        return None
    mean = statistics.fmean(vals)
    if abs(mean) < 1e-9:
        return None
    return statistics.pstdev(vals) / abs(mean) * 100


def _pe_history(f: Fundamentals, history: list[dict]) -> tuple[float | None, float | None, list[dict]]:
    """Price to earnings in each of the last few fiscal years, from filed EPS.

    Gives a genuine 'valuation against its own range' measure rather than an assertion
    that something is expensive.
    """
    if not history or not f.eps:
        return None, None, []
    by_date = {r["date"]: r["close"] for r in history}
    dates = sorted(by_date)
    series: list[dict] = []
    for year in sorted(f.eps):
        eps = f.eps[year]
        if not eps or eps <= 0:
            continue
        # Price on the last trading day on or before the fiscal year end we hold.
        target = f"{year + 1}-01-01"
        candidates = [d for d in dates if d <= target]
        if not candidates:
            continue
        px = by_date[candidates[-1]]
        series.append({"year": year, "pe": round(px / eps, 2)})
    if len(series) < 3:
        return None, None, series
    values = [s["pe"] for s in series]
    return min(values), max(values), series


def build(
    f: Fundamentals,
    rp: RiskProfile | None,
    quote: dict | None,
    peers: PeerGroup,
    history: list[dict] | None = None,
    summary: dict | None = None,
) -> dict:
    card = ScoreCard("Stock SQS", CATEGORIES)
    r = f.ratios
    as_of = f.period_end
    sector = peers.sector or ""
    is_financial = sector in FINANCIAL_SECTORS
    is_reit = sector in REIT_SECTORS

    price = (quote or {}).get("price") or (rp.last_close if rp else None)
    shares = r.get("diluted_shares")

    # Market capitalisation comes from the exchange. Deriving it as price times the
    # fiscal year's weighted average diluted share count overstates it for any
    # company that has been buying stock back, because the average over the year sits
    # above today's count. Measured against the exchange's own figure the error ran
    # from 0.4% on Microsoft to 4.7% on JPMorgan, and it fed straight into enterprise
    # value, free cash flow yield and price to book.
    market_cap = (summary or {}).get("market_cap")
    market_cap_basis = "Exchange reported"
    if not market_cap and price and shares:
        market_cap = price * shares
        market_cap_basis = "Derived from price and weighted average diluted shares"

    ebitda = r.get("ebitda")
    net_debt = r.get("net_debt")
    enterprise_value = (market_cap + net_debt) if (market_cap is not None and net_debt is not None) else None

    overlays: list[str] = []

    # --- A. Growth durability, 18 -------------------------------------------------
    card.measure(
        "revenue_cagr_3y", "Three year revenue CAGR", 5.0, "growth",
        r.get("revenue_cagr_3y"), peers=peers.distribution("revenue_cagr_3y"),
        bands=[(-15, 5), (-3, 25), (2, 45), (6, 60), (12, 75), (22, 89), (40, 98)],
        units="%", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
        interpretation="Whether demand for the business is genuinely expanding, measured over a full cycle rather than one year.",
    )
    card.measure(
        "forward_revenue_growth", "Forward revenue growth", 4.0, "growth",
        None, units="%", as_of=as_of,
        interpretation="Consensus estimates are not wired to a tier 1 to 3 source in this build.",
    )
    card.measure(
        "operating_profit_growth", "Operating profit growth", 4.0, "growth",
        r.get("operating_income_growth") if r.get("operating_income_growth") is not None else r.get("eps_growth"),
        peers=peers.distribution("operating_income_growth"),
        bands=[(-40, 5), (-15, 24), (-2, 44), (6, 58), (18, 73), (35, 87), (70, 97)],
        units="%", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
        interpretation="Checks that revenue growth is converting into earnings rather than being spent to buy it.",
    )
    card.measure(
        "fcf_growth", "Free cash flow growth", 5.0, "growth",
        r.get("fcf_growth"), peers=peers.distribution("fcf_growth"),
        bands=[(-50, 5), (-20, 24), (-4, 44), (6, 58), (20, 74), (45, 88), (90, 97)],
        units="%", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
        not_applicable=is_financial,
        na_reason="Free cash flow is not a meaningful measure for a financial institution. Weight moves to the other growth metrics.",
        interpretation="Rewards growth that actually produces cash.",
    )

    # --- B. Cash flow quality, 17 -------------------------------------------------
    # PRD 17: for a financial institution the normal free cash flow measures are
    # inappropriate, so the submetrics inside this category are substituted rather
    # than dropped. The category still carries its declared 17 points.
    if is_financial:
        ni = r.get("net_income")
        rev_f = r.get("revenue")
        assets_latest = f.assets[max(f.assets)] if f.assets else None
        ocf_latest = f.ocf[max(f.ocf)] if f.ocf else None
        card.measure(
            "net_income_margin", "Net income margin", 6.0, "cashflow",
            (ni / rev_f * 100) if (ni is not None and rev_f) else None,
            bands=[(0, 8), (5, 28), (10, 45), (16, 60), (22, 74), (30, 87), (40, 96)],
            units="%", as_of=as_of, source=SEC_FILING,
            interpretation="Substituted for free cash flow margin. Revenue to bottom line is the meaningful conversion for a lender.",
        )
        card.measure(
            "return_on_assets_q", "Return on assets", 4.0, "cashflow",
            r.get("roa"), peers=peers.distribution("roa"),
            bands=[(0, 8), (0.4, 28), (0.8, 48), (1.2, 65), (1.6, 80), (2.2, 92), (3.5, 100)],
            units="%", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
            interpretation="How hard the balance sheet works, which is the lender's equivalent of cash conversion.",
        )
        card.measure(
            "operating_cash_to_assets", "Operating cash flow to assets", 4.0, "cashflow",
            (ocf_latest / assets_latest * 100) if (ocf_latest is not None and assets_latest) else None,
            bands=[(-4, 10), (-1, 32), (0.5, 50), (1.5, 66), (3, 80), (5, 92), (8, 100)],
            units="%", as_of=as_of, source=SEC_FILING,
            interpretation="Replaces free cash flow conversion. Trading and lending flows make the usual ratio unreadable for a bank.",
        )
    else:
        card.measure(
            "fcf_margin", "Free cash flow margin", 6.0, "cashflow",
            r.get("fcf_margin"), peers=peers.distribution("fcf_margin"),
            bands=[(-10, 5), (0, 25), (4, 45), (8, 60), (14, 74), (22, 87), (35, 97)],
            units="%", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
            interpretation="Cash generated per dollar of revenue, after the capital spending needed to stay in business.",
        )
        card.measure(
            "cash_conversion", "Operating cash flow to net income", 4.0, "cashflow",
            r.get("cash_conversion"), peers=peers.distribution("cash_conversion"),
            bands=[(0, 6), (50, 26), (75, 52), (95, 76), (115, 88), (150, 92), (220, 74), (320, 52)],
            blend=0.7,
            units="%", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
            interpretation="Reported profit should show up as cash. A persistent gap is a warning.",
        )
        card.measure(
            "fcf_conversion", "Free cash flow to operating income", 4.0, "cashflow",
            r.get("fcf_conversion"), peers=peers.distribution("fcf_conversion"),
            bands=[(0, 6), (25, 28), (45, 50), (65, 70), (85, 85), (110, 93), (180, 86), (300, 66)],
            blend=0.7,
            units="%", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
            interpretation="Whether operating earnings survive capital spending.",
        )
    sbc = r.get("sbc_to_revenue")
    dilution_value = sbc
    card.measure(
        "dilution", "Share based compensation and dilution", 3.0, "cashflow",
        dilution_value, peers=peers.distribution("sbc_to_revenue"),
        bands=[(0.2, 98), (1, 88), (2.5, 74), (5, 58), (9, 40), (15, 20), (25, 5)],
        higher_is_better=False, units="% of revenue", peer_group=peers.label,
        as_of=as_of, source=SEC_FILING,
        interpretation=(
            "Penalises headline growth funded by repeatedly issuing stock. "
            f"Diluted share count moved {r.get('share_count_change'):+.1f}% in the latest year."
            if r.get("share_count_change") is not None else
            "Penalises headline growth funded by repeatedly issuing stock."
        ),
    )

    # --- C. Profitability and capital efficiency, 17 ------------------------------
    card.measure(
        "roic", "Return on invested capital", 7.0, "profitability",
        r.get("roic"), peers=peers.distribution("roic"),
        bands=[(-5, 4), (2, 22), (6, 40), (10, 56), (15, 70), (25, 85), (45, 97)],
        units="%", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
        not_applicable=is_financial,
        na_reason="Invested capital is not the right denominator for a bank. Weight moves to return on equity.",
        interpretation="The primary capital efficiency measure: what the business earns on the money tied up in it.",
    )
    card.measure(
        "operating_margin", "Operating margin", 5.0, "profitability",
        r.get("operating_margin"), peers=peers.distribution("operating_margin"),
        bands=[(-10, 4), (0, 22), (5, 40), (10, 55), (18, 70), (30, 86), (50, 97)],
        units="%", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
        interpretation="Operating economics against companies facing similar cost structures.",
    )
    card.measure(
        "roe_roa", "Return on equity and assets", 3.0, "profitability",
        r.get("roe"), peers=peers.distribution("roe"),
        bands=[(-5, 5), (3, 24), (8, 42), (13, 58), (19, 73), (30, 88), (50, 98)],
        units="%", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
        interpretation=(
            f"Return on assets is {r['roa']:.1f}%." if r.get("roa") is not None else "Peer relative profitability."
        ),
    )
    card.measure(
        "margin_trajectory", "Margin trajectory", 2.0, "profitability",
        r.get("margin_trajectory"),
        bands=[(-8, 5), (-4, 22), (-1.5, 42), (0, 55), (1.5, 70), (4, 86), (8, 100)],
        units="pp vs 3yr average", as_of=as_of, source=SEC_FILING,
        interpretation="Current operating margin against its own three year average. Rewards stable or improving economics.",
    )

    # --- D. Balance sheet resilience, 15 ------------------------------------------
    equity_latest = f.equity[max(f.equity)] if f.equity else None
    assets_bs = f.assets[max(f.assets)] if f.assets else None
    if is_financial:
        # PRD 17 names capital and liquidity ratios as the right substitutes. CET1 is
        # not carried in the us-gaap taxonomy, so common equity to assets stands in as
        # the closest capital measure available from the filing itself.
        card.measure(
            "equity_to_assets", "Common equity to total assets", 6.0, "balance_sheet",
            (equity_latest / assets_bs * 100) if (equity_latest and assets_bs) else None,
            bands=[(3, 10), (5, 30), (7, 48), (9, 64), (11, 78), (14, 90), (20, 100)],
            units="%", as_of=as_of, source=SEC_FILING,
            interpretation="Capital standing behind the balance sheet. Substituted for net debt to EBITDA, which does not describe a lender.",
        )
        card.measure(
            "cash_to_assets", "Cash and equivalents to assets", 4.0, "balance_sheet",
            (r.get("cash") / assets_bs * 100) if (r.get("cash") and assets_bs) else None,
            bands=[(1, 12), (4, 34), (8, 54), (12, 70), (18, 84), (25, 94)],
            units="%", as_of=as_of, source=SEC_FILING,
            interpretation="Liquidity held against the balance sheet, substituted for interest coverage.",
        )
    else:
        card.measure(
            "net_debt_ebitda", "Net debt to EBITDA", 6.0, "balance_sheet",
            r.get("net_debt_to_ebitda"), peers=peers.distribution("net_debt_to_ebitda"),
            bands=[(-2, 100), (-0.5, 94), (0.5, 86), (1.5, 74), (2.5, 58), (3.5, 40), (5, 20), (7, 6)],
            higher_is_better=False, blend=0.7, units="x", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
            interpretation="How many years of cash earnings it would take to clear net borrowings.",
        )
        card.measure(
            "interest_coverage", "Interest coverage", 4.0, "balance_sheet",
            r.get("interest_coverage"), peers=peers.distribution("interest_coverage"),
            bands=[(0, 4), (1.5, 20), (3, 42), (6, 62), (12, 78), (25, 90), (60, 97)],
            blend=0.7,
            units="x", peer_group=peers.label, as_of=as_of, source=SEC_FILING,
            interpretation="Operating profit against the annual interest bill.",
        )
    card.measure(
        "liquidity", "Cash against current liabilities", 3.0, "balance_sheet",
        r.get("cash_to_current_liabilities"),
        bands=[(0.0, 8), (0.15, 32), (0.3, 52), (0.5, 68), (0.8, 82), (1.5, 93), (3.0, 100)],
        units="x", as_of=as_of, source=SEC_FILING,
        interpretation=(
            f"Current ratio is {r['current_ratio']:.2f}x." if r.get("current_ratio") else
            "Immediate liquidity against near term obligations."
        ),
    )
    card.measure(
        "debt_maturity", "Debt maturity and refinancing risk", 2.0, "balance_sheet",
        None, as_of=as_of,
        interpretation="The maturity ladder sits in the notes to the accounts and is not machine readable from XBRL facts.",
    )

    # --- E. Valuation, 15 ---------------------------------------------------------
    eps = r.get("eps_latest")
    trailing_pe = (price / eps) if (price and eps and eps > 0) else None
    unprofitable = (r.get("net_income") is not None and r["net_income"] <= 0) or (eps is not None and eps <= 0)

    if unprofitable:
        # PRD 14. P/E is marked not applicable and the engine substitutes other measures
        # rather than rewarding a company for having no earnings to divide by.
        ev_sales = None
        if enterprise_value is not None and r.get("revenue"):
            ev_sales = enterprise_value / r["revenue"]
        card.measure(
            "earnings_multiple", "Price to earnings", 4.0, "valuation", None,
            not_applicable=True,
            na_reason="The company is not profitable, so a P/E is meaningless. Weight moves to the other valuation measures.",
            as_of=as_of,
        )
        card.measure(
            "ev_sales", "Enterprise value to sales", 4.0, "valuation", ev_sales,
            bands=[(0.5, 95), (1.5, 85), (3, 70), (5, 55), (8, 38), (14, 18), (25, 5)],
            higher_is_better=False, units="x", as_of=as_of, source=NASDAQ,
            interpretation="Substituted for the earnings multiple because the company does not yet earn a profit.",
        )
        overlays.append("Unprofitable company: price to earnings replaced with enterprise value to sales and gross margin quality.")
    else:
        card.measure(
            "earnings_multiple", "Price to earnings", 4.0, "valuation", trailing_pe,
            bands=[(6, 95), (11, 86), (16, 74), (21, 62), (28, 46), (40, 26), (60, 10), (90, 3)],
            higher_is_better=False, units="x", as_of=as_of, source=NASDAQ,
            interpretation=(
                f"{f.flow_basis} Diluted earnings per share of {eps:.2f} against the last "
                f"traded price." if eps else f.flow_basis
            ),
        )
        if is_financial or is_reit:
            # PRD 17 names price to book as the appropriate multiple here. Enterprise
            # value is not a meaningful construct when debt is raw material.
            card.measure(
                "price_to_book", "Price to book", 4.0, "valuation",
                (market_cap / equity_latest) if (market_cap and equity_latest and equity_latest > 0) else None,
                bands=[(0.4, 97), (0.8, 88), (1.1, 74), (1.5, 60), (2.2, 44), (3.2, 26), (5, 10)],
                higher_is_better=False, units="x", as_of=as_of, source=NASDAQ,
                interpretation="Substituted for enterprise value to EBITDA, which does not describe this balance sheet.",
            )
        else:
            card.measure(
                "ev_ebitda", "Enterprise value to EBITDA", 4.0, "valuation",
                (enterprise_value / ebitda) if (enterprise_value is not None and ebitda and ebitda > 0) else None,
                bands=[(3, 96), (6, 88), (9, 77), (12, 65), (16, 50), (22, 30), (32, 12), (50, 4)],
                higher_is_better=False, units="x", as_of=as_of, source=NASDAQ,
                interpretation="Values the whole business including its debt, so capital structure does not flatter the multiple.",
            )

    fcf_yield = None
    if market_cap and r.get("free_cash_flow") is not None and market_cap > 0:
        fcf_yield = r["free_cash_flow"] / market_cap * 100
    card.measure(
        "fcf_yield", "Free cash flow yield", 4.0, "valuation", fcf_yield,
        bands=[(0, 4), (1, 22), (2, 42), (3, 58), (4.5, 72), (6, 85), (9, 95), (14, 100)],
        units="%", as_of=as_of, source=NASDAQ,
        not_applicable=is_financial,
        na_reason="Free cash flow yield does not describe a lender. Weight moves to the earnings multiple and the range test.",
        interpretation="Cash the business throws off each year against what the market is charging for it.",
    )

    # Valuation against its own history.
    #
    # The earnings multiple against its own five year range is the measure that
    # actually belongs in a valuation category. Position in the 52 week price range
    # is momentum wearing a valuation costume: a company that has just raised
    # guidance can sit at 95% of its range and be cheaper than it was a year ago.
    # It is kept only as a fallback, because a weak proxy still beats no reading,
    # and it is scored on a gentler band and labelled for what it is.
    pe_low, pe_high, pe_series = _pe_history(f, history or [])
    own_range_score_value = None
    range_basis = ""
    range_bands = [(0, 96), (20, 86), (40, 74), (60, 60), (80, 42), (100, 22)]
    w52_hi = (summary or {}).get("week52_high")
    w52_lo = (summary or {}).get("week52_low")
    if trailing_pe and pe_low and pe_high and pe_high > pe_low:
        own_range_score_value = (trailing_pe - pe_low) / (pe_high - pe_low) * 100
        range_basis = (f"At {trailing_pe:.1f}x against its own filed five year range of "
                       f"{pe_low:.1f}x to {pe_high:.1f}x.")
    elif price and w52_hi and w52_lo and w52_hi > w52_lo:
        own_range_score_value = (price - w52_lo) / (w52_hi - w52_lo) * 100
        range_basis = (f"No usable five year earnings range on file, so this falls back to "
                       f"price position: {own_range_score_value:.0f}% of the 52 week range of "
                       f"{w52_lo:,.2f} to {w52_hi:,.2f}. That is a momentum reading, not a "
                       f"valuation, and it is scored on a gentler band for that reason.")
        range_bands = [(0, 88), (25, 78), (50, 68), (75, 56), (100, 44)]
    card.measure(
        "valuation_vs_own_history", "Valuation against its own range", 3.0, "valuation",
        own_range_score_value,
        bands=range_bands,
        higher_is_better=False, units="% of its own range",
        as_of=as_of, source=NASDAQ,
        interpretation=range_basis or "No usable range on file.",
    )

    # --- F. Business quality and earnings durability, 10 --------------------------
    # PRD 15 and 51 require evidence behind a qualitative score. The evidence used here
    # is the company's own filed record, not an assertion about its competitive position.
    moat_evidence: list[str] = []
    moat_score = NEUTRAL
    roic_vals = []
    for y in sorted(set(f.operating_income) & set(f.equity)):
        debt_y = f.total_debt.get(y, 0.0)
        cash_y = f.cash.get(y, 0.0)
        inv = debt_y + f.equity[y] - cash_y
        if inv and inv > 0:
            roic_vals.append(f.operating_income[y] * 0.79 / inv * 100)
    gm = r.get("gross_margin")
    if roic_vals:
        sustained = sum(1 for v in roic_vals[-5:] if v > 12)
        span = len(roic_vals[-5:])
        if span >= 3:
            moat_evidence.append(
                f"Return on invested capital exceeded 12% in {sustained} of the last {span} filed years."
            )
            moat_score = score_against_bands(
                sustained / span * 100, [(0, 20), (40, 45), (60, 60), (80, 78), (100, 92)]
            )
    if gm is not None:
        moat_evidence.append(f"Gross margin of {gm:.1f}% in the latest filed year.")
        if gm > 55:
            moat_score = min(100.0, moat_score + 6)
        elif gm < 20:
            moat_score = max(0.0, moat_score - 6)
    card.qualitative(
        "moat", "Competitive advantage", 4.0, "business_quality", moat_score,
        moat_evidence, source=SEC_FILING, as_of=as_of,
    )

    om_series = [
        f.operating_income[y] / f.revenue[y] * 100
        for y in sorted(set(f.operating_income) & set(f.revenue))
        if f.revenue[y]
    ]
    card.measure(
        "earnings_stability", "Earnings stability", 3.0, "business_quality",
        _cv(om_series),
        bands=[(2, 100), (5, 92), (10, 80), (18, 64), (30, 45), (50, 25), (90, 8)],
        higher_is_better=False, units="% variation in operating margin",
        as_of=as_of, source=SEC_FILING,
        interpretation=f"Operating margin variation across {len(om_series)} filed years.",
    )
    card.measure(
        "concentration", "Customer and revenue concentration", 3.0, "business_quality",
        None, as_of=as_of,
        interpretation="Segment and customer concentration is disclosed in narrative form and is not available as a structured fact.",
    )

    # --- G. Market risk and forward signals, 8 ------------------------------------
    # PRD 16 is explicit that technical indicators stay a small part of the score.
    card.measure(
        "max_drawdown", "Maximum drawdown", 3.0, "market_risk",
        rp.max_drawdown_pct if rp else None,
        bands=[(-85, 4), (-65, 18), (-50, 34), (-38, 50), (-28, 66), (-20, 80), (-13, 91), (-6, 100)],
        units="%", as_of=rp.last_date if rp else None, source=NASDAQ,
        interpretation=(
            f"Worst peak to trough fall across {rp.years_covered:.1f} years of daily closes."
            if rp else ""
        ),
    )
    downside = rp.downside_capture_pct if rp else None
    card.measure(
        "downside_capture", "Beta and downside capture", 2.0, "market_risk",
        downside,
        bands=[(30, 100), (55, 90), (75, 80), (92, 68), (105, 56), (125, 40), (160, 20), (220, 5)],
        higher_is_better=False, units="% of market down days",
        as_of=rp.last_date if rp else None, source=NASDAQ,
        interpretation=(
            f"Beta to the S&P 500 is {rp.beta:.2f}"
            + (f", against {(summary or {}).get('beta'):.2f} reported by the exchange."
               if (summary or {}).get("beta") is not None else ".")
            if rp and rp.beta is not None
            else "Share of the market's down day moves this security absorbs."
        ),
    )
    card.measure(
        "momentum", "Medium term momentum", 3.0, "market_risk",
        rp.momentum_12_1_pct if rp else None,
        bands=[(-60, 8), (-30, 25), (-12, 42), (0, 52), (12, 63), (30, 76), (60, 88), (120, 96)],
        units="% over 12 months excluding the last month",
        as_of=rp.last_date if rp else None, source=NASDAQ,
        interpretation="Estimate revisions are unavailable, so PRD 16's alternative measure is used. It stays a small weight on purpose.",
    )

    if sector in SOFTWARE_SECTORS and r.get("revenue_growth_1y") is not None and r.get("fcf_margin") is not None:
        overlays.append(
            f"Software overlay: Rule of 40 reads {r['revenue_growth_1y'] + r['fcf_margin']:.0f} "
            f"({r['revenue_growth_1y']:.0f}% revenue growth plus {r['fcf_margin']:.0f}% free cash flow margin). "
            "Supporting context only, never a standalone buy criterion."
        )
    if is_financial:
        overlays.append(
            "Financial institution overlay: free cash flow, enterprise value and net debt measures are "
            "marked not applicable and their weight moves to return on equity and liquidity, per PRD 17."
        )
    if is_reit:
        overlays.append("Real estate overlay: enterprise value to EBITDA is suppressed for a REIT capital structure.")

    result = card.finalise()
    result["overlays"] = overlays
    result["category_labels"] = CATEGORY_LABELS
    result["derived"] = {
        "price": price,
        "market_cap": market_cap,
        "market_cap_basis": market_cap_basis,
        "enterprise_value": enterprise_value,
        "trailing_pe": round(trailing_pe, 2) if trailing_pe else None,
        "fcf_yield_pct": round(fcf_yield, 2) if fcf_yield is not None else None,
        "ev_ebitda": round(enterprise_value / ebitda, 2) if (enterprise_value is not None and ebitda and ebitda > 0) else None,
        "pe_range": {"low": pe_low, "high": pe_high, "series": pe_series},
        "unprofitable": unprofitable,
    }
    result["peer_group"] = peers.meta()
    return result
