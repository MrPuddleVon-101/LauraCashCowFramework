"""Client facts and team policy.

PRD section 5 is explicit that these two things must never be mixed. Everything in
CLIENT_CONFIG comes from the Wharton case study and is immutable for the duration of the
competition. Everything in TEAM_POLICY is a Cash Cows decision that can be revised, and
revising it creates a new framework version.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Literal

FRAMEWORK_VERSION = "LCCF-1.2.0"
FRAMEWORK_AUTHOR = "Cash Cows investment team"
FRAMEWORK_LOCKED_ON = "2026-10-05"
FRAMEWORK_CHANGE_REASON = (
    "Audit remediation. Dedicated ladder capital is no longer counted as spendable; "
    "liability matching compares real cash-arrival dates rather than calendar years; "
    "the three dated Treasury fund identities were corrected; protection mode now makes "
    "a risky holding score worse rather than better; a balance sheet ratio is no longer "
    "read as a trading spread; peer ties are neutral and nonfinite inputs are rejected. "
    "Scores from earlier versions are not comparable with these."
)# Year 0 is 2026. Subtract 2026 from a calendar year to get its year number.
BASE_YEAR = 2026


@dataclass(frozen=True)
class ClientConfig:
    """Authoritative financial inputs. Case study facts only."""

    client_name: str = "Laura Gao"
    base_currency: str = "USD"
    contribution_2027: float = 300_000.0
    contribution_2028: float = 150_000.0
    residency_start_year: int = 2033
    annual_operating_payment: float = 50_000.0
    first_payment_year: int = 2033
    last_payment_year: int = 2042
    operating_payments_count: int = 10
    sponsor_conversation_year: int = 2031
    facility_contribution_priority: str = "SECONDARY_TO_OPERATING_RESERVE"
    liquidity_priority: str = "MODERATE_HIGH"
    growth_priority: str = "HIGH_FOR_SURPLUS_CAPITAL"
    risk_willingness: str = "THOUGHTFUL_RISK"
    risk_capacity: str = "DYNAMIC_BY_GOAL"
    normal_living_expenses_paid_elsewhere: bool = True

    @property
    def total_nominal_liability(self) -> float:
        return self.annual_operating_payment * self.operating_payments_count

    @property
    def liability_years(self) -> list[int]:
        return list(range(self.first_payment_year, self.last_payment_year + 1))


@dataclass
class TeamPolicy:
    """Cash Cows strategy. Editable, version controlled."""

    required_funding_probability: float = 0.95
    payments_targeted_for_early_matching: int = 8
    early_matching_first_year: int = 2033
    early_matching_last_year: int = 2040
    provisional_facility_planning_amount: float = 40_000.0
    provisional_facility_cap: float = 100_000.0
    retained_growth_target: float = 100_000.0
    illustrative_yield_assumption: float = 0.04

    # Position sizing ceilings, expressed as a share of the growth sleeve (PRD 44).
    max_broad_core_etf: float = 0.45
    max_international_etf: float = 0.30
    max_individual_stock: float = 0.08
    max_thematic_etf: float = 0.12
    lookthrough_issuer_warning: float = 0.08

    # Signal thresholds (PRD 42).
    # Thresholds are expressed on the calibrated scale documented in
    # normalize.PERCENTILE_CURVE, where a median reading scores 62, a top-quartile
    # reading scores about 77 and a top-decile reading scores 88.
    #
    # They used to assume a scale on which rank mapped straight onto score. On that
    # scale a weighted mean of twenty percentiles could not reach 70, so every
    # candidate was RED and the ladder carried no information at all. Measured over a
    # 52 name spread of funds, Treasuries, mega caps and genuinely weak businesses,
    # the figures below give roughly 10% amber plus, 54% amber and 37% red, and green
    # stays rare without being arithmetically impossible.
    green_min_sqs: float = 85.0
    green_min_lpfs: float = 85.0
    green_min_ccs: float = 85.0
    green_min_dcs: float = 85.0
    amber_plus_min_ccs: float = 78.0
    amber_plus_min_component: float = 72.0
    amber_min_ccs: float = 66.0
    # Below the median company on a weighted basis. Reject.
    red_max_sqs: float = 60.0
    red_max_lpfs: float = 60.0
    insufficient_data_dcs: float = 70.0

    # Composite exponents (PRD 41). Laura fit is deliberately weighted above raw quality.
    sqs_exponent: float = 0.45
    lpfs_exponent: float = 0.55

    # Risk state triggers (PRD 40).
    growth_mode_min_years: int = 4
    growth_mode_min_probability: float = 0.97
    balanced_mode_min_years: int = 2

    # Missing data ceiling (PRD 60).
    max_missing_weight_for_green: float = 0.20


CLIENT = ClientConfig()
POLICY = TeamPolicy()


RISK_STATES = ("GROWTH", "BALANCED", "PROTECTION")
RiskState = Literal["GROWTH", "BALANCED", "PROTECTION"]


def risk_state(as_of_year: int, funding_probability: float) -> tuple[RiskState, str]:
    """PRD 40. Laura's risk capacity is not static, so the framework changes behaviour.

    Returns the state and the trigger that produced it, so the interface can explain
    itself rather than asserting a mode.
    """
    years_remaining = CLIENT.residency_start_year - as_of_year

    if years_remaining < POLICY.balanced_mode_min_years:
        return "PROTECTION", f"Fewer than {POLICY.balanced_mode_min_years} years remain before 2033."
    if funding_probability < POLICY.required_funding_probability:
        return (
            "PROTECTION",
            f"Modelled funding probability {funding_probability:.1%} is below the "
            f"{POLICY.required_funding_probability:.0%} policy floor.",
        )
    if years_remaining >= POLICY.growth_mode_min_years and funding_probability >= POLICY.growth_mode_min_probability:
        return (
            "GROWTH",
            f"{years_remaining} years remain and funding probability is "
            f"{funding_probability:.1%}, at or above {POLICY.growth_mode_min_probability:.0%}.",
        )
    return (
        "BALANCED",
        f"{years_remaining} years remain with funding probability {funding_probability:.1%}. "
        "Liability protection carries more weight than it does in growth mode.",
    )


# Security roles (PRD 7). A candidate cannot be fit-scored without one.
ROLES: dict[str, str] = {
    "CG": "Core Growth",
    "SG": "Satellite Growth",
    "ID": "International Diversifier",
    "LM": "Liability Matcher",
    "LR": "Liquidity Reserve",
    "LG": "Long-Term Residual Growth",
    "DA": "Defensive Allocation",
}

ROLE_DESCRIPTIONS: dict[str, str] = {
    "CG": "The spine of the growth sleeve. Broad, diversified, held for the whole run to 2033.",
    "SG": "A researched individual position taken on top of the core, sized small on purpose.",
    "ID": "Exposure outside the United States, held to reduce single-country dependence.",
    "LM": "Dedicated to a specific $50,000 payment year. Certainty matters more than yield.",
    "LR": "Short-dated and liquid. Covers timing, not growth.",
    "LG": "Capital intended to stay invested after 2033 once the residency is funded.",
    "DA": "Ballast. Expected to behave differently from equities in a drawdown.",
}

# Which buckets each role belongs to (PRD 6).
ROLE_BUCKET: dict[str, str] = {
    "CG": "B", "SG": "B", "ID": "B", "LG": "C",
    "LM": "A", "LR": "A", "DA": "B",
}

BUCKETS: dict[str, dict[str, str]] = {
    "A": {
        "name": "Operating Liability Portfolio",
        "purpose": "Fund the ten $50,000 payments from 2033 to 2042.",
        "priority": "Certainty",
    },
    "B": {
        "name": "Growth Portfolio",
        "purpose": "Grow capital before 2033 to raise what Laura can put toward the facility.",
        "priority": "Growth, diversification, quality, acceptable valuation",
    },
    "C": {
        "name": "Flexibility / Residual Portfolio",
        "purpose": "Keep capital beyond the residency so one project does not absorb everything.",
        "priority": "Optionality",
    },
}


def framework_manifest() -> dict:
    return {
        "version": FRAMEWORK_VERSION,
        "author": FRAMEWORK_AUTHOR,
        "locked_on": FRAMEWORK_LOCKED_ON,
        "reason": FRAMEWORK_CHANGE_REASON,
        "client": asdict(CLIENT),
        "policy": asdict(POLICY),
        "roles": ROLES,
        "buckets": BUCKETS,
    }
