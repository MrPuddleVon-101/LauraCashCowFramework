"""Laura's liability calendar and the present value engine. PRD 34 to 37.

Ten payments of $50,000, one at the beginning of each year from 2033 to 2042, for a
total nominal commitment of $500,000. Every payment carries a funding state, and the
distinction the PRD cares most about is between ECONOMICALLY_COVERED and MATCHED: a
strong equity portfolio is not the same thing as a Treasury that matures when the
payment is due.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..config import CLIENT, POLICY
from ..providers import treasury
from .registry import get_fund

FundingState = Literal["UNFUNDED", "PARTIALLY_FUNDED", "ECONOMICALLY_COVERED", "MATCHED", "PAID"]

STATE_DESCRIPTIONS: dict[str, str] = {
    "UNFUNDED": "No dedicated matching asset and no modelled capital behind it.",
    "PARTIALLY_FUNDED": "A dedicated cash flow exists but covers less than the full $50,000.",
    "ECONOMICALLY_COVERED": "Portfolio modelling suggests enough capital, but nothing is dedicated to this date.",
    "MATCHED": "A specific high certainty cash flow is dedicated to this payment.",
    "PAID": "The obligation has been met.",
}


@dataclass
class MatchedAsset:
    ticker: str
    payment_year: int
    expected_cash_flow: float
    maturity_date: str = ""
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker, "payment_year": self.payment_year,
            "expected_cash_flow": round(self.expected_cash_flow, 2),
            "maturity_date": self.maturity_date, "note": self.note,
        }


def years_until(payment_year: int, as_of_year: int) -> float:
    """Payments occur at the beginning of the year, so 2033 is six years from 2027."""
    return max(0.0, float(payment_year - as_of_year))


def present_value(payment_year: int, as_of_year: int, curve: dict | None = None,
                  amount: float | None = None, flat_rate: float | None = None) -> dict:
    """PRD 36. PV = 50,000 / (1 + y)^years, at a maturity appropriate market yield."""
    amount = amount if amount is not None else CLIENT.annual_operating_payment
    n = years_until(payment_year, as_of_year)
    if flat_rate is not None:
        rate = flat_rate
        basis = f"Flat {flat_rate:.2%} planning assumption"
    else:
        curve = curve or treasury.get_curve()
        rate = treasury.yield_for(n, curve)
        basis = f"Treasury par yield interpolated at {n:.0f} years"
    pv = amount / ((1 + rate) ** n) if n > 0 else amount
    return {
        "payment_year": payment_year,
        "amount": amount,
        "years": n,
        "discount_rate": round(rate, 6),
        "discount_rate_pct": round(rate * 100, 3),
        "present_value": round(pv, 2),
        "basis": basis,
    }


def build_calendar(
    as_of_year: int,
    matched: list[MatchedAsset] | None = None,
    economic_capital: float = 0.0,
    flat_rate: float | None = None,
) -> dict:
    """The full ten year ladder with a funding state and present value per payment.

    `economic_capital` is the portfolio value available to the liability sleeve but
    not dedicated to a dated instrument. It is applied to the earliest unmatched
    payments, which is how a real reserve would be drawn down, and those payments are
    marked ECONOMICALLY_COVERED rather than MATCHED.
    """
    matched = matched or []
    curve = treasury.get_curve()
    by_year: dict[int, float] = {}
    notes: dict[int, list[str]] = {}
    for m in matched:
        by_year[m.payment_year] = by_year.get(m.payment_year, 0.0) + m.expected_cash_flow
        notes.setdefault(m.payment_year, []).append(
            f"{m.ticker}: {m.note or 'dedicated cash flow'} of ${m.expected_cash_flow:,.0f}"
        )

    payments = []
    remaining_capital = economic_capital
    required = CLIENT.annual_operating_payment

    for year in CLIENT.liability_years:
        dedicated = by_year.get(year, 0.0)
        pv = present_value(year, as_of_year, curve, flat_rate=flat_rate)

        if year < as_of_year:
            state: FundingState = "PAID"
            shortfall = 0.0
        elif dedicated >= required:
            state = "MATCHED"
            shortfall = 0.0
        elif dedicated > 0:
            state = "PARTIALLY_FUNDED"
            shortfall = required - dedicated
        else:
            shortfall = required
            state = "UNFUNDED"

        if state in ("UNFUNDED", "PARTIALLY_FUNDED") and remaining_capital > 0:
            cost_today = shortfall / ((1 + pv["discount_rate"]) ** pv["years"]) if pv["years"] > 0 else shortfall
            if remaining_capital >= cost_today:
                remaining_capital -= cost_today
                state = "ECONOMICALLY_COVERED"

        payments.append({
            "year": year,
            "required": required,
            "dedicated_cash_flow": round(dedicated, 2),
            "surplus": round(dedicated - required, 2) if dedicated else 0.0,
            "shortfall": round(shortfall, 2),
            "state": state,
            "state_description": STATE_DESCRIPTIONS[state],
            "present_value": pv["present_value"],
            "discount_rate_pct": pv["discount_rate_pct"],
            "years_away": pv["years"],
            "notes": notes.get(year, []),
        })

    counts: dict[str, int] = {}
    for p in payments:
        counts[p["state"]] = counts.get(p["state"], 0) + 1

    total_pv = sum(p["present_value"] for p in payments if p["state"] not in ("MATCHED", "PAID"))
    matched_count = counts.get("MATCHED", 0) + counts.get("PAID", 0)

    return {
        "as_of_year": as_of_year,
        "payments": payments,
        "total_nominal": CLIENT.total_nominal_liability,
        "matched_count": matched_count,
        "state_counts": counts,
        "cost_to_secure_remaining": round(total_pv, 2),
        "cost_to_secure_note": (
            "What it would cost today to buy every payment that is not already matched, "
            "discounted at the Treasury yield for each payment's own maturity."
        ),
        "curve": {
            "as_of": curve.get("as_of"),
            "source": curve.get("source"),
            "source_url": curve.get("source_url"),
            "degraded": curve.get("degraded", False),
            "note": curve.get("note"),
            "points": curve.get("points", []),
        },
        "residual_economic_capital": round(max(0.0, remaining_capital), 2),
    }


def ladder_candidates(payment_year: int) -> list[dict]:
    """Registry instruments whose defined maturity could carry a given payment year."""
    from .registry import _registry

    out = []
    for ticker, fund in _registry().get("funds", {}).items():
        if not fund.get("has_maturity_date"):
            continue
        my = fund.get("maturity_year")
        if my is None:
            continue
        out.append({
            "ticker": ticker,
            "name": fund.get("name"),
            "maturity_year": my,
            "termination_date": fund.get("termination_date"),
            "sec_yield_pct": fund.get("sec_yield_pct"),
            "fits": my <= payment_year,
            "gap_years": my - payment_year,
        })
    return sorted(out, key=lambda x: abs(x["gap_years"]))


def ladder_coverage_report() -> dict:
    """Which of Laura's ten years can be matched with instruments we actually hold data for.

    This surfaces a real constraint rather than hiding it: the defined maturity
    Treasury funds in the registry stop well short of 2042, so the back half of the
    ladder needs individual Treasuries or STRIPS instead.
    """
    from .registry import _registry

    available = sorted(
        fund.get("maturity_year")
        for fund in _registry().get("funds", {}).values()
        if fund.get("has_maturity_date") and fund.get("maturity_year")
    )
    covered = [y for y in CLIENT.liability_years if y in available]
    uncovered = [y for y in CLIENT.liability_years if y not in available]
    return {
        "instrument_maturities_available": available,
        "years_coverable_by_registry": covered,
        "years_requiring_direct_treasuries": uncovered,
        "finding": (
            f"Defined maturity Treasury funds in the registry reach {max(available)}. "
            f"The {len(uncovered)} payments from {min(uncovered)} to {max(uncovered)} cannot be matched "
            "with a dated fund and need individual Treasuries or STRIPS, bought directly."
            if uncovered and available else
            "Every payment year can be matched with a dated instrument in the registry."
        ),
    }
