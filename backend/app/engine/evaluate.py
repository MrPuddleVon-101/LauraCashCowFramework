"""The evaluation pipeline.

Client objectives, portfolio strategy, evaluation framework, security research,
score, committee decision. PRD 2 asks that every security pass through the same
standardised process, and this module is that process.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from ..config import CLIENT, FRAMEWORK_VERSION, POLICY, ROLES, ROLE_BUCKET, ROLE_DESCRIPTIONS, risk_state
from ..providers import market, sec, treasury, yahoo
from . import composite as comp
from . import drift, fit, funds, liability, lookthrough, simulate, stock
from .normalize import data_confidence
from .peers import PeerGroup
from .registry import ASSET_TYPE_LABELS, ROLES_FOR_TYPE, classify, get_fund, registry_meta


def _default_role(asset_type: str) -> str:
    roles = ROLES_FOR_TYPE.get(asset_type) or ["CG"]
    return roles[0]


def _top_metrics(sqs: dict, n: int = 3, best: bool = True) -> list[dict]:
    """Strengths and risks are drawn from what actually moved the score."""
    scored = [
        m for c in sqs.get("categories", [])
        for m in c.get("metrics", [])
        if m["status"] == "OK" and m["effective_weight"] > 0
    ]
    if not scored:
        return []
    # Rank by how much each metric moved the total away from neutral.
    scored.sort(key=lambda m: (m["score"] - 50) * m["effective_weight"], reverse=best)
    out = []
    for m in scored[:n]:
        value = m["value"]
        if isinstance(value, (int, float)):
            shown = f"{value:,.2f}".rstrip("0").rstrip(".") + (f" {m['units']}" if m["units"] else "")
        else:
            # Qualitative measures carry a score and evidence but no figure, so they
            # cannot be phrased as "reads X".
            shown = ""
        out.append({
            "label": m["label"],
            "value": shown,
            "score": m["score"],
            "band": m["band"],
            "weight": m["effective_weight"],
            "detail": m["interpretation"] or m["note"],
            "peer_group": m["peer_group"],
            "percentile": m["percentile"],
        })
    return out


def _explanation(ticker: str, asset_type: str, role: str, sqs: dict, lpfs: dict,
                 trade: dict, funding: dict, gate: dict, sig: dict,
                 strengths: list[dict], risks: list[dict]) -> dict:
    """PRD 63. Plain English, in three parts, with no number that is not on screen."""
    def phrase(m: dict, good: bool) -> str:
        if m["value"]:
            return (f"{m['label']} reads {m['value']}, which scores {m['score']:.0f} out of 100."
                    if good else f"{m['label']} reads {m['value']}, scoring {m['score']:.0f}.")
        return (f"{m['label']} scores {m['score']:.0f} out of 100 on the evidence on file."
                if good else f"{m['label']} scores only {m['score']:.0f} out of 100.")

    why_high = [phrase(s, True) for s in strengths]
    what_wrong = [phrase(r, False) for r in risks]

    ov = trade.get("overlap", {})
    issuer_overlap = ov.get("issuer_overlap_pct", 0.0)
    if issuer_overlap > 35:
        what_wrong.append(
            f"{issuer_overlap:.0f}% of this candidate's named exposure is already in the portfolio, "
            "so it adds less than the ticker suggests."
        )

    bucket = ROLE_BUCKET.get(role, "B")
    if bucket == "A":
        laura = [
            "This sits in the operating liability portfolio, where certainty outranks return.",
            f"Its job is to make a $50,000 payment arrive on a specific date between "
            f"{CLIENT.first_payment_year} and {CLIENT.last_payment_year}.",
        ]
    elif bucket == "C":
        laura = [
            "This is residual capital intended to stay invested after the residency is funded.",
            "It protects Laura's flexibility rather than the residency itself.",
        ]
    else:
        laura = [
            "This belongs to growth capital, not to the money dedicated to the ten fixed payments.",
            "Her mandatory payments are protected by dated instruments elsewhere in the portfolio.",
        ]
    laura.append(
        f"Modelled funding probability is {funding.get('funding_probability', 0):.1%} against the team's "
        f"{POLICY.required_funding_probability:.0%} floor, so this position does not weaken funding certainty."
        if funding.get("funding_probability", 0) >= POLICY.required_funding_probability else
        f"Modelled funding probability is {funding.get('funding_probability', 0):.1%}, below the team's "
        f"{POLICY.required_funding_probability:.0%} floor. Repairing that comes before adding growth risk."
    )

    return {
        "why_the_score_is_what_it_is": why_high,
        "what_could_go_wrong": what_wrong,
        "why_laura_should_care": laura,
    }


#: Asset types whose money behaves like equity in the funding model. A dated
#: Treasury and a cash fund do not, which is the whole reason the ladder works.
_EQUITY_TYPES = {"stock", "broad_us_equity", "international_equity", "thematic_sector"}


def _post_trade_funding(
    *,
    funding: dict,
    asset_type: str,
    role: str,
    position_pct: float,
    equity_weight: float,
    payments_secured: int | None,
    portfolio_value: float,
    target_payment_year: int | None,
) -> dict:
    """Re-run the funding projection with the candidate actually in the book.

    Returns the same shape the gate needs plus what moved, so the interface can
    show the effect instead of asserting it. The projection is seeded, so the
    two runs differ only by their inputs.
    """
    w = max(0.0, min(1.0, position_pct / 100.0))
    candidate_equity = 1.0 if asset_type in _EQUITY_TYPES else 0.0
    # Funded pro rata from the existing book.
    new_equity = equity_weight * (1.0 - w) + candidate_equity * w

    secured_before = funding.get("ladder_payments_secured")
    if secured_before is None:
        secured_before = POLICY.payments_targeted_for_early_matching
    secured_after = int(secured_before)
    basis = ["Funded pro rata from the existing book."]

    if candidate_equity:
        basis.append(f"Equity weight moves from {equity_weight:.0%} to {new_equity:.0%}.")
    else:
        basis.append(f"Non-equity, so equity weight falls to {new_equity:.0%}.")

    # A dated matcher only secures a rung if it is actually big enough to buy
    # that payment at today's curve. Claiming the rung on role alone is how a
    # $5,000 position gets credited with a $50,000 liability.
    if role == "LM" and target_payment_year is not None and portfolio_value > 0:
        years = list(range(CLIENT.first_payment_year, CLIENT.last_payment_year + 1))
        if target_payment_year in years:
            rung = years.index(target_payment_year)
            position_value = portfolio_value * w
            try:
                pv = liability.present_value(target_payment_year, 2027, treasury.get_curve())
                needed = pv["present_value"]
            except Exception:
                needed = CLIENT.annual_operating_payment
            if rung >= secured_after and position_value >= needed:
                secured_after = rung + 1
                basis.append(
                    f"Covers the {target_payment_year} payment outright "
                    f"(${position_value:,.0f} against ${needed:,.0f} needed), securing rung {rung + 1}."
                )
            elif rung >= secured_after:
                basis.append(
                    f"Too small to secure {target_payment_year}: ${position_value:,.0f} "
                    f"against ${needed:,.0f} needed."
                )

    after = simulate.project(equity_weight=new_equity, ladder_payments_secured=secured_after)
    return {
        "funding_probability": after["funding_probability"],
        "equity_weight": round(new_equity, 4),
        "payments_secured": secured_after,
        "basis": basis,
    }


def evaluate(
    ticker: str,
    *,
    role: str | None = None,
    position_pct: float = 5.0,
    portfolio: list[lookthrough.Position] | None = None,
    as_of_year: int = 2027,
    target_payment_year: int | None = None,
    payments_secured: int | None = None,
    equity_weight: float = 0.62,
) -> dict:
    ticker = ticker.strip().upper()

    # Exchange reference data is fetched first: it carries market capitalisation,
    # sector, expense ratio and fund assets, all of which the engine previously
    # either derived badly or read from a transcribed file that had drifted.
    summary = market.get_summary(ticker, "stocks")
    asset_type, fund = classify(ticker, summary)
    role = (role or _default_role(asset_type)).upper()

    market_class = "stocks" if asset_type == "stock" else "etf"
    rp = market.risk_profile(ticker, market_class)
    quote = market.get_quote(ticker, market_class)
    history = market.get_history(ticker, market_class)

    name = ticker
    source_tiers: list[int] = []
    freshest: str | None = None

    # --- security quality ---------------------------------------------------------
    if asset_type == "stock":
        f = sec.get_company_fundamentals(ticker)
        if f is None:
            if quote is None:
                return {
                    "ticker": ticker,
                    "error": "not_found",
                    "message": (
                        f"{ticker} did not resolve against the SEC company list, the fund registry or "
                        "the exchange quote service. Check the symbol."
                    ),
                }
            return {
                "ticker": ticker,
                "error": "no_fundamentals",
                "message": (
                    f"{ticker} trades but has no SEC XBRL company facts, so it cannot be scored. "
                    "Foreign issuers and some trusts file in formats this build does not parse."
                ),
                "quote": quote,
        "reference": summary,
            }
        name = f.name
        peers = PeerGroup(
            ticker, f.ratios.get("revenue"),
            exchange_sector=(summary or {}).get("sector"),
            exchange_industry=(summary or {}).get("industry"),
        )
        sqs = stock.build(f, rp, quote, peers, history, summary)
        freshest = f.period_end
        source_tiers = [1, 1]
        sector = peers.sector
        peer_n = peers.n
        extra = {
            "sic": f.sic, "sic_description": f.sic_description, "cik": f.cik,
            "fiscal_year": f.fiscal_year,
            "revenue_history": f.history("revenue"),
            "fcf_history": f.history("fcf"),
            "ratios": {k: v for k, v in f.ratios.items() if isinstance(v, (int, float)) or v is None},
            "exchange_sector": (summary or {}).get("sector"),
            "exchange_industry": (summary or {}).get("industry"),
            "market_cap": (summary or {}).get("market_cap"),
        }
    else:
        if fund is None:
            return {
                "ticker": ticker,
                "error": "not_in_registry",
                "message": (
                    f"{ticker} is not an SEC filer and is not in the local fund registry, so there is no "
                    "source for its holdings, costs or maturity structure. Add it to data/etf_registry.json "
                    "with the issuer factsheet it was read from."
                ),
                "quote": quote,
        "reference": summary,
            }
        name = fund.get("name", ticker)
        sector = None
        peer_n = 0
        if asset_type == "broad_us_equity":
            sqs = funds.build_broad_etf(ticker, fund, rp, quote)
        elif asset_type == "international_equity":
            sqs = funds.build_international_etf(ticker, fund, rp, quote)
        elif asset_type == "thematic_sector":
            sqs = funds.build_thematic_etf(ticker, fund, rp, quote)
        elif asset_type == "cash_equivalent":
            sqs = funds.build_cash(ticker, fund, rp, quote)
        else:
            sqs = funds.build_bond(ticker, fund, rp, quote, target_payment_year)
        freshest = fund.get("as_of")
        source_tiers = [2, 1]
        extra = {
            "issuer": fund.get("issuer"),
            "category": fund.get("category"),
            "expense_ratio": fund.get("expense_ratio"),
            "methodology": fund.get("methodology"),
            "benchmark": fund.get("benchmark"),
            "maturity_year": fund.get("maturity_year"),
            "termination_date": fund.get("termination_date"),
            "sector_weights": fund.get("sector_weights"),
            "country_weights": fund.get("country_weights"),
            "top_holdings": fund.get("top_holdings"),
            "source_url": fund.get("source_url"),
            "provenance": fund.get("provenance"),
            "registry_as_of": registry_meta().get("as_of"),
            "expense_ratio_source": fund.get("expense_ratio_source", "registry"),
            "expense_ratio_registry": fund.get("expense_ratio_registry"),
            "aum_source": fund.get("aum_source", "registry"),
            "aum_registry": fund.get("aum_registry"),
        }

    # --- portfolio context --------------------------------------------------------
    portfolio = portfolio if portfolio is not None else []
    if portfolio:
        trade = lookthrough.simulate_trade(portfolio, ticker, position_pct)
    else:
        empty = lookthrough.analyse([])
        trade = {
            "before": {k: v for k, v in empty.items() if not k.startswith("_")},
            "after": {k: v for k, v in empty.items() if not k.startswith("_")},
            "delta": {"issuer_hhi": 0.0, "sector_hhi": 0.0, "country_hhi": 0.0},
            "overlap": {"issuer_overlap_pct": 0.0, "sector_overlap_pct": 0.0,
                        "country_overlap_pct": 0.0, "candidate_issuers": [], "shared_issuers": []},
            "candidate_weight_pct": position_pct,
            "largest_lookthrough_issuer": None,
            "_after_issuers": {},
        }

    largest_issuer_pct = None
    top_issuer = None
    candidate_adds_to_top = False
    after_issuers = trade.get("_after_issuers") or {}
    if after_issuers:
        top_issuer = max(after_issuers, key=after_issuers.get)
        largest_issuer_pct = after_issuers[top_issuer]
        candidate_issuers = {
            e["key"] for e in (trade.get("overlap", {}).get("candidate_issuers") or [])
        }
        candidate_adds_to_top = top_issuer in candidate_issuers or top_issuer == ticker

    # --- funding model ------------------------------------------------------------
    #
    # Two runs, not one. The gate asks whether the trade leaves funding below
    # policy, and that question is unanswerable if the candidate is handed the
    # pre-trade figure: it was, so a trade could never fail on its own effect.
    #
    # The trade is modelled as funded pro rata from the existing book, which is
    # the ordinary "rebalance into this" assumption and the only one the engine
    # has the inputs to make honestly. Equity weight moves toward the candidate's
    # own equity share, and a dated matcher large enough to buy its payment
    # outright secures one more rung of the ladder.
    funding = simulate.project(
        equity_weight=equity_weight,
        ladder_payments_secured=payments_secured,
    )
    post = _post_trade_funding(
        funding=funding,
        asset_type=asset_type,
        role=role,
        position_pct=position_pct,
        equity_weight=equity_weight,
        payments_secured=payments_secured,
        portfolio_value=(trade.get("before") or {}).get("total_value") or 0.0,
        target_payment_year=target_payment_year,
    )

    # --- fit ----------------------------------------------------------------------
    lpfs = fit.build(
        role, asset_type, sqs, trade, funding,
        as_of_year=as_of_year,
        target_payment_year=target_payment_year,
        position_pct=position_pct,
        risk_profile=rp,
        fund=fund,
    )

    # --- data confidence ----------------------------------------------------------
    if quote:
        source_tiers.append(1)
    if summary:
        source_tiers.append(1)
    # Cross-source verification, actually performed.
    #
    # This used to be a flat 1.0 whenever a quote and a price history both
    # existed, even though both came from the same provider and were never
    # compared against each other. Two endpoints from one source agreeing with
    # themselves is not corroboration. Yahoo is a genuinely separate read, so the
    # figures that both sources carry are compared and the result is whatever the
    # comparison says. Where Yahoo has nothing, agreement is unknown, and unknown
    # is scored below verified rather than as though it were verified.
    checks: list[dict] = []
    agree_scores: list[float] = []
    try:
        ymkt = yahoo.market_only(ticker)
    except Exception:
        ymkt = {}
    for label, ours, theirs in (
        ("Price", (quote or {}).get("price"), ymkt.get("price")),
        ("Market capitalisation", (summary or {}).get("market_cap"), ymkt.get("market_cap")),
    ):
        a = yahoo.agreement(ours, theirs, tolerance=0.02)
        checks.append({
            "field": label, "ours": ours, "theirs": theirs,
            "agreement": None if a is None else round(a, 3),
            "verdict": "not checked" if a is None else ("agrees" if a >= 0.99 else
                       ("close" if a >= 0.6 else "disagrees")),
            "against": yahoo.SOURCE_NAME,
        })
        if a is not None:
            agree_scores.append(a)

    agreement = sum(agree_scores) / len(agree_scores) if agree_scores else 0.6

    # Computed before confidence, because confidence depends on it.
    registry_drift = drift.check(ticker, fund)
    drift_count = int((registry_drift or {}).get("drifted_count") or 0)

    dcs = data_confidence(
        sqs,
        source_tiers=source_tiers,
        freshest_as_of=freshest,
        cross_source_agreement=agreement,
        peer_group_size=peer_n,
        registry_drift_count=drift_count,
    )
    dcs["cross_checks"] = checks

    # --- gate, composite, signal --------------------------------------------------
    gate = comp.red_gate(
        asset_type=asset_type, role=role, fund=fund, dcs=dcs["score"],
        missing_weight_share=sqs["missing_weight_share"],
        funding_probability=funding["funding_probability"],
        post_trade_funding_probability=post["funding_probability"],
        position_pct=position_pct,
        lookthrough_issuer_pct=largest_issuer_pct,
        target_payment_year=target_payment_year,
        candidate_adds_to_top_issuer=candidate_adds_to_top,
        top_issuer=top_issuer,
    )
    ccs = comp.composite(sqs["score"], lpfs["score"])
    sig = comp.signal(
        sqs=sqs["score"], lpfs=lpfs["score"], ccs=ccs, dcs=dcs["score"],
        gate=gate, missing_weight_share=sqs["missing_weight_share"],
    )
    sizing = comp.position_sizing(
        asset_type=asset_type, role=role, ccs=ccs, dcs=dcs["score"],
        lookthrough_issuer_pct=largest_issuer_pct, signal_key=sig["signal"],
    )

    strengths = _top_metrics(sqs, 3, best=True)
    risks = _top_metrics(sqs, 3, best=False)
    state, state_reason = risk_state(as_of_year, funding["funding_probability"])


    return {
        "ticker": ticker,
        "name": name,
        "asset_type": asset_type,
        "asset_type_label": ASSET_TYPE_LABELS.get(asset_type, asset_type),
        "role": role,
        "role_label": ROLES.get(role, role),
        "role_description": ROLE_DESCRIPTIONS.get(role, ""),
        "bucket": ROLE_BUCKET.get(role, "B"),
        "valid_roles": ROLES_FOR_TYPE.get(asset_type, []),
        "position_pct": position_pct,
        "target_payment_year": target_payment_year,
        "framework_version": FRAMEWORK_VERSION,
        "evaluated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of_year": as_of_year,

        "scores": {
            "security_quality": sqs["score"],
            "laura_fit": lpfs["score"],
            "composite": ccs,
            "data_confidence": dcs["score"],
        },
        "signal": sig,
        "red_gate": gate,
        "risk_state": {"state": state, "reason": state_reason},

        "security_quality": sqs,
        "laura_fit": lpfs,
        "data_confidence": dcs,
        "position_sizing": sizing,

        "quote": quote,
        "reference": summary,
        "risk_profile": rp.to_dict() if rp else None,
        "portfolio_impact": trade,
        "funding": {k: v for k, v in funding.items() if not k.startswith("_")},
        "funding_after_trade": {
            "funding_probability": post["funding_probability"],
            "delta": round(post["funding_probability"] - funding["funding_probability"], 4),
            "equity_weight_before": round(equity_weight, 4),
            "equity_weight_after": post["equity_weight"],
            "payments_secured_before": funding.get("ladder_payments_secured"),
            "payments_secured_after": post["payments_secured"],
            "basis": post["basis"],
        },
        "sponsor_range": simulate.sponsor_range(funding),

        "strengths": strengths,
        "risks": risks,
        "explanation": _explanation(ticker, asset_type, role, sqs, lpfs, trade, funding, gate, sig, strengths, risks),
        "review_triggers": comp.review_triggers(asset_type, role, fund),
        "registry_drift": registry_drift,
        "details": extra,
        "sources": _collect_sources(sqs),
    }


def _collect_sources(sqs: dict) -> list[dict]:
    seen: dict[str, dict] = {}
    for c in sqs.get("categories", []):
        for m in c.get("metrics", []):
            s = m.get("source")
            if not s:
                continue
            key = s["name"]
            entry = seen.setdefault(key, {**s, "supports": []})
            entry["supports"].append(m["label"])
    return list(seen.values())


def decision_log_entry(result: dict, author: str = "", action: str = "EVALUATE",
                       reason: str = "") -> dict:
    """PRD 52. Produces the row the Trading Notes will later be written from."""
    return {
        "date": date.today().isoformat(),
        "author": author or "Cash Cows analyst",
        "security": f"{result['ticker']} {result['name']}",
        "asset_type": result["asset_type_label"],
        "proposed_role": result["role_label"],
        "action": action,
        "position": f"{result['position_pct']:.1f}% of growth sleeve",
        "reason": reason or (result["explanation"]["why_the_score_is_what_it_is"][0]
                             if result["explanation"]["why_the_score_is_what_it_is"] else ""),
        "evidence": [s["name"] for s in result.get("sources", [])],
        "client_link": result["explanation"]["why_laura_should_care"][0]
        if result["explanation"]["why_laura_should_care"] else "",
        "risk": result["risks"][0]["label"] if result["risks"] else "",
        "sqs": result["scores"]["security_quality"],
        "lpfs": result["scores"]["laura_fit"],
        "ccs": result["scores"]["composite"],
        "dcs": result["scores"]["data_confidence"],
        "red_gate": result["red_gate"]["status"],
        "signal": result["signal"]["signal"],
        "portfolio_impact": (
            f"Issuer HHI {result['portfolio_impact']['delta']['issuer_hhi']:+.0f}, "
            f"sector HHI {result['portfolio_impact']['delta']['sector_hhi']:+.0f}"
        ),
        "framework_version": result["framework_version"],
        "review_date": f"{date.today().year + 1}-{date.today().month:02d}-01",
    }
