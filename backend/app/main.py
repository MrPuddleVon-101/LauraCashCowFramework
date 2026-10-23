"""Stonky x Cash Cows API. PRD 65.

A modular monolith, which is what PRD 57 asks for. No microservices.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import os
from datetime import date, datetime, timezone

from . import store
from .config import BUCKETS, CLIENT, FRAMEWORK_VERSION, POLICY, ROLES, ROLE_DESCRIPTIONS, framework_manifest
from .engine import evaluate as ev
from .engine import fixedincome
from .providers import router
from .engine import liability, lookthrough, simulate
from .engine.peers import _peers
from .engine.registry import ASSET_TYPE_LABELS, list_funds, registry_meta
from .providers import sec, treasury

DATA = Path(__file__).resolve().parents[1] / "data"

app = FastAPI(
    title="Stonky x Cash Cows",
    description="Laura Cash Cow Framework decision engine",
    version=FRAMEWORK_VERSION,
)
#: The Pages origin is fixed and is named exactly rather than by wildcard, so a
#: deployed backend is reachable from the published interface and from nowhere
#: unexpected. Extra origins can be added for a preview deployment through
#: ALLOWED_ORIGINS, comma separated.
ALLOWED_ORIGINS = [
    "https://mrpuddlevon-101.github.io",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
] + [o.strip() for o in os.environ.get("ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _portfolios() -> dict:
    return json.loads((DATA / "portfolios.json").read_text())


def _positions(name: str = "competition") -> list[lookthrough.Position]:
    """Positions for a named portfolio.

    An unknown name used to return an empty list, which the engine then scored as
    though Laura owned nothing. A typo should be a 404, not a silent reset of her
    whole portfolio.
    """
    portfolios = _portfolios()
    if name not in portfolios:
        known = ", ".join(sorted(k for k in portfolios if not k.startswith("_")))
        raise HTTPException(status_code=404, detail=f"Unknown portfolio '{name}'. Known: {known}.")
    data = portfolios.get(name, {})
    out = [
        lookthrough.Position(
            ticker=p["ticker"], value=float(p["value"]), role=p.get("role", ""),
            label=p.get("note", ""),
        )
        for p in data.get("positions", [])
    ]
    cash = float(data.get("cash") or 0)
    if cash:
        out.append(lookthrough.Position("SGOV", cash, "LR", label="Uninvested cash, modelled as T-bills"))
    return out


@app.on_event("startup")
def _startup() -> None:
    store.record_framework_version(framework_manifest())


# --- framework and client ---------------------------------------------------------

@app.get("/api/framework")
def get_framework() -> dict:
    manifest = framework_manifest()
    manifest["role_descriptions"] = ROLE_DESCRIPTIONS
    manifest["asset_types"] = ASSET_TYPE_LABELS
    manifest["versions"] = store.list_framework_versions()
    manifest["stale_snapshots"] = store.stale_snapshots(FRAMEWORK_VERSION)
    manifest["registry"] = registry_meta()
    peers = _peers()
    manifest["peer_data"] = {
        "generated_at": peers.get("generated_at"),
        "source": peers.get("source"),
        "source_url": peers.get("source_url"),
        "groups": len(peers.get("groups", {})),
        "periods": peers.get("periods"),
    }
    return manifest


@app.get("/api/client")
def get_client() -> dict:
    """Everything the interface needs to tell Laura's story, split by what it is."""
    return {
        "facts": {
            "name": CLIENT.client_name,
            "contribution_2027": CLIENT.contribution_2027,
            "contribution_2028": CLIENT.contribution_2028,
            "residency_start_year": CLIENT.residency_start_year,
            "annual_operating_payment": CLIENT.annual_operating_payment,
            "first_payment_year": CLIENT.first_payment_year,
            "last_payment_year": CLIENT.last_payment_year,
            "operating_payments_count": CLIENT.operating_payments_count,
            "total_nominal_liability": CLIENT.total_nominal_liability,
            "sponsor_conversation_year": CLIENT.sponsor_conversation_year,
            "risk_willingness": CLIENT.risk_willingness,
            "risk_capacity": CLIENT.risk_capacity,
            "source": "Wharton Global High School Investment Competition case study, Laura Gao.",
        },
        "policy": {
            "required_funding_probability": POLICY.required_funding_probability,
            "payments_targeted_for_early_matching": POLICY.payments_targeted_for_early_matching,
            "provisional_facility_planning_amount": POLICY.provisional_facility_planning_amount,
            "provisional_facility_cap": POLICY.provisional_facility_cap,
            "retained_growth_target": POLICY.retained_growth_target,
            "illustrative_yield_assumption": POLICY.illustrative_yield_assumption,
            "source": "Cash Cows team strategy. Editable, and a change creates a new framework version.",
        },
        "buckets": BUCKETS,
        "roles": {k: {"label": v, "description": ROLE_DESCRIPTIONS.get(k, "")} for k, v in ROLES.items()},
    }


# --- securities -------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    """A request the engine can actually answer.

    These bounds exist so a mistyped field comes back as a 422 naming the field
    rather than a 500 from somewhere deep in the engine. An unknown role used to
    raise inside the fit model; a payment year of 9999 and a secured count of
    -999 were accepted and quietly produced nonsense.
    """

    model_config = {"extra": "forbid"}

    # 12 characters excluded every fixed-income identifier the competition uses,
    # starting with B-T-4.375-15112039. An exchange-qualified ticker (7203:TSE)
    # and an ISIN do not fit either. The pattern still refuses anything that is
    # not a plausible identifier.
    ticker: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9.:\-]+$")
    role: Literal["CG", "SG", "ID", "LM", "LR", "LG", "DA"] | None = None
    position_pct: float = Field(default=5.0, ge=0, le=100)
    portfolio: str = Field(default="competition", max_length=64)
    target_payment_year: int | None = Field(
        default=None, ge=CLIENT.first_payment_year, le=CLIENT.last_payment_year
    )
    payments_secured: int | None = Field(
        default=None, ge=0, le=CLIENT.operating_payments_count
    )
    equity_weight: float = Field(default=0.62, ge=0, le=1)
    as_of_year: int = Field(default=2027, ge=2026, le=CLIENT.last_payment_year)


@app.post("/api/security/evaluate")
def post_evaluate(req: EvaluateRequest) -> dict:
    result = ev.evaluate(
        req.ticker,
        role=req.role,
        position_pct=req.position_pct,
        portfolio=_positions(req.portfolio),
        as_of_year=req.as_of_year,
        target_payment_year=req.target_payment_year,
        payments_secured=req.payments_secured,
        equity_weight=req.equity_weight,
    )
    if result.get("error"):
        return result
    result["snapshot_id"] = store.record_snapshot(result)
    result["decision_log_draft"] = ev.decision_log_entry(result)
    return result


@app.get("/api/security/{ticker}")
def get_security(ticker: str, role: str | None = None, position_pct: float = 5.0,
                 portfolio: str = "competition", target_payment_year: int | None = None) -> dict:
    return post_evaluate(EvaluateRequest(
        ticker=ticker, role=role, position_pct=position_pct,
        portfolio=portfolio, target_payment_year=target_payment_year,
    ))


@app.get("/api/security/{ticker}/history")
def get_security_history(ticker: str) -> dict:
    return {"ticker": ticker.upper(), "snapshots": store.snapshot_history(ticker)}


@app.get("/api/search")
def search(q: str = Query(..., min_length=1), limit: int = 12) -> dict:
    """Symbol lookup across the fund registry and the full SEC company list."""
    q = q.strip().upper()
    results: list[dict] = []

    for fund in list_funds():
        if q in fund["ticker"] or q in (fund["name"] or "").upper():
            results.append({
                "ticker": fund["ticker"], "name": fund["name"],
                "type": fund["asset_type_label"], "source": "registry",
            })

    table = sec._read_cache("sec_tickers.json", sec.TICKER_TTL)
    if table is None:
        sec.ticker_to_cik("AAPL")
        table = sec._read_cache("sec_tickers.json", sec.TICKER_TTL) or {}

    exact = [t for t in table if t == q]
    prefix = sorted(t for t in table if t.startswith(q) and t != q)
    for t in (exact + prefix)[: limit * 2]:
        if any(r["ticker"] == t for r in results):
            continue
        results.append({"ticker": t, "name": None, "type": "Individual stock", "source": "sec"})

    return {"query": q, "results": results[:limit]}


@app.get("/api/universe")
def get_universe() -> dict:
    return {"funds": list_funds(), "registry": registry_meta()}


# --- portfolio --------------------------------------------------------------------

@app.get("/api/portfolio/{name}")
def get_portfolio(name: str = "competition") -> dict:
    data = _portfolios().get(name)
    if not data:
        raise HTTPException(404, f"No portfolio named {name}")
    positions = _positions(name)
    analysis = lookthrough.analyse(positions)
    return {
        "name": name,
        "meta": {k: v for k, v in data.items() if k != "positions"},
        "analysis": {k: v for k, v in analysis.items() if not k.startswith("_")},
        "positions": data.get("positions", []),
    }


@app.get("/api/portfolio/{name}/exposure")
def get_exposure(name: str = "competition") -> dict:
    analysis = lookthrough.analyse(_positions(name))
    return {k: v for k, v in analysis.items() if not k.startswith("_")}


class TradeRequest(BaseModel):
    ticker: str
    weight_pct: float = Field(ge=0, le=99)
    portfolio: str = "competition"


@app.post("/api/portfolio/simulate-trade")
def post_simulate_trade(req: TradeRequest) -> dict:
    trade = lookthrough.simulate_trade(_positions(req.portfolio), req.ticker, req.weight_pct)
    return {k: v for k, v in trade.items() if not k.startswith("_")}


# --- liabilities and scenarios ----------------------------------------------------

@app.get("/api/liabilities")
def get_liabilities(as_of_year: int = 2027, portfolio: str = "competition") -> dict:
    """Laura's ladder, with registry instruments mapped to the years they can carry."""
    data = _portfolios().get(portfolio, {})
    matched = []
    for p in data.get("positions", []):
        year = p.get("target_payment_year")
        if year and p.get("role") == "LM":
            matched.append(liability.MatchedAsset(
                ticker=p["ticker"], payment_year=int(year),
                expected_cash_flow=float(p["value"]),
                note="dedicated holding in the competition portfolio",
            ))
    calendar = liability.build_calendar(as_of_year, matched)
    calendar["coverage"] = liability.ladder_coverage_report()
    calendar["candidates_by_year"] = {
        str(y): liability.ladder_candidates(y)[:3] for y in CLIENT.liability_years
    }
    return calendar


@app.get("/api/funding-probability")
def get_funding(equity_weight: float = 0.62, payments_secured: int | None = None,
                paths: int = 10000) -> dict:
    sim = simulate.project(
        equity_weight=equity_weight,
        ladder_payments_secured=payments_secured,
        n_paths=max(1000, min(50000, paths)),
    )
    out = {k: v for k, v in sim.items() if not k.startswith("_")}
    out["sponsor_range"] = simulate.sponsor_range(sim)
    # A coarse histogram so the interface can draw the distribution rather than a number.
    import numpy as np
    dist = sim["_distribution"]
    counts, edges = np.histogram(dist, bins=36)
    out["distribution"] = {
        "counts": [int(c) for c in counts],
        "edges": [float(e) for e in edges],
    }
    return out


@app.get("/api/stress-test")
def get_stress(portfolio_value: float = 600000, equity_weight: float = 0.62,
               as_of_year: int = 2033, payments_secured: int | None = None) -> dict:
    return simulate.stress_test(portfolio_value, equity_weight, as_of_year, payments_secured)


@app.get("/api/yield-curve")
def get_curve() -> dict:
    return treasury.get_curve()


# --- decision log -----------------------------------------------------------------

class DecisionRequest(BaseModel):
    entry: dict
    snapshot_id: int | None = None
    portfolio: str = "competition"
    override: bool = False
    override_reason: str = ""


@app.post("/api/decision-log")
def post_decision(req: DecisionRequest) -> dict:
    if req.override and not req.override_reason.strip():
        raise HTTPException(400, "An override requires a written reason. PRD 64 does not allow a silent override.")
    decision_id = store.record_decision(
        req.entry, req.snapshot_id, req.portfolio, req.override, req.override_reason
    )
    return {"id": decision_id, "recorded": True}


@app.get("/api/decision-log")
def get_decisions(limit: int = 100, portfolio: str | None = None) -> dict:
    return {"decisions": store.list_decisions(limit, portfolio)}


@app.get("/api/health")
def health() -> dict:
    """What this engine can actually do right now.

    The interface reads this to decide what to enable. A capability that is not
    listed here is one the interface must not offer, which is the difference
    between a degraded service and a dishonest one.
    """
    curve = treasury.get_curve()
    peers = _peers()
    routed = router.status()
    sec_ready = sec._read_cache("sec_tickers.json", sec.TICKER_TTL) is not None
    return {
        "status": "ok",
        "mode": "LIVE",
        "framework_version": FRAMEWORK_VERSION,
        "server_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "providers": {
            "sec_edgar": sec_ready,
            "sec_user_agent_set": bool(os.environ.get("SEC_USER_AGENT")),
            "treasury_curve_as_of": curve.get("as_of"),
            "treasury_degraded": curve.get("degraded", False),
            "peer_groups": len(peers.get("groups", {})),
            "peer_data_generated": peers.get("generated_at"),
            "registry_as_of": registry_meta().get("as_of"),
        },
        "routed_providers": routed["providers"],
        "capabilities": {
            **routed["capabilities"],
            "us_fundamentals": sec_ready,
            "treasury_curve": not curve.get("degraded", False),
            "fixed_income_maths": True,
        },
        "coverage": {
            "global_search": routed["global_search"],
            "global_quotes": routed["global_quotes"],
            "identifier_resolution": routed["identifier_resolution"],
        },
        "degraded": routed["degraded"],
        "cache": {
            "directory_present": sec.CACHE_DIR.exists() if hasattr(sec, "CACHE_DIR") else None,
            "treasury_as_of": curve.get("as_of"),
        },
    }


@app.get("/api/resolve")
def resolve_identifier(q: str = Query(..., min_length=1), exchange: str = "") -> dict:
    """Turn an identifier into one instrument, or report that it is ambiguous."""
    bond = fixedincome.parse_wins_identifier(q)
    if bond is not None:
        return {
            "resolved": {
                "display_symbol": bond.identifier,
                "qualified_symbol": bond.identifier,
                "name": f"{bond.issuer} {bond.coupon_rate}% {bond.maturity.isoformat()}",
                "asset_class": bond.security_type,
                "currency": bond.currency,
                "country": "US" if bond.security_type == "treasury" else "",
                "provider": "instrument terms",
            },
            "ambiguous": False,
            "candidates": [],
            "note": "Parsed from the identifier itself. No provider is involved.",
        }
    return router.resolve(q, exchange=exchange)


class BondRequest(BaseModel):
    """An individual bond, described by its terms rather than by a ticker."""

    model_config = {"extra": "forbid"}

    identifier: str = Field(min_length=1, max_length=64)
    face_value: float = Field(default=100_000.0, gt=0)
    price_pct_of_par: float = Field(default=100.0, gt=0, le=1000)
    settlement: date | None = None
    coupon_rate: float | None = Field(default=None, ge=0, le=100)
    maturity: date | None = None
    frequency: int = Field(default=2, ge=1, le=12)
    currency: str = Field(default="USD", max_length=8)
    issuer: str = Field(default="", max_length=120)
    cusip: str | None = Field(default=None, max_length=12)
    isin: str | None = Field(default=None, max_length=12)
    callable: bool = False
    credit_quality: str = Field(default="US_TREASURY", max_length=32)


@app.post("/api/fixed-income/describe")
def describe_bond(req: BondRequest) -> dict:
    """Schedule, cost, yield, duration and which payments the cash can reach."""
    terms = fixedincome.parse_wins_identifier(req.identifier)
    if terms is None:
        if req.coupon_rate is None or req.maturity is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"{req.identifier} is not a WInS bond identifier, so its coupon "
                    "and maturity have to be given explicitly."
                ),
            )
        terms = fixedincome.BondTerms(
            identifier=req.identifier.upper(),
            issuer=req.issuer or "Unknown issuer",
            coupon_rate=req.coupon_rate,
            maturity=req.maturity,
            security_type="corporate_bond",
            credit_quality=req.credit_quality,
        )
    terms.face_value = req.face_value
    terms.price_pct_of_par = req.price_pct_of_par
    terms.settlement = req.settlement or date.today()
    terms.frequency = req.frequency
    terms.currency = req.currency
    terms.callable = req.callable
    terms.cusip = req.cusip
    terms.isin = req.isin
    if req.issuer:
        terms.issuer = req.issuer
    years = list(range(CLIENT.first_payment_year, CLIENT.last_payment_year + 1))
    return fixedincome.describe(terms, payment_years=years,
                                payment_amount=CLIENT.annual_operating_payment)


# --- serving the built interface ------------------------------------------------
#
# In development Vite serves the frontend on 5173 and proxies /api here, so this
# does nothing. In a deployment there is one process: the API also hands out the
# built single page app, which means one service, one URL and no CORS to arrange.
# Mounted last so every /api route is matched first.
_DIST = (Path(__file__).resolve().parents[2] / "frontend" / "dist").resolve()

if _DIST.is_dir():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")
    if (_DIST / "brand").is_dir():
        app.mount("/brand", StaticFiles(directory=_DIST / "brand"), name="brand")

    def _inside_dist(requested: str) -> Path | None:
        """Resolve a request path to a real file inside the published build.

        Returns None for anything that escapes it. Joining the request onto the
        directory and trusting the result is not enough: Starlette hands this
        route the percent-decoded path, so "%2e%2e%2f" arrives as "../" after
        the server's own normalisation has already run and walks straight out of
        the build. Resolving first and then proving containment is what closes
        it, and resolve() also follows any symlink before the check so a link
        pointing outside cannot be used either.
        """
        if not requested:
            return None
        candidate = (_DIST / requested).resolve()
        if candidate != _DIST and _DIST not in candidate.parents:
            return None
        return candidate if candidate.is_file() else None

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str) -> Any:
        """Any path that is not an API route is the single page app.

        An unknown API route stays a 404 from the API rather than quietly
        becoming a 200 with an HTML body, because a client that asked for JSON
        should be told it was wrong, not handed a web page to parse.
        """
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Unknown API route.")
        asset = _inside_dist(full_path)
        if asset is not None:
            return FileResponse(asset)
        return FileResponse(_DIST / "index.html")
