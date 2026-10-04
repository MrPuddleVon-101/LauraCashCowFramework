"""Build real peer distributions from SEC XBRL frames.

PRD 12 requires quantitative metrics to be measured against an appropriate peer group
rather than compared in the abstract. The frames endpoint returns one tag for one
period across every registrant that reported it, so a dozen requests give us the whole
market rather than a hand-picked comparison set.

Two peer groups come out of this:

  * sector    Companies in the same sector, from the curated map in data/sectors.json.
              Used whenever the candidate is in the map and the sector has enough names.
  * size      SEC registrants in the same revenue band. The documented fallback when a
              sector group is unavailable or too thin, per PRD 12.

Run:  python -m scripts.build_peers
"""

from __future__ import annotations

import json
import math
import statistics
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Cash Cows Investment Team (Wharton GHSIC) research@cashcows.example",
    "Accept-Encoding": "gzip, deflate",
}
FRAME = "https://data.sec.gov/api/xbrl/frames/us-gaap/{tag}/USD/{period}.json"

# The fiscal year most registrants have now filed, and the comparison year three
# back, which is what the 3 year revenue CAGR needs.
LATEST = "CY2025"
PRIOR_1 = "CY2024"
PRIOR_3 = "CY2022"
LATEST_I = "CY2025Q4I"

DURATION_TAGS = {
    "revenue_a": "RevenueFromContractWithCustomerExcludingAssessedTax",
    "revenue_b": "Revenues",
    "operating_income": "OperatingIncomeLoss",
    "net_income": "NetIncomeLoss",
    "ocf": "NetCashProvidedByUsedInOperatingActivities",
    "capex": "PaymentsToAcquirePropertyPlantAndEquipment",
    "dna": "DepreciationDepletionAndAmortization",
    "interest": "InterestExpense",
    "sbc": "ShareBasedCompensation",
}
INSTANT_TAGS = {
    "assets": "Assets",
    "equity": "StockholdersEquity",
    "cash": "CashAndCashEquivalentsAtCarryingValue",
    "lt_debt": "LongTermDebtNoncurrent",
    "st_debt": "LongTermDebtCurrent",
}

MIN_REVENUE = 1_000_000_000.0  # $1bn floor keeps the comparison to companies of scale
SAMPLE_POINTS = 300            # distributions are stored downsampled, sorted ascending


def fetch_frame(tag: str, period: str) -> dict[int, float]:
    url = FRAME.format(tag=tag, period=period)
    for attempt in range(3):
        try:
            r = httpx.get(url, headers=HEADERS, timeout=90.0)
            if r.status_code == 200:
                return {int(d["cik"]): float(d["val"]) for d in r.json().get("data", [])}
            if r.status_code == 404:
                return {}
        except httpx.HTTPError:
            pass
        time.sleep(1.5 * (attempt + 1))
    return {}


def merge_revenue(a: dict[int, float], b: dict[int, float]) -> dict[int, float]:
    """Filers use either revenue tag. Take the larger reported figure where both exist."""
    out = dict(b)
    for cik, v in a.items():
        out[cik] = max(v, out.get(cik, 0.0))
    return out


def downsample(values: list[float]) -> list[float]:
    vals = sorted(v for v in values if v is not None and math.isfinite(v))
    if len(vals) <= SAMPLE_POINTS:
        return [round(v, 6) for v in vals]
    step = (len(vals) - 1) / (SAMPLE_POINTS - 1)
    return [round(vals[int(round(i * step))], 6) for i in range(SAMPLE_POINTS)]


def ratios_for(cik: int, F: dict) -> dict[str, float]:
    rev = F["revenue"].get(cik)
    if not rev or rev < MIN_REVENUE:
        return {}
    out: dict[str, float] = {}

    opinc = F["operating_income"].get(cik)
    ni = F["net_income"].get(cik)
    ocf = F["ocf"].get(cik)
    capex = F["capex"].get(cik)
    dna = F["dna"].get(cik)
    interest = F["interest"].get(cik)
    sbc = F["sbc"].get(cik)
    assets = F["assets"].get(cik)
    equity = F["equity"].get(cik)
    cash = F["cash"].get(cik)
    debt = (F["lt_debt"].get(cik) or 0.0) + (F["st_debt"].get(cik) or 0.0)

    fcf = (ocf - abs(capex)) if (ocf is not None and capex is not None) else None

    if fcf is not None:
        out["fcf_margin"] = fcf / rev * 100
    if opinc is not None:
        out["operating_margin"] = opinc / rev * 100
    # A conversion ratio is only meaningful against a positive denominator. Including
    # loss-makers and near-breakeven filers fills the distribution with four-figure
    # ratios and pushes genuinely healthy companies into the bottom decile.
    if ocf is not None and ni and ni > 0.02 * abs(rev):
        out["cash_conversion"] = max(-200.0, min(400.0, ocf / ni * 100))
    if fcf is not None and opinc and opinc > 0.02 * abs(rev):
        out["fcf_conversion"] = max(-200.0, min(400.0, fcf / opinc * 100))
    if sbc is not None:
        out["sbc_to_revenue"] = sbc / rev * 100
    if ni is not None and equity and equity > 0:
        out["roe"] = ni / equity * 100
    if ni is not None and assets:
        out["roa"] = ni / assets * 100
    if opinc is not None and equity and debt is not None:
        invested = debt + equity - (cash or 0.0)
        if invested > 0:
            out["roic"] = opinc * 0.79 / invested * 100  # 21% statutory tax, uniformly applied
    if opinc is not None and dna is not None:
        ebitda = opinc + dna
        if ebitda > 0.02 * abs(rev) and cash is not None:
            out["net_debt_to_ebitda"] = max(-10.0, min(20.0, (debt - cash) / ebitda))
    if opinc is not None and interest and abs(interest) > 0:
        out["interest_coverage"] = max(-50.0, min(500.0, opinc / abs(interest)))

    rev_prior3 = F["revenue_prior3"].get(cik)
    if rev_prior3 and rev_prior3 > 0:
        out["revenue_cagr_3y"] = ((rev / rev_prior3) ** (1 / 3) - 1) * 100
    rev_prior1 = F["revenue_prior1"].get(cik)
    if rev_prior1 and rev_prior1 > 0:
        out["revenue_growth_1y"] = (rev / rev_prior1 - 1) * 100
    op_prior1 = F["operating_income_prior1"].get(cik)
    if opinc is not None and op_prior1 and op_prior1 > 0:
        out["operating_income_growth"] = (opinc / op_prior1 - 1) * 100
    ocf_prior1 = F["ocf_prior1"].get(cik)
    capex_prior1 = F["capex_prior1"].get(cik)
    if fcf is not None and ocf_prior1 is not None and capex_prior1 is not None:
        fcf_prior = ocf_prior1 - abs(capex_prior1)
        if fcf_prior > 0:
            out["fcf_growth"] = (fcf / fcf_prior - 1) * 100

    return {k: v for k, v in out.items() if math.isfinite(v)}


def size_band(revenue: float) -> str:
    if revenue < 2e9:
        return "1-2bn"
    if revenue < 5e9:
        return "2-5bn"
    if revenue < 15e9:
        return "5-15bn"
    if revenue < 50e9:
        return "15-50bn"
    return "50bn-plus"


def main() -> int:
    print("Fetching SEC XBRL frames. This pulls the whole registrant universe per tag.")
    F: dict[str, dict[int, float]] = {}

    rev_a = fetch_frame(DURATION_TAGS["revenue_a"], LATEST)
    rev_b = fetch_frame(DURATION_TAGS["revenue_b"], LATEST)
    F["revenue"] = merge_revenue(rev_a, rev_b)
    print(f"  revenue {LATEST}: {len(F['revenue'])} filers")

    F["revenue_prior3"] = merge_revenue(
        fetch_frame(DURATION_TAGS["revenue_a"], PRIOR_3),
        fetch_frame(DURATION_TAGS["revenue_b"], PRIOR_3),
    )
    F["revenue_prior1"] = merge_revenue(
        fetch_frame(DURATION_TAGS["revenue_a"], PRIOR_1),
        fetch_frame(DURATION_TAGS["revenue_b"], PRIOR_1),
    )

    for key in ("operating_income", "net_income", "ocf", "capex", "dna", "interest", "sbc"):
        F[key] = fetch_frame(DURATION_TAGS[key], LATEST)
        print(f"  {key} {LATEST}: {len(F[key])} filers")
    for key in ("operating_income", "ocf", "capex"):
        F[f"{key}_prior1"] = fetch_frame(DURATION_TAGS[key], PRIOR_1)

    for key, tag in INSTANT_TAGS.items():
        F[key] = fetch_frame(tag, LATEST_I)
        print(f"  {key} {LATEST_I}: {len(F[key])} filers")

    sectors_path = DATA / "sectors.json"
    sector_map: dict[str, str] = json.loads(sectors_path.read_text()) if sectors_path.exists() else {}

    tickers = httpx.get(
        "https://www.sec.gov/files/company_tickers.json", headers=HEADERS, timeout=60
    ).json()
    cik_to_ticker: dict[int, str] = {}
    for v in tickers.values():
        cik_to_ticker.setdefault(int(v["cik_str"]), v["ticker"].upper())

    universe: dict[int, dict[str, float]] = {}
    for cik in F["revenue"]:
        r = ratios_for(cik, F)
        if r:
            universe[cik] = r
    print(f"\n{len(universe)} companies above the ${MIN_REVENUE/1e9:.0f}bn revenue floor")

    buckets: dict[str, dict[str, list[float]]] = {}

    def add(bucket: str, ratios: dict[str, float]) -> None:
        b = buckets.setdefault(bucket, {})
        for k, v in ratios.items():
            b.setdefault(k, []).append(v)

    for cik, r in universe.items():
        add("ALL", r)
        add(f"size:{size_band(F['revenue'][cik])}", r)
        tkr = cik_to_ticker.get(cik)
        if tkr and tkr in sector_map:
            add(f"sector:{sector_map[tkr]}", r)

    out = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "source": "SEC XBRL frames API",
        "source_url": "https://data.sec.gov/api/xbrl/frames/",
        "periods": {"latest": LATEST, "prior_1": PRIOR_1, "prior_3": PRIOR_3, "instant": LATEST_I},
        "revenue_floor_usd": MIN_REVENUE,
        "groups": {},
    }
    for bucket, ratios in sorted(buckets.items()):
        entry = {"n": 0, "distributions": {}}
        for k, vals in ratios.items():
            if len(vals) >= 8:
                entry["distributions"][k] = downsample(vals)
        entry["n"] = max((len(v) for v in ratios.values()), default=0)
        if entry["distributions"]:
            out["groups"][bucket] = entry

    (DATA / "peers.json").write_text(json.dumps(out))
    size_kb = (DATA / "peers.json").stat().st_size // 1024
    print(f"\nWrote data/peers.json ({size_kb}KB) with {len(out['groups'])} peer groups")
    for b in sorted(out["groups"]):
        g = out["groups"][b]
        med = statistics.median(g["distributions"].get("operating_margin", [0]))
        print(f"  {b:28s} n={g['n']:5d}  metrics={len(g['distributions']):2d}  median op margin={med:6.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
