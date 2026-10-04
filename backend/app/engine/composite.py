"""Red Gate, composite score, signal logic and position sizing. PRD 9, 41 to 45.

The composite is a weighted geometric mean, not an average, because an average lets a
superb security hide a poor client fit. A 98 quality company that scores 65 for Laura
is a fantastic security and the wrong client, and the arithmetic should say so.
"""

from __future__ import annotations

from ..config import CLIENT, POLICY, ROLES
from .registry import ROLES_FOR_TYPE

SIGNALS = ("GREEN", "AMBER_PLUS", "AMBER", "RED", "INSUFFICIENT_DATA")

SIGNAL_LABELS = {
    "GREEN": "Green",
    "AMBER_PLUS": "Amber plus",
    "AMBER": "Amber",
    "RED": "Red",
    "INSUFFICIENT_DATA": "Insufficient data",
}

SIGNAL_MEANINGS = {
    "GREEN": "High conviction Cash Cow candidate. Green is meant to be rare.",
    "AMBER_PLUS": "Strong candidate requiring committee review.",
    "AMBER": "Potentially useful, but meaningful weaknesses exist.",
    "RED": "Reject under current conditions.",
    "INSUFFICIENT_DATA": "No investment conclusion permitted.",
}


def composite(sqs: float, lpfs: float) -> float:
    """CCS = 100 x (SQS/100)^0.45 x (LPFS/100)^0.55."""
    s = max(0.0, min(100.0, sqs)) / 100.0
    l = max(0.0, min(100.0, lpfs)) / 100.0
    if s <= 0 or l <= 0:
        return 0.0
    return round(100.0 * (s ** POLICY.sqs_exponent) * (l ** POLICY.lpfs_exponent), 1)


def red_gate(
    *,
    asset_type: str,
    role: str,
    fund: dict | None,
    dcs: float,
    missing_weight_share: float,
    funding_probability: float,
    post_trade_funding_probability: float | None,
    position_pct: float,
    lookthrough_issuer_pct: float | None,
    candidate_adds_to_top_issuer: bool = False,
    top_issuer: str | None = None,
    competition_mode: bool = False,
) -> dict:
    """PRD 9. Runs before numerical scoring. A hard failure cannot be outscored."""
    failures: list[dict] = []
    reviews: list[dict] = []

    def fail(key: str, detail: str) -> None:
        failures.append({"key": key, "detail": detail})

    def review(key: str, detail: str) -> None:
        reviews.append({"key": key, "detail": detail})

    # Universal hard failures.
    if dcs < POLICY.insufficient_data_dcs:
        fail("data_quality", f"Data confidence is {dcs:.0f}, below the {POLICY.insufficient_data_dcs:.0f} floor. "
                            "Essential data is missing or unreliable.")
    if missing_weight_share > POLICY.max_missing_weight_for_green:
        review("missing_data", f"{missing_weight_share:.0%} of weighted inputs are unavailable, above the "
                               f"{POLICY.max_missing_weight_for_green:.0%} ceiling. No green signal is permitted.")

    valid_roles = ROLES_FOR_TYPE.get(asset_type, [])
    if valid_roles and role not in valid_roles:
        review("role_mismatch",
               f"{ROLES.get(role, role)} is an unusual role for a {asset_type.replace('_', ' ')}. "
               f"Roles normally scored for this asset type: {', '.join(ROLES.get(r, r) for r in valid_roles)}.")

    # Position limits are team policy, not client facts, and are editable.
    limit_map = {
        "broad_us_equity": ("broad core ETF", POLICY.max_broad_core_etf),
        "international_equity": ("international diversified ETF", POLICY.max_international_etf),
        "stock": ("individual stock", POLICY.max_individual_stock),
        "thematic_sector": ("thematic ETF", POLICY.max_thematic_etf),
    }
    if asset_type in limit_map:
        label, cap = limit_map[asset_type]
        if position_pct / 100.0 > cap:
            fail("concentration_limit",
                 f"A {position_pct:.1f}% position breaches the team's {cap:.0%} ceiling for a {label}.")

    # A concentration warning belongs to the candidate only when the candidate is part
    # of the cause. Flagging a cash reserve because the portfolio already leans on one
    # chip maker would make the gate meaningless.
    if (
        lookthrough_issuer_pct is not None
        and lookthrough_issuer_pct / 100.0 > POLICY.lookthrough_issuer_warning
        and candidate_adds_to_top_issuer
    ):
        review("lookthrough_concentration",
               f"{top_issuer or 'The largest look-through issuer'} reaches {lookthrough_issuer_pct:.1f}% of the "
               f"portfolio after this trade, above the {POLICY.lookthrough_issuer_warning:.0%} warning level, and "
               "this candidate adds to it.")

    if post_trade_funding_probability is not None:
        if post_trade_funding_probability < POLICY.required_funding_probability:
            fail("funding_probability",
                 f"The trade leaves modelled operating funding probability at "
                 f"{post_trade_funding_probability:.1%}, below the {POLICY.required_funding_probability:.0%} "
                 "policy threshold.")

    # Liability-matching hard failures. PRD 9 and 23.
    if role == "LM":
        if not (fund or {}).get("has_maturity_date"):
            fail("no_maturity",
                 "Proposed as a liability matcher but the instrument has no maturity date. A normal bond "
                 "fund does not guarantee a future $50,000 payment because its value on that date is unknown.")
        if (fund or {}).get("callable"):
            fail("call_risk", "Callable, so the expected cash flow can be removed before Laura needs it.")
        currency = (fund or {}).get("currency", "USD")
        if currency != "USD":
            fail("currency", f"Denominated in {currency} against a US dollar obligation, with no hedge on file.")

    if asset_type in ("thematic_sector",) and role in ("CG",):
        review("role_quality",
               "A thematic fund proposed as core growth. PRD 20 is explicit that a thematic fund cannot "
               "inherit a broad fund's diversification credit.")

    leveraged = (fund or {}).get("leveraged") or (fund or {}).get("inverse")
    if leveraged:
        fail("leverage", "Leveraged or inverse product. Not permitted without an explicit written justification.")

    status = "FAIL" if failures else ("REVIEW" if reviews else "PASS")
    return {
        "status": status,
        "failures": failures,
        "reviews": reviews,
        "summary": (
            failures[0]["detail"] if failures else
            (reviews[0]["detail"] if reviews else "No Red Gate condition was triggered.")
        ),
    }


def signal(*, sqs: float, lpfs: float, ccs: float, dcs: float, gate: dict,
           missing_weight_share: float) -> dict:
    """PRD 42. Green requires every condition, which is why green should be rare."""
    reasons: list[str] = []

    if dcs < POLICY.insufficient_data_dcs:
        return {
            "signal": "INSUFFICIENT_DATA",
            "label": SIGNAL_LABELS["INSUFFICIENT_DATA"],
            "meaning": SIGNAL_MEANINGS["INSUFFICIENT_DATA"],
            "reasons": [f"Data confidence {dcs:.0f} is below {POLICY.insufficient_data_dcs:.0f}."],
        }

    if gate["status"] == "FAIL":
        return {
            "signal": "RED", "label": SIGNAL_LABELS["RED"], "meaning": SIGNAL_MEANINGS["RED"],
            "reasons": [f["detail"] for f in gate["failures"]],
        }
    if sqs < POLICY.red_max_sqs:
        reasons.append(f"Security quality {sqs:.0f} is below {POLICY.red_max_sqs:.0f}.")
    if lpfs < POLICY.red_max_lpfs:
        reasons.append(f"Laura fit {lpfs:.0f} is below {POLICY.red_max_lpfs:.0f}.")
    if reasons:
        return {"signal": "RED", "label": SIGNAL_LABELS["RED"], "meaning": SIGNAL_MEANINGS["RED"], "reasons": reasons}

    green_blockers: list[str] = []
    if gate["status"] != "PASS":
        green_blockers.append("Red Gate is in review rather than passing.")
    if sqs < POLICY.green_min_sqs:
        green_blockers.append(f"Security quality {sqs:.0f} is below the {POLICY.green_min_sqs:.0f} green threshold.")
    if lpfs < POLICY.green_min_lpfs:
        green_blockers.append(f"Laura fit {lpfs:.0f} is below the {POLICY.green_min_lpfs:.0f} green threshold.")
    if ccs < POLICY.green_min_ccs:
        green_blockers.append(f"Composite {ccs:.0f} is below the {POLICY.green_min_ccs:.0f} green threshold.")
    if dcs < POLICY.green_min_dcs:
        green_blockers.append(f"Data confidence {dcs:.0f} is below the {POLICY.green_min_dcs:.0f} green threshold.")
    if missing_weight_share > POLICY.max_missing_weight_for_green:
        green_blockers.append(
            f"{missing_weight_share:.0%} of weighted inputs are unavailable, above the "
            f"{POLICY.max_missing_weight_for_green:.0%} ceiling."
        )

    if not green_blockers:
        return {
            "signal": "GREEN", "label": SIGNAL_LABELS["GREEN"], "meaning": SIGNAL_MEANINGS["GREEN"],
            "reasons": ["Red Gate passed and all four scores cleared their thresholds."],
        }

    if ccs >= POLICY.amber_plus_min_ccs and min(sqs, lpfs) >= POLICY.amber_plus_min_component:
        return {
            "signal": "AMBER_PLUS", "label": SIGNAL_LABELS["AMBER_PLUS"],
            "meaning": SIGNAL_MEANINGS["AMBER_PLUS"], "reasons": green_blockers,
        }

    return {
        "signal": "AMBER", "label": SIGNAL_LABELS["AMBER"], "meaning": SIGNAL_MEANINGS["AMBER"],
        "reasons": green_blockers,
    }


def position_sizing(*, asset_type: str, role: str, ccs: float, dcs: float,
                    lookthrough_issuer_pct: float | None, signal_key: str) -> dict:
    """PRD 44. A green signal does not mean buy as much as possible."""
    caps = {
        "broad_us_equity": POLICY.max_broad_core_etf,
        "international_equity": POLICY.max_international_etf,
        "stock": POLICY.max_individual_stock,
        "thematic_sector": POLICY.max_thematic_etf,
    }
    policy_cap = caps.get(asset_type, 0.25)

    # Confidence scales the cap. A green at high data confidence earns the full
    # allowance; an amber on thin data does not.
    conviction = {"GREEN": 1.0, "AMBER_PLUS": 0.7, "AMBER": 0.4, "RED": 0.0, "INSUFFICIENT_DATA": 0.0}
    factor = conviction.get(signal_key, 0.3) * min(1.0, dcs / 90.0)
    suggested = policy_cap * factor

    constraints = [f"Team ceiling for this asset type is {policy_cap:.0%} of the growth sleeve."]
    if signal_key not in ("GREEN",):
        constraints.append(f"Signal is {SIGNAL_LABELS.get(signal_key, signal_key)}, so the allowance is reduced.")
    if dcs < 90:
        constraints.append(f"Data confidence of {dcs:.0f} scales the allowance down.")
    if lookthrough_issuer_pct is not None and lookthrough_issuer_pct / 100 > POLICY.lookthrough_issuer_warning:
        suggested = min(suggested, policy_cap * 0.5)
        constraints.append(
            f"Look-through exposure to the largest issuer is already {lookthrough_issuer_pct:.1f}%."
        )

    return {
        "policy_cap_pct": round(policy_cap * 100, 1),
        "suggested_pct": round(max(0.0, suggested) * 100, 1),
        "constraints": constraints,
        "note": "These limits are team policy defaults, not facts from Laura's case, and are editable.",
    }


def review_triggers(asset_type: str, role: str, fund: dict | None) -> list[str]:
    """PRD 54. Every approved holding needs explicit conditions that reopen the decision."""
    out = [
        f"Modelled operating funding probability falls below {POLICY.required_funding_probability:.0%}.",
        "Laura's stated objectives or the residency timeline change.",
    ]
    if asset_type == "stock":
        out += [
            "The earnings thesis breaks, or free cash flow deteriorates for two consecutive filings.",
            "Net leverage rises materially above the level recorded at purchase.",
            "Valuation moves above the top of its own five year range without an earnings justification.",
        ]
    elif asset_type in ("broad_us_equity", "international_equity", "thematic_sector"):
        out += [
            "The index methodology or the fund's selection rules change.",
            "The expense ratio changes.",
            "Portfolio overlap with another holding increases materially.",
            "A sector concentration limit is breached after a rebalance.",
        ]
    else:
        out += [
            "The issuer is downgraded.",
            "A call or early redemption event occurs.",
            "The payment date this instrument is matched to moves within twelve months.",
        ]
    if role == "LM":
        out.append("The instrument's termination date moves relative to the payment it is matched to.")
    return out
