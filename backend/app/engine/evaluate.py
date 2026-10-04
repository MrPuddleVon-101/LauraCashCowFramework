"""The evaluation pipeline.

Client objectives, portfolio strategy, evaluation framework, security research,
score, committee decision. PRD 2 asks that every security pass through the same
standardised process, and this module is that process.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from ..config import CLIENT, FRAMEWORK_VERSION, POLICY, ROLES, ROLE_BUCKET, ROLE_DESCRIPTIONS, risk_state
from ..providers import market, sec
from . import composite as comp
from . import fit, funds, liability, lookthrough, simulate, stock
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
    funding = simulate.project(
        equity_weight=equity_weight,
        ladder_payments_secured=payments_secured,
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
    dcs = data_confidence(
        sqs,
        source_tiers=source_tiers,
        freshest_as_of=freshest,
        cross_source_agreement=1.0 if (quote and rp) else 0.75,
        peer_group_size=peer_n,
    )

    # --- gate, composite, signal --------------------------------------------------
    gate = comp.red_gate(
        asset_type=asset_type, role=role, fund=fund, dcs=dcs["score"],
        missing_weight_share=sqs["missing_weight_share"],
        funding_probability=funding["funding_probability"],
        post_trade_funding_probability=funding["funding_probability"],
        position_pct=position_pct,
        lookthrough_issuer_pct=largest_issuer_pct,
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
        "sponsor_range": simulate.sponsor_range(funding),

        "strengths": strengths,
        "risks": risks,
        "explanation": _explanation(ticker, asset_type, role, sqs, lpfs, trade, funding, gate, sig, strengths, risks),
        "review_triggers": comp.review_triggers(asset_type, role, fund),
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
