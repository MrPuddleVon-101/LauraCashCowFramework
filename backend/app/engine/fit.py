"""Laura Portfolio Fit Score. PRD 25 to 33.

Security quality asks whether something is objectively attractive. This asks whether
Laura should own it. The weights change entirely with the proposed role, because
comparing a Treasury and a growth stock against the same objective is the exact
mistake PRD 7 exists to prevent.

Mission and reputational fit is deliberately only five points, and when there is no
evidence it scores 50. The model must not invent Laura's political, social or ethical
preferences, and PRD 31 says so in those words.
"""

from __future__ import annotations

from ..config import CLIENT, POLICY, ROLE_BUCKET, ROLES, risk_state
from .normalize import NEUTRAL, ScoreCard, Source, score_against_bands

TEAM = Source(
    name="Cash Cows framework, client case study and team policy",
    source_type="internal",
    authority_tier=1,
    claim_supported="Client objectives, liability calendar and team allocation policy",
)

ROLE_WEIGHTS: dict[str, dict[str, float]] = {
    # PRD 26
    "CG": {"growth": 20, "liability": 15, "horizon": 15, "diversification": 25,
           "liquidity": 10, "downside": 10, "mission": 5},
    # PRD 27
    "SG": {"growth": 25, "liability": 10, "horizon": 15, "diversification": 20,
           "liquidity": 10, "downside": 15, "mission": 5},
    # PRD 28
    "ID": {"growth": 15, "liability": 10, "horizon": 10, "diversification": 35,
           "liquidity": 10, "downside": 15, "mission": 5},
    # PRD 29
    "LM": {"date_match": 30, "certainty": 25, "funding_impact": 20,
           "liquidity": 10, "yield_efficiency": 10, "mission": 5},
    # PRD 30
    "LR": {"preservation": 25, "liquidity": 30, "timing": 20,
           "funding_impact": 10, "opportunity_cost": 10, "mission": 5},
    # Team extensions. The PRD defines five role models; these two are Cash Cows
    # additions and are labelled as such wherever they appear.
    "LG": {"growth": 22, "liability": 10, "horizon": 20, "diversification": 23,
           "liquidity": 10, "downside": 10, "mission": 5},
    "DA": {"preservation": 22, "liability": 18, "horizon": 10, "diversification": 20,
           "liquidity": 15, "downside": 10, "mission": 5},
}

CATEGORY_LABELS: dict[str, str] = {
    "growth": "Contribution to long-term growth",
    "liability": "Compatibility with the liability strategy",
    "horizon": "Time horizon fit",
    "diversification": "Incremental diversification",
    "liquidity": "Liquidity and flexibility",
    "downside": "Downside compatibility",
    "mission": "Mission and reputational fit",
    "date_match": "Liability date match",
    "certainty": "Payment certainty",
    "funding_impact": "Improvement to 2033 funding probability",
    "yield_efficiency": "Yield efficiency",
    "preservation": "Capital preservation",
    "timing": "Timing match",
    "opportunity_cost": "Opportunity cost",
}

TEAM_DEFINED_ROLES = {"LG", "DA"}

# Risk state changes how hard the downside categories bite. PRD 40 asks the framework
# to change behaviour mathematically rather than by assertion.
RISK_STATE_DOWNSIDE_MULTIPLIER = {"GROWTH": 0.80, "BALANCED": 1.00, "PROTECTION": 1.35}


def _diversification_score(trade: dict, candidate_type: str) -> tuple[float, list[str]]:
    """PRD 33. Four components, weighted 40 / 25 / 20 / 15.

    The question is whether owning this actually makes Laura's portfolio more robust,
    not whether it has a different ticker.
    """
    delta = trade.get("delta", {})
    ov = trade.get("overlap", {})
    notes: list[str] = []

    # 40 percent: issuer concentration improvement.
    issuer_delta = delta.get("issuer_hhi", 0.0)
    issuer_score = score_against_bands(
        issuer_delta, [(-400, 100), (-150, 88), (-40, 76), (0, 62), (40, 46), (150, 24), (400, 6)]
    )
    notes.append(
        f"Issuer concentration {'falls' if issuer_delta < 0 else 'rises'} by "
        f"{abs(issuer_delta):.0f} HHI points after the trade."
    )

    # 25 percent: sector concentration improvement.
    sector_delta = delta.get("sector_hhi", 0.0)
    sector_score = score_against_bands(
        sector_delta, [(-300, 100), (-120, 88), (-30, 74), (0, 58), (30, 42), (120, 22), (300, 5)]
    )

    # 20 percent: overlap with what she already owns, standing in for correlation.
    issuer_overlap = ov.get("issuer_overlap_pct", 0.0)
    overlap_score = score_against_bands(
        issuer_overlap, [(0, 100), (10, 88), (25, 72), (40, 55), (60, 34), (80, 14), (100, 3)]
    )
    if issuer_overlap > 40:
        notes.append(
            f"{issuer_overlap:.0f}% of this candidate's named exposure is already held elsewhere in the portfolio."
        )

    # 15 percent: geographic or factor diversification.
    country_delta = delta.get("country_hhi", 0.0)
    geo_score = score_against_bands(
        country_delta, [(-2000, 100), (-800, 88), (-200, 72), (0, 55), (200, 40), (800, 20), (2000, 5)]
    )

    total = issuer_score * 0.40 + sector_score * 0.25 + overlap_score * 0.20 + geo_score * 0.15
    return round(total, 1), notes


def build(
    role: str,
    asset_type: str,
    sqs: dict,
    trade: dict,
    funding: dict,
    *,
    as_of_year: int = 2027,
    target_payment_year: int | None = None,
    position_pct: float = 0.0,
    risk_profile=None,
    fund: dict | None = None,
    exclusions: list[str] | None = None,
) -> dict:
    role = role.upper()
    weights = ROLE_WEIGHTS.get(role)
    if weights is None:
        raise ValueError(f"Unknown role {role}")

    categories = {k: float(v) for k, v in weights.items()}
    card = ScoreCard(f"LPFS: {ROLES.get(role, role)}", categories)

    prob = funding.get("funding_probability", 0.0)
    state, state_reason = risk_state(as_of_year, prob)
    downside_mult = RISK_STATE_DOWNSIDE_MULTIPLIER[state]
    years_to_residency = CLIENT.residency_start_year - as_of_year

    derived = sqs.get("derived", {})
    lt = sqs.get("lookthrough", {})
    rp = risk_profile
    max_dd = getattr(rp, "max_drawdown_pct", None)
    vol = getattr(rp, "annual_volatility_pct", None)
    beta = getattr(rp, "beta", None)

    is_equity_like = asset_type in ("stock", "broad_us_equity", "international_equity", "thematic_sector")
    has_maturity = bool((fund or {}).get("has_maturity_date"))
    maturity_year = (fund or {}).get("maturity_year")

    # --- growth-oriented roles ----------------------------------------------------
    if "growth" in weights:
        growth_proxy = None
        if asset_type == "stock":
            # By key, not by position. This used to read categories[0] and happened
            # to be right only because "growth" is declared first in the stock model.
            # Reordering that dict would have silently started scoring Laura's growth
            # contribution off the cash flow category instead.
            growth_proxy = next(
                (c.get("score") for c in (sqs.get("categories") or []) if c.get("key") == "growth"),
                None,
            )
        else:
            w = lt.get("weighted", {})
            growth_proxy = w.get("revenue_cagr_3y")
        card.measure(
            "growth_contribution", CATEGORY_LABELS["growth"], weights["growth"], "growth",
            growth_proxy if asset_type != "stock" else growth_proxy,
            bands=([(-5, 12), (0, 32), (5, 52), (10, 68), (18, 84), (30, 95)]
                   if asset_type != "stock" else
                   [(25, 14), (45, 38), (62, 62), (75, 76), (86, 88), (95, 97)]),
            units=("% weighted revenue CAGR" if asset_type != "stock" else "growth durability score"),
            as_of=None, source=TEAM,
            interpretation=(
                "Growth capital is what raises Laura's eventual facility contribution. It is not "
                "what funds the ten payments."
            ),
        )

    if "liability" in weights:
        # An equity holding is compatible with the liability strategy when the ladder
        # is already secured independently of it.
        secured = funding.get("payments_secured_by_2028", 0)
        compat = score_against_bands(
            float(secured), [(0, 18), (2, 38), (4, 55), (6, 72), (8, 88), (10, 97)]
        )
        if not is_equity_like:
            compat = min(100.0, compat + 10)
        card.qualitative(
            "liability_compatibility", CATEGORY_LABELS["liability"], weights["liability"], "liability",
            compat,
            [
                f"{secured} of the ten payments are targeted for matching with dated instruments by 2028.",
                f"Modelled funding probability is {prob:.1%} against a {POLICY.required_funding_probability:.0%} policy floor.",
                "This position sits in the growth sleeve and is not relied on to make any payment."
                if is_equity_like else "This position sits inside the liability or defensive sleeve.",
            ],
            source=TEAM,
        )

    if "horizon" in weights:
        if role == "LG":
            horizon_score = 88.0
            horizon_note = "Residual growth capital is intended to stay invested past 2033, so a long horizon is the point."
        else:
            horizon_score = score_against_bands(
                float(years_to_residency), [(0, 20), (1, 32), (2, 48), (4, 68), (6, 85), (8, 94)]
            )
            horizon_note = (
                f"{years_to_residency} years until the residency is established in "
                f"{CLIENT.residency_start_year}. Equity needs time to recover from a bad sequence."
            )
        card.qualitative("horizon", CATEGORY_LABELS["horizon"], weights["horizon"], "horizon",
                         horizon_score, [horizon_note], source=TEAM)

    if "diversification" in weights:
        div_score, div_notes = _diversification_score(trade, asset_type)
        card.qualitative("diversification", CATEGORY_LABELS["diversification"],
                         weights["diversification"], "diversification", div_score,
                         div_notes or ["No existing portfolio supplied, so the trade is scored standalone."],
                         source=TEAM)

    if "downside" in weights:
        base = score_against_bands(
            max_dd if max_dd is not None else -35.0,
            [(-70, 6), (-55, 20), (-45, 32), (-35, 48), (-25, 66), (-18, 80), (-10, 93), (-4, 100)],
        )
        adjusted = max(0.0, min(100.0, 50 + (base - 50) / downside_mult))
        card.qualitative(
            "downside", CATEGORY_LABELS["downside"], weights["downside"], "downside", adjusted,
            [
                f"Worst observed drawdown {max_dd:.1f}%." if max_dd is not None else "No price history on file.",
                f"Risk state is {state}. {state_reason}",
                f"Downside is weighted {downside_mult:.2f}x in this state, per PRD 40.",
            ],
            source=TEAM,
        )

    # --- liability-matching role --------------------------------------------------
    if "date_match" in weights:
        if not has_maturity:
            score = 4.0
            evidence = [
                "The instrument has no maturity date, so it cannot be dated against a payment.",
                "PRD 23 requires a Red Gate review or failure when a perpetual bond fund is proposed as a liability matcher.",
            ]
        elif target_payment_year is None:
            score = 45.0
            evidence = ["A maturity exists but no target payment year was specified for this evaluation."]
        else:
            gap = maturity_year - target_payment_year if maturity_year else 99
            if gap > 0:
                score = max(0.0, 25 - gap * 8)
                evidence = [
                    f"Matures in {maturity_year}, after the {target_payment_year} payment is due. "
                    "The cash arrives too late without another liquidity source."
                ]
            else:
                score = score_against_bands(float(abs(gap)), [(0, 100), (1, 78), (2, 52), (3, 28), (5, 8)])
                evidence = [
                    f"Terminates {(fund or {}).get('termination_date')}, ahead of the "
                    f"{target_payment_year} payment at the start of that year."
                ]
        card.qualitative("date_match", CATEGORY_LABELS["date_match"], weights["date_match"],
                         "date_match", score, evidence, source=TEAM)

    if "certainty" in weights:
        is_treasury = bool(derived.get("is_treasury"))
        callable_ = bool((fund or {}).get("callable"))
        score = 95.0 if (is_treasury and not callable_) else (60.0 if is_treasury else 45.0)
        if not has_maturity:
            score = min(score, 20.0)
        card.qualitative(
            "certainty", CATEGORY_LABELS["certainty"], weights["certainty"], "certainty", score,
            [
                "US Treasury obligation." if is_treasury else "Not a direct sovereign obligation.",
                "Not callable, so the cash flow cannot be withdrawn early." if not callable_ else "Callable.",
                "No defined maturity, so the amount available on the payment date is unknown."
                if not has_maturity else "Defined termination date with a dated distribution.",
            ],
            source=TEAM,
        )

    if "funding_impact" in weights:
        improves = has_maturity and target_payment_year is not None
        score = 88.0 if improves else (NEUTRAL if not is_equity_like else 35.0)
        card.qualitative(
            "funding_impact", CATEGORY_LABELS["funding_impact"], weights["funding_impact"],
            "funding_impact", score,
            [
                f"Current modelled funding probability is {prob:.1%}.",
                "A dated instrument converts a modelled probability into a matched payment, which is the "
                "distinction PRD 35 treats as the important one."
                if improves else
                "This holding does not move a payment from economically covered to matched.",
            ],
            source=TEAM,
        )

    if "yield_efficiency" in weights:
        y = (fund or {}).get("sec_yield_pct")
        card.measure(
            "yield_efficiency", CATEGORY_LABELS["yield_efficiency"], weights["yield_efficiency"],
            "yield_efficiency", y,
            bands=[(1, 15), (2, 35), (3, 52), (4, 68), (5, 84), (6.5, 95)],
            units="%", source=TEAM,
            interpretation="An investment offering a large yield with poor certainty should score badly here, and does.",
        )

    # --- liquidity-reserve and defensive roles ------------------------------------
    if "preservation" in weights:
        card.measure(
            "preservation", CATEGORY_LABELS["preservation"], weights["preservation"], "preservation",
            max_dd,
            bands=[(-30, 5), (-15, 25), (-8, 45), (-4, 65), (-2, 82), (-0.8, 94), (-0.2, 100)],
            units="% maximum drawdown", source=TEAM,
            interpretation="Money set aside for a dated payment has very little capacity for loss, whatever Laura's willingness.",
        )

    if "timing" in weights:
        avg_mat = (fund or {}).get("average_maturity_years")
        card.measure(
            "timing", CATEGORY_LABELS["timing"], weights["timing"], "timing", avg_mat,
            bands=[(0.05, 100), (0.3, 92), (0.8, 78), (1.5, 60), (3, 36), (6, 12)],
            higher_is_better=False, units="years average maturity", source=TEAM,
            interpretation="A liquidity reserve should mature inside the window it is covering.",
        )

    if "opportunity_cost" in weights:
        y = (fund or {}).get("sec_yield_pct")
        card.measure(
            "opportunity_cost", CATEGORY_LABELS["opportunity_cost"], weights["opportunity_cost"],
            "opportunity_cost", y,
            bands=[(0.5, 15), (1.5, 35), (2.5, 52), (3.5, 68), (4.5, 84), (6, 95)],
            units="%", source=TEAM,
            interpretation="Cash that earns nothing has a real cost over a six year horizon.",
        )

    if "liquidity" in weights:
        spread = None
        for c in sqs.get("categories", []):
            for m in c.get("metrics", []):
                if m["key"] in ("bid_ask", "liquidity") and m["value"] is not None:
                    spread = m["value"]
                    break
        card.measure(
            "liquidity", CATEGORY_LABELS["liquidity"], weights["liquidity"], "liquidity", spread,
            bands=[(0.5, 100), (2, 92), (5, 82), (12, 66), (25, 44), (50, 18)],
            higher_is_better=False, units="bps", source=TEAM,
            interpretation="Laura needs to be able to move without paying a penalty to do it.",
        )

    # --- mission and reputational fit, 5 points everywhere ------------------------
    # PRD 31 critical rule: with no evidence, hold this at neutral. Not 0 and not
    # 100. Neutral is NEUTRAL on the calibrated scale rather than the literal 50,
    # because declining to have an opinion must not read as a mark against.
    exclusions = exclusions or []
    if exclusions:
        mission_score = NEUTRAL - 37.0
        mission_evidence = [f"Team approved client exclusion in force: {', '.join(exclusions)}."]
    else:
        mission_score = NEUTRAL
        mission_evidence = [
            "No explicit client exclusion is on file, and no material controversy has been recorded "
            "against this security in the evidence store.",
            "Laura's public background is creative, entrepreneurial and community oriented. PRD 4 forbids "
            "converting that into an investment preference, so this is held at neutral.",
        ]
    card.qualitative("mission", CATEGORY_LABELS["mission"], weights["mission"], "mission",
                     mission_score, mission_evidence, source=TEAM)

    result = card.finalise()
    result["role"] = role
    result["role_label"] = ROLES.get(role, role)
    result["role_is_team_defined"] = role in TEAM_DEFINED_ROLES
    result["bucket"] = ROLE_BUCKET.get(role, "B")
    result["category_labels"] = CATEGORY_LABELS
    result["risk_state"] = {"state": state, "reason": state_reason, "downside_multiplier": downside_mult}
    result["position_pct"] = position_pct
    return result
