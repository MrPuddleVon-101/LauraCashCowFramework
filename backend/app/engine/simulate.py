"""Monte Carlo, stress tests and facility capacity. PRD 38, 39, 46, 47, 48.

PRD 39 is blunt about the spirit of this: use Monte Carlo as a scenario tool, not as
fake precision. Returns are drawn from a Student-t distribution rather than a normal
one, because the normal assumption understates exactly the kind of year that would
threaten Laura's ladder.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..config import CLIENT, POLICY
from ..providers import treasury
from .liability import present_value

DEFAULT_PATHS = 10_000
SEED = 20261002  # fixed so a committee can reproduce any number the app showed them

# Long-run capital market assumptions used for projection. These are team planning
# inputs, not observed facts, and are surfaced as such everywhere they are used.
@dataclass
class Assumptions:
    equity_return: float = 0.072
    equity_vol: float = 0.165
    bond_return: float = 0.045
    bond_vol: float = 0.055
    correlation: float = 0.15
    t_degrees_freedom: int = 5
    inflation: float = 0.025

    def to_dict(self) -> dict:
        return {
            "equity_return_pct": round(self.equity_return * 100, 2),
            "equity_vol_pct": round(self.equity_vol * 100, 2),
            "bond_return_pct": round(self.bond_return * 100, 2),
            "bond_vol_pct": round(self.bond_vol * 100, 2),
            "correlation": self.correlation,
            "t_degrees_freedom": self.t_degrees_freedom,
            "inflation_pct": round(self.inflation * 100, 2),
            "basis": (
                "Team planning assumptions, not observed facts. Fat tails are modelled with a "
                f"Student-t at {self.t_degrees_freedom} degrees of freedom rather than a normal distribution."
            ),
        }


def _draw(rng: np.random.Generator, n_paths: int, n_years: int, a: Assumptions) -> tuple[np.ndarray, np.ndarray]:
    """Correlated fat-tailed annual returns for the equity and bond sleeves."""
    df = a.t_degrees_freedom
    # Scale the t so its variance matches the target volatility.
    scale = np.sqrt((df - 2) / df) if df > 2 else 1.0

    z1 = rng.standard_t(df, size=(n_paths, n_years)) * scale
    z2 = rng.standard_t(df, size=(n_paths, n_years)) * scale
    rho = a.correlation
    z2 = rho * z1 + np.sqrt(max(0.0, 1 - rho * rho)) * z2

    equity = a.equity_return + a.equity_vol * z1
    bond = a.bond_return + a.bond_vol * z2
    return equity, bond


def project(
    equity_weight: float = 0.62,
    assumptions: Assumptions | None = None,
    n_paths: int = DEFAULT_PATHS,
    ladder_payments_secured: int | None = None,
    flat_yield: float | None = None,
) -> dict:
    """Project Laura's portfolio from the 2027 contribution to the 2033 decision point.

    The model follows the case study: $300,000 at the beginning of 2027, $150,000 at
    the beginning of 2028, nothing in or out until 2033. Capital earmarked for the
    payment ladder is held in dated bonds and grows at the bond rate with far less
    dispersion, which is the whole point of matching.
    """
    a = assumptions or Assumptions()
    rng = np.random.default_rng(SEED)
    secured = POLICY.payments_targeted_for_early_matching if ladder_payments_secured is None else ladder_payments_secured
    secured = max(0, min(CLIENT.operating_payments_count, secured))

    curve = treasury.get_curve()

    # Cost today of buying the first `secured` payments outright.
    ladder_cost_2027 = 0.0
    for i in range(secured):
        year = CLIENT.first_payment_year + i
        pv = present_value(year, 2027, curve, flat_rate=flat_yield)
        ladder_cost_2027 += pv["present_value"]

    years = CLIENT.residency_start_year - 2027  # 2027 through to the start of 2033
    equity, bond = _draw(rng, n_paths, years, a)

    # 2027: fund as much of the ladder as the first contribution allows, invest the rest.
    ladder = np.full(n_paths, min(ladder_cost_2027, CLIENT.contribution_2027))
    growth = np.full(n_paths, max(0.0, CLIENT.contribution_2027 - ladder[0]))
    ladder_shortfall = max(0.0, ladder_cost_2027 - CLIENT.contribution_2027)

    for t in range(years):
        if t == 1:  # beginning of 2028
            # Second contribution tops up the ladder first, then the growth sleeve.
            top_up = min(ladder_shortfall, CLIENT.contribution_2028)
            ladder = ladder + top_up
            growth = growth + (CLIENT.contribution_2028 - top_up)
            ladder_shortfall -= top_up

        g_ret = equity[:, t] * equity_weight + bond[:, t] * (1 - equity_weight)
        growth = growth * (1 + g_ret)
        ladder = ladder * (1 + bond[:, t] * 0.35 + a.bond_return * 0.65)

    total_2033 = growth + ladder

    # In 2033 the operating reserve is established before anything goes to the facility.
    reserve_needed = 0.0
    for i in range(secured, CLIENT.operating_payments_count):
        year = CLIENT.first_payment_year + i
        reserve_needed += present_value(year, CLIENT.residency_start_year, curve, flat_rate=flat_yield)["present_value"]

    after_reserve = np.maximum(0.0, total_2033 - reserve_needed)
    fundable = (total_2033 >= reserve_needed) if secured < CLIENT.operating_payments_count else np.ones(n_paths, dtype=bool)
    # A matched payment is matched regardless of the growth sleeve, so funding
    # probability only depends on covering the payments that are still unsecured.
    funding_probability = float(np.mean(fundable))

    # PRD 47. Operating payments have priority, so capacity is what survives the
    # reserve and the retained growth target. The team's $100,000 cap is a policy
    # recommendation applied on top, not a property of the portfolio, so both are
    # reported. Collapsing them would hide the distribution behind a flat line.
    raw_capacity = np.maximum(0.0, after_reserve - POLICY.retained_growth_target)
    recommended = np.minimum(raw_capacity, POLICY.provisional_facility_cap)
    facility_capacity = raw_capacity

    def pct(arr: np.ndarray, q: float) -> float:
        return float(np.percentile(arr, q))

    return {
        "paths": n_paths,
        "equity_weight": equity_weight,
        "payments_secured_by_2028": secured,
        "ladder_cost_2027": round(ladder_cost_2027, 2),
        "ladder_fully_funded_by_2028": bool(ladder_shortfall <= 1.0),
        "reserve_needed_2033": round(reserve_needed, 2),
        "funding_probability": round(funding_probability, 4),
        "meets_policy_threshold": bool(funding_probability >= POLICY.required_funding_probability),
        "portfolio_2033": {
            "p10": round(pct(total_2033, 10), 2),
            "p25": round(pct(total_2033, 25), 2),
            "median": round(pct(total_2033, 50), 2),
            "p75": round(pct(total_2033, 75), 2),
            "p90": round(pct(total_2033, 90), 2),
            "mean": round(float(np.mean(total_2033)), 2),
        },
        "facility_capacity": {
            "pessimistic_p10": round(pct(raw_capacity, 10), 2),
            "p25": round(pct(raw_capacity, 25), 2),
            "median": round(pct(raw_capacity, 50), 2),
            "p75": round(pct(raw_capacity, 75), 2),
            "optimistic_p90": round(pct(raw_capacity, 90), 2),
            "probability_above_zero": round(float(np.mean(raw_capacity > 0)), 4),
            "basis": "Uncapped. What the portfolio could afford after the operating reserve and the $100,000 retained growth target.",
        },
        "facility_recommended": {
            "pessimistic_p10": round(pct(recommended, 10), 2),
            "median": round(pct(recommended, 50), 2),
            "optimistic_p90": round(pct(recommended, 90), 2),
            "cap": POLICY.provisional_facility_cap,
            "basis": f"The team's ${POLICY.provisional_facility_cap:,.0f} policy cap applied to the figures above.",
        },
        "retained_growth_target": POLICY.retained_growth_target,
        "assumptions": a.to_dict(),
        "curve_as_of": curve.get("as_of"),
        "curve_source": curve.get("source"),
        "seed": SEED,
        "reproducibility": "Fixed seed. Any figure shown can be regenerated exactly.",
        "_distribution": total_2033,
        "_facility": raw_capacity,
        "_recommended": recommended,
    }


def sponsor_range(sim: dict, confidence: float = 0.80) -> dict:
    """PRD 48. The range Laura can credibly quote to co-sponsors in 2031.

    A range is only credible if the operating commitment survives at the bottom of it,
    so the lower bound is taken from the unfavourable tail rather than the median.
    """
    facility = sim["_facility"]
    lower_q = (1 - confidence) / 2 * 100
    upper_q = (1 + confidence) / 2 * 100
    low = float(np.percentile(facility, lower_q))
    high = float(np.percentile(facility, upper_q))

    # Round outward to figures a person would actually say out loud. Cast back to
    # Python floats: numpy scalars travel fine inside the engine but cannot be
    # serialised into a JSON response.
    low_r = float(max(0.0, np.floor(low / 5_000) * 5_000))
    high_r = float(np.ceil(high / 5_000) * 5_000)

    supported = sim["funding_probability"] >= POLICY.required_funding_probability

    return {
        "confidence": confidence,
        "low": round(low_r, 2),
        "high": round(high_r, 2),
        "raw_low": round(low, 2),
        "raw_high": round(high, 2),
        "median": round(float(np.percentile(facility, 50)), 2),
        "supported": bool(supported),
        "warning": None if supported else (
            "This range is not sufficiently supported by current portfolio outcomes. "
            f"Modelled funding probability is {sim['funding_probability']:.1%}, below the "
            f"{POLICY.required_funding_probability:.0%} policy floor, so the operating "
            "commitment must be repaired before any facility figure is communicated."
        ),
        "policy_cap": POLICY.provisional_facility_cap,
        "exceeds_policy_cap": bool(low_r > POLICY.provisional_facility_cap),
        "statement": (
            f"Based on current portfolio conditions, Laura can communicate a facility contribution "
            f"range of ${low_r:,.0f} to ${high_r:,.0f} with approximately {confidence:.0%} modelled "
            f"confidence while retaining full operating funding."
        ),
        "policy_note": (
            f"The modelled range sits above the team's ${POLICY.provisional_facility_cap:,.0f} provisional cap. "
            "That cap was set against a 4% yield assumption. With the ladder now costing less to secure at "
            "current Treasury yields, the cap is the binding constraint rather than the portfolio, and the "
            "committee should decide whether to raise it rather than quietly quoting a larger figure."
            if low_r > POLICY.provisional_facility_cap else
            f"The modelled range sits within the team's ${POLICY.provisional_facility_cap:,.0f} provisional cap."
        ),
    }


# --- PRD 46: deterministic stress tests -------------------------------------------

SCENARIOS: list[dict] = [
    {"key": "broad_equity", "name": "Broad equity shock", "equity": -0.30, "bond": 0.02,
     "description": "U.S. equities fall 30 percent."},
    {"key": "growth_shock", "name": "Growth shock", "equity": -0.45, "bond": 0.03,
     "description": "Growth and technology stocks fall 45 percent."},
    {"key": "recession", "name": "Recession", "equity": -0.22, "bond": 0.05,
     "description": "Revenue growth and margins decline across the book."},
    {"key": "rate_up", "name": "Rate shock up", "equity": -0.12, "bond": -0.09,
     "description": "Rates rise 200 basis points."},
    {"key": "rate_down", "name": "Rate shock down", "equity": 0.05, "bond": 0.09,
     "description": "Rates fall 200 basis points."},
    {"key": "fx", "name": "International currency shock", "equity": -0.06, "bond": 0.0,
     "description": "The dollar appreciates 15 percent against foreign holdings."},
    {"key": "concentration", "name": "Concentration shock", "equity": -0.14, "bond": 0.0,
     "description": "The largest underlying position falls 40 percent."},
]


def stress_test(portfolio_value: float, equity_weight: float, as_of_year: int,
                payments_secured: int | None = None, flat_yield: float | None = None) -> dict:
    """Run every scenario and report whether the 95 percent objective survives each one."""
    secured = POLICY.payments_targeted_for_early_matching if payments_secured is None else payments_secured
    curve = treasury.get_curve()

    reserve_needed = 0.0
    for i in range(secured, CLIENT.operating_payments_count):
        year = CLIENT.first_payment_year + i
        reserve_needed += present_value(year, max(as_of_year, 2027), curve, flat_rate=flat_yield)["present_value"]

    equity_value = portfolio_value * equity_weight
    bond_value = portfolio_value * (1 - equity_weight)

    results = []
    for s in SCENARIOS:
        after = equity_value * (1 + s["equity"]) + bond_value * (1 + s["bond"])
        loss = after - portfolio_value
        surplus = after - reserve_needed
        results.append({
            "key": s["key"],
            "name": s["name"],
            "description": s["description"],
            "equity_move_pct": round(s["equity"] * 100, 1),
            "bond_move_pct": round(s["bond"] * 100, 1),
            "post_shock_value": round(after, 2),
            "loss": round(loss, 2),
            "loss_pct": round(loss / portfolio_value * 100, 2) if portfolio_value else 0.0,
            "reserve_needed": round(reserve_needed, 2),
            "surplus_after_reserve": round(surplus, 2),
            "facility_capacity": round(max(0.0, surplus - POLICY.retained_growth_target), 2),
            "objective_survives": bool(surplus >= 0),
        })

    return {
        "portfolio_value": round(portfolio_value, 2),
        "equity_weight": equity_weight,
        "reserve_needed": round(reserve_needed, 2),
        "payments_secured": secured,
        "scenarios": results,
        "worst_case": min(results, key=lambda r: r["post_shock_value"])["name"],
        "all_survive": all(r["objective_survives"] for r in results),
        "curve_as_of": curve.get("as_of"),
    }
