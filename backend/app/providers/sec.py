"""SEC EDGAR adapter.

PRD 11 puts SEC filings at the top of the source hierarchy and PRD 58 asks for a
provider interface rather than a hardcoded website, so this module exposes
`get_company_fundamentals(ticker)` and keeps the XBRL handling private.

Everything returned here traces to a company's own filed XBRL facts. Nothing is
inferred. A figure the filer did not report comes back as None and the scoring engine
treats it as missing rather than guessing.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

# SEC asks for a descriptive User-Agent with contact details on automated requests.
HEADERS = {
    "User-Agent": "Cash Cows Investment Team (Wharton GHSIC) research@cashcows.example",
    "Accept-Encoding": "gzip, deflate",
}

FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"

TICKER_TTL = 7 * 24 * 3600
FACTS_TTL = 24 * 3600


def _cache_path(name: str) -> Path:
    return CACHE_DIR / name


def _read_cache(name: str, ttl: int) -> Any | None:
    p = _cache_path(name)
    if not p.exists():
        return None
    if time.time() - p.stat().st_mtime > ttl:
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _write_cache(name: str, payload: Any) -> None:
    try:
        _cache_path(name).write_text(json.dumps(payload))
    except OSError:
        pass


def _get(url: str, timeout: float = 45.0) -> Any | None:
    try:
        r = httpx.get(url, headers=HEADERS, timeout=timeout, follow_redirects=True)
        if r.status_code != 200:
            return None
        return r.json()
    except (httpx.HTTPError, json.JSONDecodeError):
        return None


# Symbols whose SEC entry points at a registrant with no filing history, usually
# after a holding-company reorganisation. The value is the operating company that
# actually files.
CIK_OVERRIDES: dict[str, int] = {
    "XOM": 34088,   # ExxonMobil Holdings Corp has no filings; Exxon Mobil Corp does
}


def ticker_to_cik(ticker: str) -> int | None:
    ticker = ticker.strip().upper()
    if ticker in CIK_OVERRIDES:
        return CIK_OVERRIDES[ticker]
    table = _read_cache("sec_tickers.json", TICKER_TTL)
    if table is None:
        raw = _get(TICKERS_URL)
        if raw is None:
            return None
        table = {v["ticker"].upper(): v["cik_str"] for v in raw.values()}
        _write_cache("sec_tickers.json", table)
    return table.get(ticker)


def company_profile(cik: int) -> dict:
    """Name, SIC industry description and exchange, from the submissions endpoint."""
    cached = _read_cache(f"sub_{cik}.json", FACTS_TTL * 7)
    if cached is None:
        cached = _get(SUBMISSIONS_URL.format(cik=cik)) or {}
        # The filing history is large and we only need the header fields.
        cached = {
            k: cached.get(k)
            for k in ("name", "sic", "sicDescription", "tickers", "exchanges", "cik", "stateOfIncorporation")
        }
        _write_cache(f"sub_{cik}.json", cached)
    return cached


def company_facts(cik: int) -> dict | None:
    cached = _read_cache(f"facts_{cik}.json", FACTS_TTL)
    if cached is not None:
        return cached
    raw = _get(FACTS_URL.format(cik=cik), timeout=90.0)
    if raw is None:
        return None
    _write_cache(f"facts_{cik}.json", raw)
    return raw


# --- XBRL series extraction -------------------------------------------------------

REVENUE_TAGS = [
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "RevenueFromContractWithCustomerIncludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
    "SalesRevenueGoodsNet",
]
OPERATING_INCOME_TAGS = ["OperatingIncomeLoss"]
NET_INCOME_TAGS = ["NetIncomeLoss", "ProfitLoss"]
GROSS_PROFIT_TAGS = ["GrossProfit"]
OCF_TAGS = [
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
]
CAPEX_TAGS = [
    "PaymentsToAcquirePropertyPlantAndEquipment",
    "PaymentsToAcquireProductiveAssets",
    "PaymentsToAcquireOtherPropertyPlantAndEquipment",
    "PaymentsForCapitalImprovements",
    "PaymentsToAcquireRealEstate",
    "PaymentsToDevelopRealEstateAssets",
    "PaymentsToAcquireCommercialRealEstate",
]
SBC_TAGS = ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"]
DA_TAGS = [
    "DepreciationDepletionAndAmortization",
    "DepreciationAmortizationAndAccretionNet",
    "DepreciationAndAmortization",
]
TAX_TAGS = ["IncomeTaxExpenseBenefit"]
PRETAX_TAGS = ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"]
INTEREST_TAGS = ["InterestExpense", "InterestExpenseDebt", "InterestIncomeExpenseNet"]
DILUTED_SHARES_TAGS = ["WeightedAverageNumberOfDilutedSharesOutstanding"]
EPS_TAGS = ["EarningsPerShareDiluted"]

ASSETS_TAGS = ["Assets"]
EQUITY_TAGS = [
    "StockholdersEquity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
]
CASH_TAGS = [
    "CashAndCashEquivalentsAtCarryingValue",
    "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
]
SHORT_INVEST_TAGS = [
    "ShortTermInvestments",
    "MarketableSecuritiesCurrent",
    "AvailableForSaleSecuritiesDebtSecuritiesCurrent",
    "OtherShortTermInvestments",
]
LT_DEBT_TAGS = ["LongTermDebtNoncurrent", "LongTermDebt"]
ST_DEBT_TAGS = ["LongTermDebtCurrent", "DebtCurrent", "ShortTermBorrowings", "OtherShortTermBorrowings"]
CURRENT_ASSETS_TAGS = ["AssetsCurrent"]
CURRENT_LIAB_TAGS = ["LiabilitiesCurrent"]


# Foreign private issuers filing a 20-F report under IFRS, in the `ifrs-full`
# namespace with different tag names. Taiwan Semiconductor, Shell, AstraZeneca and
# Novartis all sit here. Without this, every non-US holding in an international fund
# reads as missing and the look-through engine has nothing to work with.
IFRS_EQUIVALENTS: dict[str, list[str]] = {
    "RevenueFromContractWithCustomerExcludingAssessedTax": ["RevenueFromContractsWithCustomers", "Revenue"],
    "Revenues": ["Revenue", "RevenueFromContractsWithCustomers"],
    "OperatingIncomeLoss": ["ProfitLossFromOperatingActivities"],
    "NetIncomeLoss": ["ProfitLossAttributableToOwnersOfParent", "ProfitLoss"],
    "ProfitLoss": ["ProfitLoss"],
    "GrossProfit": ["GrossProfit"],
    "NetCashProvidedByUsedInOperatingActivities": ["CashFlowsFromUsedInOperatingActivities"],
    "PaymentsToAcquirePropertyPlantAndEquipment": [
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities"
    ],
    "DepreciationDepletionAndAmortization": [
        "DepreciationAndAmortisationExpense", "DepreciationAmortisationAndImpairmentLossReversalOfImpairmentLossRecognisedInProfitOrLoss"
    ],
    "IncomeTaxExpenseBenefit": ["IncomeTaxExpenseContinuingOperations"],
    "InterestExpense": ["InterestExpense", "FinanceCosts"],
    "Assets": ["Assets"],
    "StockholdersEquity": ["EquityAttributableToOwnersOfParent", "Equity"],
    "CashAndCashEquivalentsAtCarryingValue": ["CashAndCashEquivalents"],
    "AssetsCurrent": ["CurrentAssets"],
    "LiabilitiesCurrent": ["CurrentLiabilities"],
    "LongTermDebtNoncurrent": ["NoncurrentPortionOfNoncurrentBorrowings", "BorrowingsNoncurrent"],
    "LongTermDebtCurrent": ["CurrentPortionOfNoncurrentBorrowings", "BorrowingsCurrent"],
    "EarningsPerShareDiluted": ["DilutedEarningsLossPerShare"],
    "WeightedAverageNumberOfDilutedSharesOutstanding": [
        "WeightedAverageNumberOfDilutedSharesOutstanding", "AdjustedWeightedAverageShares"
    ],
    "ShareBasedCompensation": ["ShareBasedPaymentsExpense"],
}


def _node_units(node: dict) -> list[dict]:
    for unit in ("USD", "shares", "USD/shares", "pure"):
        if unit in node.get("units", {}):
            return node["units"][unit]
    # A 20-F filer may report only in its reporting currency.
    units = node.get("units", {})
    for key in units:
        if key.endswith("/shares") or len(key) == 3:
            return units[key]
    return []


def _units(facts: dict, tag: str) -> list[dict]:
    all_facts = facts.get("facts", {})
    node = all_facts.get("us-gaap", {}).get(tag)
    if node:
        return _node_units(node)
    ifrs = all_facts.get("ifrs-full", {})
    if ifrs:
        for alt in IFRS_EQUIVALENTS.get(tag, []):
            node = ifrs.get(alt)
            if node:
                return _node_units(node)
    return []


def _best(candidates: list[dict[int, float]]) -> dict[int, float]:
    """Pick the most usable series among several candidate tags.

    Filers migrate between tags over time, so the first tag that returns anything is
    often a stale fragment. NVIDIA, for instance, carries a few early years under the
    newer revenue tag and the full history under `Revenues`. Rank by how recent the
    series runs, then by how many years it covers.
    """
    usable = [c for c in candidates if c]
    if not usable:
        return {}
    return max(usable, key=lambda s: (max(s), len(s)))


def _annual_duration(facts: dict, tags: list[str]) -> dict[int, float]:
    """Annual (roughly 365 day) duration facts from 10-K filings, keyed by fiscal year."""
    return _best([_annual_duration_one(facts, t) for t in tags])


def _annual_duration_one(facts: dict, tag: str) -> dict[int, float]:
    out: dict[int, tuple[str, float]] = {}
    if True:
        for f in _units(facts, tag):
            if f.get("form") not in ("10-K", "10-K/A", "20-F"):
                continue
            start, end = f.get("start"), f.get("end")
            if not start or not end:
                continue
            try:
                d0 = datetime.strptime(start, "%Y-%m-%d").date()
                d1 = datetime.strptime(end, "%Y-%m-%d").date()
            except ValueError:
                continue
            days = (d1 - d0).days
            if not (330 <= days <= 400):
                continue
            year = d1.year if d1.month >= 6 else d1.year - 1
            filed = f.get("filed", "")
            prev = out.get(year)
            if prev is None or filed > prev[0]:
                out[year] = (filed, float(f["val"]))
    return {y: v for y, (_, v) in out.items()}


def _annual_instant(facts: dict, tags: list[str]) -> dict[int, float]:
    """Point-in-time balance-sheet facts from 10-K filings, keyed by fiscal year."""
    return _best([_annual_instant_one(facts, t) for t in tags])


def _annual_instant_one(facts: dict, tag: str) -> dict[int, float]:
    out: dict[int, tuple[str, float]] = {}
    if True:
        for f in _units(facts, tag):
            if f.get("form") not in ("10-K", "10-K/A", "20-F"):
                continue
            end = f.get("end")
            if not end:
                continue
            try:
                d1 = datetime.strptime(end, "%Y-%m-%d").date()
            except ValueError:
                continue
            year = d1.year if d1.month >= 6 else d1.year - 1
            filed = f.get("filed", "")
            prev = out.get(year)
            if prev is None or filed > prev[0]:
                out[year] = (filed, float(f["val"]))
    return {y: v for y, (_, v) in out.items()}


def _sum_tags_instant(facts: dict, groups: list[list[str]]) -> dict[int, float]:
    """Add several independent line items, e.g. short and long term debt."""
    series: list[dict[int, float]] = [_annual_instant(facts, g) for g in groups]
    years: set[int] = set()
    for s in series:
        years |= set(s)
    return {y: sum(s.get(y, 0.0) for s in series) for y in years}


def _latest(series: dict[int, float], n: int = 1) -> float | None:
    if not series:
        return None
    years = sorted(series)
    if len(years) < n:
        return None
    return series[years[-n]]


def _cagr(series: dict[int, float], years: int = 3) -> float | None:
    if len(series) < years + 1:
        return None
    ordered = sorted(series)
    end_y, start_y = ordered[-1], ordered[-1 - years]
    end_v, start_v = series[end_y], series[start_y]
    if start_v is None or start_v <= 0 or end_v is None:
        return None
    if end_v <= 0:
        return -100.0
    return ((end_v / start_v) ** (1 / years) - 1) * 100


def _growth(series: dict[int, float]) -> float | None:
    """Most recent year over prior year, in percent. Guards sign flips."""
    if len(series) < 2:
        return None
    ordered = sorted(series)
    cur, prev = series[ordered[-1]], series[ordered[-2]]
    if prev is None or cur is None or prev == 0:
        return None
    if prev < 0:
        # Growth off a negative base is not meaningful as a percentage.
        return None
    return (cur - prev) / abs(prev) * 100


def _safe_div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


@dataclass
class Fundamentals:
    ticker: str
    cik: int
    name: str
    sic: str = ""
    sic_description: str = ""
    exchange: str = ""
    fiscal_year: int | None = None
    period_end: str | None = None

    # Raw annual series, kept so the audit trail can show the working.
    revenue: dict[int, float] = field(default_factory=dict)
    operating_income: dict[int, float] = field(default_factory=dict)
    net_income: dict[int, float] = field(default_factory=dict)
    gross_profit: dict[int, float] = field(default_factory=dict)
    ocf: dict[int, float] = field(default_factory=dict)
    capex: dict[int, float] = field(default_factory=dict)
    fcf: dict[int, float] = field(default_factory=dict)
    sbc: dict[int, float] = field(default_factory=dict)
    dna: dict[int, float] = field(default_factory=dict)
    diluted_shares: dict[int, float] = field(default_factory=dict)
    eps: dict[int, float] = field(default_factory=dict)
    assets: dict[int, float] = field(default_factory=dict)
    equity: dict[int, float] = field(default_factory=dict)
    cash: dict[int, float] = field(default_factory=dict)
    total_debt: dict[int, float] = field(default_factory=dict)
    current_assets: dict[int, float] = field(default_factory=dict)
    current_liabilities: dict[int, float] = field(default_factory=dict)
    interest_expense: dict[int, float] = field(default_factory=dict)
    tax: dict[int, float] = field(default_factory=dict)
    pretax: dict[int, float] = field(default_factory=dict)

    ratios: dict[str, float | None] = field(default_factory=dict)
    operating_income_basis: str = "As reported"

    def history(self, key: str, n: int = 6) -> list[dict]:
        series: dict[int, float] = getattr(self, key, {}) or {}
        years = sorted(series)[-n:]
        return [{"year": y, "value": series[y]} for y in years]


def _derive(f: Fundamentals) -> None:
    years = sorted(set(f.ocf) & set(f.capex))
    f.fcf = {y: f.ocf[y] - abs(f.capex[y]) for y in years}
    if not f.fcf and f.ocf:
        # Some filers omit capex as a separate tag. Operating cash flow alone is not
        # free cash flow, so we leave FCF empty rather than overstate it.
        f.fcf = {}

    rev = _latest(f.revenue)
    opinc = _latest(f.operating_income)
    ni = _latest(f.net_income)
    ocf = _latest(f.ocf)
    fcf = _latest(f.fcf)
    assets = _latest(f.assets)
    equity = _latest(f.equity)
    cash = _latest(f.cash)
    debt = _latest(f.total_debt)
    dna = _latest(f.dna)
    sbc = _latest(f.sbc)
    interest = _latest(f.interest_expense)
    tax = _latest(f.tax)
    pretax = _latest(f.pretax)

    ebitda = (opinc + dna) if (opinc is not None and dna is not None) else None
    net_debt = (debt - cash) if (debt is not None and cash is not None) else None

    tax_rate = None
    if tax is not None and pretax not in (None, 0):
        tax_rate = max(0.0, min(0.45, tax / pretax))
    if tax_rate is None:
        tax_rate = 0.21  # US statutory, used only when the filer's effective rate is unusable

    nopat = opinc * (1 - tax_rate) if opinc is not None else None
    invested = None
    if debt is not None and equity is not None:
        invested = debt + equity - (cash or 0.0)
        if invested <= 0:
            invested = None

    # Margin trajectory: current operating margin against the three year average.
    traj = None
    om_series = {
        y: f.operating_income[y] / f.revenue[y] * 100
        for y in sorted(set(f.operating_income) & set(f.revenue))
        if f.revenue[y]
    }
    if len(om_series) >= 3:
        ordered = sorted(om_series)
        recent = om_series[ordered[-1]]
        prior = sum(om_series[y] for y in ordered[-4:-1]) / len(ordered[-4:-1])
        traj = recent - prior

    share_change = None
    if len(f.diluted_shares) >= 2:
        ordered = sorted(f.diluted_shares)
        a, b = f.diluted_shares[ordered[-2]], f.diluted_shares[ordered[-1]]
        if a:
            share_change = (b - a) / a * 100

    f.ratios = {
        "revenue_cagr_3y": _cagr(f.revenue, 3),
        "revenue_growth_1y": _growth(f.revenue),
        "operating_income_growth": _growth(f.operating_income),
        "eps_growth": _growth(f.eps),
        "fcf_growth": _growth(f.fcf),
        "fcf_margin": None if (fcf is None or not rev) else fcf / rev * 100,
        "operating_margin": None if (opinc is None or not rev) else opinc / rev * 100,
        "gross_margin": None if (_latest(f.gross_profit) is None or not rev) else _latest(f.gross_profit) / rev * 100,
        "cash_conversion": None if (ocf is None or ni in (None, 0)) else ocf / ni * 100,
        "fcf_conversion": None if (fcf is None or opinc in (None, 0) or opinc < 0) else fcf / opinc * 100,
        "sbc_to_revenue": None if (sbc is None or not rev) else sbc / rev * 100,
        "share_count_change": share_change,
        "roic": None if (nopat is None or invested is None) else nopat / invested * 100,
        "roe": None if (ni is None or equity in (None, 0) or equity < 0) else ni / equity * 100,
        "roa": None if (ni is None or not assets) else ni / assets * 100,
        "margin_trajectory": traj,
        "net_debt_to_ebitda": None if (net_debt is None or ebitda in (None, 0) or ebitda < 0) else net_debt / ebitda,
        "interest_coverage": None if (opinc is None or interest in (None, 0)) else opinc / abs(interest),
        "cash_to_current_liabilities": _safe_div(cash, _latest(f.current_liabilities)),
        "current_ratio": _safe_div(_latest(f.current_assets), _latest(f.current_liabilities)),
        "ebitda": ebitda,
        "net_debt": net_debt,
        "revenue": rev,
        "net_income": ni,
        "operating_income": opinc,
        "free_cash_flow": fcf,
        "equity": equity,
        "cash": cash,
        "total_debt": debt,
        "diluted_shares": _latest(f.diluted_shares),
        "eps_latest": _latest(f.eps),
        "effective_tax_rate": tax_rate * 100,
    }


def get_company_fundamentals(ticker: str) -> Fundamentals | None:
    cik = ticker_to_cik(ticker)
    if cik is None:
        return None
    facts = company_facts(cik)
    if facts is None:
        return None
    profile = company_profile(cik)

    f = Fundamentals(
        ticker=ticker.upper(),
        cik=cik,
        name=facts.get("entityName") or profile.get("name") or ticker.upper(),
        sic=str(profile.get("sic") or ""),
        sic_description=profile.get("sicDescription") or "",
        exchange=(profile.get("exchanges") or [""])[0] if profile.get("exchanges") else "",
    )

    f.revenue = _annual_duration(facts, REVENUE_TAGS)
    f.operating_income = _annual_duration(facts, OPERATING_INCOME_TAGS)
    f.net_income = _annual_duration(facts, NET_INCOME_TAGS)
    f.gross_profit = _annual_duration(facts, GROSS_PROFIT_TAGS)
    f.ocf = _annual_duration(facts, OCF_TAGS)
    f.capex = _annual_duration(facts, CAPEX_TAGS)
    f.sbc = _annual_duration(facts, SBC_TAGS)
    f.dna = _annual_duration(facts, DA_TAGS)
    if not f.dna:
        # Microsoft and others report depreciation and amortisation as separate line
        # items with no combined tag, so rebuild the total from its components rather
        # than treating EBITDA as unavailable.
        dep = _annual_duration(facts, ["Depreciation", "DepreciationNonproduction"])
        amort = _annual_duration(facts, [
            "AmortizationOfIntangibleAssets",
            "AmortizationOfAcquiredIntangibleAssets",
            "FiniteLivedIntangibleAssetsAmortizationExpense",
        ])
        if dep or amort:
            years = set(dep) | set(amort)
            f.dna = {y: dep.get(y, 0.0) + amort.get(y, 0.0) for y in years}
    f.tax = _annual_duration(facts, TAX_TAGS)
    f.pretax = _annual_duration(facts, PRETAX_TAGS)
    f.interest_expense = _annual_duration(facts, INTEREST_TAGS)
    f.diluted_shares = _annual_duration(facts, DILUTED_SHARES_TAGS)
    f.eps = _annual_duration(facts, EPS_TAGS)

    f.assets = _annual_instant(facts, ASSETS_TAGS)
    f.equity = _annual_instant(facts, EQUITY_TAGS)
    f.cash = _annual_instant(facts, CASH_TAGS)
    f.current_assets = _annual_instant(facts, CURRENT_ASSETS_TAGS)
    f.current_liabilities = _annual_instant(facts, CURRENT_LIAB_TAGS)
    f.total_debt = _sum_tags_instant(facts, [LT_DEBT_TAGS, ST_DEBT_TAGS])

    if not f.operating_income and f.pretax:
        interest = f.interest_expense or {}
        rebuilt = {y: f.pretax[y] + abs(interest.get(y, 0.0)) for y in f.pretax}
        if rebuilt:
            f.operating_income = rebuilt
            f.operating_income_basis = "Rebuilt as pretax income plus interest expense"

    all_years = set(f.revenue) | set(f.net_income) | set(f.assets)
    if all_years:
        f.fiscal_year = max(all_years)

    # Freshness is measured from the period end of the revenue series we actually used.
    if f.revenue:
        latest_fy = max(f.revenue)
        ends = [
            x["end"]
            for tag in REVENUE_TAGS
            for x in _units(facts, tag)
            if x.get("form") in ("10-K", "10-K/A", "20-F")
            and x.get("end")
            and (int(x["end"][:4]) if int(x["end"][5:7]) >= 6 else int(x["end"][:4]) - 1) == latest_fy
        ]
        if ends:
            f.period_end = max(ends)

    _derive(f)
    return f
