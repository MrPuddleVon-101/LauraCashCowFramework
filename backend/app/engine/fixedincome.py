"""Individual fixed income: identifiers, cash flows and liability matching.

A bond is not a stock with a different ticker. It has a coupon, a schedule, a
maturity and a face value, and the only question Laura actually needs answered
is whether its cash lands before a payment is due. That question is arithmetic,
not a score, so it is computed here from the instrument's own terms rather than
inferred from a price series.

The WInS competition identifies Treasuries like this:

    B-T-4.375-15112039
    │ │ │     └── maturity, DDMMYYYY
    │ │ └──────── coupon, percent of par
    │ └────────── T for Treasury
    └──────────── B for bond

Nothing here reaches a provider. Given the terms, every figure below is
determined, which is also why a dated Treasury can be trusted against a dated
liability in a way a bond fund cannot.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

#: B-T-<coupon>-<DDMMYYYY>. The coupon may carry decimals; the date may not.
WINS_BOND = re.compile(
    r"^(?P<kind>[A-Z])-(?P<issuer>[A-Z]+)-(?P<coupon>\d+(?:\.\d+)?)-(?P<maturity>\d{8})$",
    re.IGNORECASE,
)

ISSUER_LABELS = {"T": "U.S. Treasury"}


@dataclass
class Coupon:
    date: date
    amount: float
    kind: str = "coupon"          # coupon | coupon+principal
    supports_payment_year: int | None = None


@dataclass
class BondTerms:
    """Everything needed to price and schedule a bond, and nothing else."""

    identifier: str
    issuer: str
    coupon_rate: float                 # percent of par, per year
    maturity: date
    face_value: float = 100_000.0
    price_pct_of_par: float = 100.0
    frequency: int = 2                 # coupons per year
    currency: str = "USD"
    settlement: date | None = None
    callable: bool = False
    credit_quality: str = "US_TREASURY"
    cusip: str | None = None
    isin: str | None = None
    security_type: str = "treasury"
    source: str = "instrument terms"

    @property
    def annual_coupon(self) -> float:
        return self.face_value * self.coupon_rate / 100.0

    @property
    def coupon_amount(self) -> float:
        return self.annual_coupon / self.frequency


def parse_wins_identifier(ident: str) -> BondTerms | None:
    """Read a WInS bond identifier. Returns None if it is not one."""
    m = WINS_BOND.match((ident or "").strip())
    if not m:
        return None
    raw = m.group("maturity")
    try:
        maturity = date(int(raw[4:8]), int(raw[2:4]), int(raw[0:2]))
    except ValueError:
        return None
    issuer_code = m.group("issuer").upper()
    return BondTerms(
        identifier=ident.strip().upper(),
        issuer=ISSUER_LABELS.get(issuer_code, issuer_code),
        coupon_rate=float(m.group("coupon")),
        maturity=maturity,
        security_type="treasury" if issuer_code == "T" else "corporate_bond",
        credit_quality="US_TREASURY" if issuer_code == "T" else "UNRATED",
    )


def coupon_schedule(terms: BondTerms, from_date: date | None = None) -> list[Coupon]:
    """Every remaining payment, working backwards from maturity.

    Counting forward from issue drifts off the maturity date; a bond's schedule
    is anchored at its maturity, so this is built backwards and then reversed.
    """
    start = from_date or terms.settlement or date.today()
    step = 12 // max(1, terms.frequency)
    out: list[Coupon] = []
    y, m = terms.maturity.year, terms.maturity.month
    d = terms.maturity.day
    while True:
        try:
            when = date(y, m, min(d, 28) if m == 2 else d)
        except ValueError:
            when = date(y, m, 28)
        if when <= start:
            break
        is_final = (when == terms.maturity)
        out.append(Coupon(
            date=when,
            amount=terms.coupon_amount + (terms.face_value if is_final else 0.0),
            kind="coupon+principal" if is_final else "coupon",
        ))
        m -= step
        while m <= 0:
            m += 12
            y -= 1
        if y < start.year - 1:
            break
    return list(reversed(out))


def purchase_cost(terms: BondTerms) -> dict:
    """What it costs to buy, and the accrued interest owed to the seller."""
    clean = terms.face_value * terms.price_pct_of_par / 100.0
    settle = terms.settlement or date.today()
    sched = coupon_schedule(terms, from_date=settle)
    accrued = 0.0
    if sched:
        nxt = sched[0].date
        step_days = 365.0 / terms.frequency
        days_to_next = (nxt - settle).days
        elapsed = max(0.0, step_days - days_to_next)
        accrued = terms.coupon_amount * min(1.0, elapsed / step_days)
    return {
        "clean_price": round(clean, 2),
        "accrued_interest": round(accrued, 2),
        "dirty_price": round(clean + accrued, 2),
        "face_value": terms.face_value,
        "price_pct_of_par": terms.price_pct_of_par,
    }


def yield_to_maturity(terms: BondTerms, guess: float = 0.05) -> float | None:
    """Solve for the rate that discounts the schedule back to the dirty price.

    Bisection rather than Newton: it cannot diverge on a badly priced bond, and
    the range below covers anything that is not already in default.
    """
    settle = terms.settlement or date.today()
    sched = coupon_schedule(terms, from_date=settle)
    if not sched:
        return None
    target = purchase_cost(terms)["dirty_price"]

    def pv(rate: float) -> float:
        total = 0.0
        for c in sched:
            t = (c.date - settle).days / 365.0
            total += c.amount / ((1.0 + rate / terms.frequency) ** (terms.frequency * t))
        return total

    lo, hi = -0.9, 1.5
    if pv(lo) < target or pv(hi) > target:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if pv(mid) > target:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 6)


def durations(terms: BondTerms) -> dict:
    """Macaulay and modified duration, in years."""
    y = yield_to_maturity(terms)
    if y is None:
        return {"macaulay": None, "modified": None, "yield_to_maturity": None}
    settle = terms.settlement or date.today()
    sched = coupon_schedule(terms, from_date=settle)
    pv_total = 0.0
    weighted = 0.0
    for c in sched:
        t = (c.date - settle).days / 365.0
        pv = c.amount / ((1.0 + y / terms.frequency) ** (terms.frequency * t))
        pv_total += pv
        weighted += pv * t
    if pv_total <= 0:
        return {"macaulay": None, "modified": None, "yield_to_maturity": y}
    mac = weighted / pv_total
    return {
        "macaulay": round(mac, 4),
        "modified": round(mac / (1.0 + y / terms.frequency), 4),
        "yield_to_maturity": y,
    }


def liability_coverage(terms: BondTerms, payment_years: list[int],
                       payment_amount: float) -> dict:
    """Which of Laura's payments this bond's own cash can actually reach.

    A payment is due at the start of its year, so only cash that has already
    landed counts. Money is assigned to the earliest payment it can still reach
    and is not counted again for a later one, because a dollar spent in 2033 is
    not available in 2034.
    """
    settle = terms.settlement or date.today()
    sched = coupon_schedule(terms, from_date=settle)
    remaining = {y: payment_amount for y in payment_years}
    assigned: dict[int, float] = {y: 0.0 for y in payment_years}

    for c in sched:
        cash = c.amount
        for y in sorted(payment_years):
            if cash <= 0:
                break
            # Due 1 January of its year, so the cash must land before that.
            if c.date >= date(y, 1, 1):
                continue
            take = min(cash, remaining[y])
            if take > 0:
                assigned[y] += take
                remaining[y] -= take
                cash -= take
                c.supports_payment_year = y

    fully = [y for y in payment_years if remaining[y] <= 0.005]
    return {
        "assigned": {y: round(v, 2) for y, v in assigned.items() if v > 0},
        "shortfall": {y: round(v, 2) for y, v in remaining.items() if v > 0.005},
        "payments_fully_covered": fully,
        "payments_fully_covered_count": len(fully),
        "total_cash_before_last_payment": round(sum(assigned.values()), 2),
        "basis": (
            "Contractual coupons and principal only, assigned to the earliest payment "
            "each can still reach and never counted twice."
        ),
    }


def describe(terms: BondTerms, payment_years: list[int] | None = None,
             payment_amount: float = 50_000.0) -> dict:
    """The whole instrument, as figures that can each be checked by hand."""
    sched = coupon_schedule(terms)
    cost = purchase_cost(terms)
    dur = durations(terms)
    out = {
        "identifier": terms.identifier,
        "issuer": terms.issuer,
        "security_type": terms.security_type,
        "coupon_rate_pct": terms.coupon_rate,
        "coupon_frequency": terms.frequency,
        "maturity": terms.maturity.isoformat(),
        "face_value": terms.face_value,
        "currency": terms.currency,
        "callable": terms.callable,
        "credit_quality": terms.credit_quality,
        "cusip": terms.cusip,
        "isin": terms.isin,
        "settlement": (terms.settlement or date.today()).isoformat(),
        "purchase": cost,
        "coupon_amount": round(terms.coupon_amount, 2),
        "annual_coupon": round(terms.annual_coupon, 2),
        "remaining_payments": len(sched),
        "principal_repayment": terms.face_value,
        "principal_repaid_on": terms.maturity.isoformat(),
        "yield_to_maturity_pct": None if dur["yield_to_maturity"] is None
                                 else round(dur["yield_to_maturity"] * 100, 4),
        "macaulay_duration_years": dur["macaulay"],
        "modified_duration_years": dur["modified"],
        "schedule": [
            {"date": c.date.isoformat(), "amount": round(c.amount, 2), "kind": c.kind}
            for c in sched
        ],
        "source": terms.source,
        "basis": "Computed from the instrument's own terms. No provider is involved.",
    }
    if payment_years:
        out["liability_coverage"] = liability_coverage(terms, payment_years, payment_amount)
    return out
