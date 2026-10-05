"""When the money actually lands, against when it is actually owed.

The engine used to compare calendar years as integers, so a fund terminating in
December 2033 counted as a perfect match for a payment due at the start of
January 2033. It is eleven and a half months late. The explanation string even
said the December termination was "ahead of the payment at the start of that
year", which is the kind of sentence that survives review precisely because it
sounds orderly.

Everything that needs to know whether an instrument can pay a bill asks this
module, so the scorecard, the fit model, the Red Gate and the liability ledger
cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

#: Laura's operating payments fall due at the beginning of each year.
PAYMENT_MONTH = 1
PAYMENT_DAY = 1

#: A terminating fund does not hand over cash on its termination date. The
#: portfolio is liquidated, the final distribution is declared and paid, and the
#: proceeds then have to settle before they can be sent on. Fifteen days is a
#: working allowance, not an issuer guarantee, and it is deliberately on the
#: short side so the rule errs toward calling something late rather than early.
SETTLEMENT_DAYS = 15


def payment_date(year: int) -> date:
    """The date a given operating payment is actually due."""
    return date(year, PAYMENT_MONTH, PAYMENT_DAY)


def cash_available(termination: date, settlement_days: int = SETTLEMENT_DAYS) -> date:
    """The earliest date proceeds from a terminating instrument can be spent."""
    return termination + timedelta(days=settlement_days)


@dataclass
class Eligibility:
    """Whether an instrument's cash can meet a dated payment, and why."""

    ok: bool
    reason: str
    days_early: int | None = None
    cash_date: date | None = None
    due_date: date | None = None

    def to_dict(self) -> dict:
        return {
            "eligible": self.ok,
            "reason": self.reason,
            "days_early": self.days_early,
            "cash_available": self.cash_date.isoformat() if self.cash_date else None,
            "payment_due": self.due_date.isoformat() if self.due_date else None,
        }


def parse_termination(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def covers(termination: str | date | None, payment_year: int | None,
           settlement_days: int = SETTLEMENT_DAYS) -> Eligibility:
    """Can an instrument terminating on `termination` pay the `payment_year` bill?"""
    if payment_year is None:
        return Eligibility(False, "No payment year was nominated, so nothing is being matched.")

    due = payment_date(payment_year)
    term = termination if isinstance(termination, date) else parse_termination(termination)
    if term is None:
        return Eligibility(
            False,
            "No termination date on file, so the date the cash arrives is unknown.",
            due_date=due,
        )

    ready = cash_available(term, settlement_days)
    early = (due - ready).days
    if early < 0:
        return Eligibility(
            False,
            f"Terminates {term.isoformat()}, so proceeds are not expected to be usable until "
            f"about {ready.isoformat()}, which is {-early} days after the "
            f"{due.isoformat()} payment is due.",
            days_early=early, cash_date=ready, due_date=due,
        )
    return Eligibility(
        True,
        f"Terminates {term.isoformat()}, so proceeds should be usable by about "
        f"{ready.isoformat()}, {early} days before the {due.isoformat()} payment.",
        days_early=early, cash_date=ready, due_date=due,
    )


def match_score(elig: Eligibility) -> float:
    """Score a date match, given eligibility.

    Arriving early is good, but arriving a very long time early means the money
    sits in a matured instrument for years earning nothing in particular, so the
    curve peaks a few months ahead of the payment rather than at five years.
    """
    if not elig.ok or elig.days_early is None:
        return 4.0
    d = elig.days_early
    if d <= 30:
        return 88.0
    if d <= 120:
        return 100.0
    if d <= 400:
        return 92.0
    if d <= 800:
        return 68.0
    if d <= 1200:
        return 44.0
    return 24.0
