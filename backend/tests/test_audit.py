"""Deterministic checks for the findings in the October 2026 code audit.

No network and no provider calls: every case here is arithmetic or a fixture, so
it gives the same answer on every machine. Run it with

    cd backend && ./.venv/bin/python -m tests.test_audit
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {name}")
    if not condition:
        FAILURES.append(f"{name}: {detail}")
        if detail:
            print(f"        {detail}")


# --- F02, dated fund identities ------------------------------------------------

def test_fund_identities() -> None:
    print("\nF02  dated fund identities match the issuer's registered product")
    reg = json.loads((Path(__file__).resolve().parents[1] / "data" / "etf_registry.json").read_text())
    funds = reg["funds"]
    # Verified 2026-10-05 against the issuer's registered fund names.
    for ticker, year in (("IBTM", 2032), ("IBTO", 2033), ("IBTP", 2034)):
        f = funds[ticker]
        check(f"{ticker} is the Dec {year} fund",
              f["maturity_year"] == year and str(year) in f["name"],
              f"registry says {f['maturity_year']} / {f['name']}")
        check(f"{ticker} termination date agrees with its maturity year",
              f["termination_date"].startswith(str(year)),
              f"termination_date={f['termination_date']}")
        check(f"{ticker} benchmark agrees with its maturity year",
              str(year) in f["benchmark"], f"benchmark={f['benchmark']}")


# --- F03, a December termination cannot pay a January bill ---------------------

def test_date_eligibility() -> None:
    print("\nF03  cash has to arrive before the payment, on real dates")
    from app.engine.dates import covers, match_score

    late = covers("2033-12-15", 2033)
    check("December 2033 cannot cover January 2033", not late.ok, late.reason)
    check("a late instrument scores near zero on date match", match_score(late) <= 10.0)

    early = covers("2032-12-15", 2033)
    check("December 2032 can cover January 2033", early.ok, early.reason)
    check("an eligible instrument scores well", match_score(early) >= 80.0)

    none = covers(None, 2033)
    check("no termination date is not a match", not none.ok, none.reason)
    untargeted = covers("2032-12-15", None)
    check("no nominated payment is not a match", not untargeted.ok, untargeted.reason)


# --- F06, protection mode must not flatter a risky holding ---------------------

def test_protection_mode() -> None:
    print("\nF06  a more protective state cannot improve the same risky holding")
    from app.engine.fit import downside_score

    scores = {m: downside_score(-45.0, m) for m in ("GROWTH", "BALANCED", "PROTECTION")}
    check("growth >= balanced >= protection for a -45% drawdown",
          scores["GROWTH"] >= scores["BALANCED"] >= scores["PROTECTION"],
          f"{scores}")
    check("protection is strictly harsher than growth",
          scores["PROTECTION"] < scores["GROWTH"], f"{scores}")


# --- F10, normalisation ---------------------------------------------------------

def test_normalisation() -> None:
    print("\nF10  ties are neutral, weights are conserved, nonfinite values are rejected")
    from app.engine.normalize import NEUTRAL, ScoreCard, score_against_peers

    peers = [5.0] * 20
    hi, _, _ = score_against_peers(5.0, peers, higher_is_better=True)
    lo, _, _ = score_against_peers(5.0, peers, higher_is_better=False)
    check("an all-tie peer set scores the same either way", abs(hi - lo) < 1e-6, f"{hi} vs {lo}")
    check("an all-tie peer set scores neutral", abs(hi - NEUTRAL) < 1e-6, f"{hi}")

    nan, _, _ = score_against_peers(float("nan"), [1.0, 2.0, 3.0])
    check("a NaN value cannot produce a score", nan == NEUTRAL, f"{nan}")

    card = ScoreCard("fixture", {"resolved": 50.0, "unresolved": 50.0})
    card.measure("a", "a", 50.0, "resolved", 1.0, bands=[(0, 100), (2, 100)])
    card.measure("b", "b", 40.0, "unresolved", None, not_applicable=True, na_reason="n/a")
    card.measure("c", "c", 10.0, "unresolved", None)
    out = card.finalise()
    check("a wholly unresolved category keeps its weight",
          abs(out["points_available"] - 100.0) < 1e-6, f"available={out['points_available']}")
    check("the unresolved half is charged to missing",
          out["missing_weight_share"] >= 0.49, f"missing={out['missing_weight_share']}")


# --- F15, the liability ledger --------------------------------------------------

def test_liability_ledger() -> None:
    print("\nF15  partial coverage reduces what is left to secure")
    from app.engine import liability

    flat = {"as_of": "2026-10-05", "source": "fixture", "degraded": False,
            "points": [{"years": y, "yield_pct": 0.0, "tenor": f"{y}y"} for y in range(1, 31)]}
    full = liability.build_calendar(as_of_year=2027, matched=[], curve=flat)
    part = liability.build_calendar(
        as_of_year=2027, curve=flat,
        matched=[liability.MatchedAsset(ticker="FIX", payment_year=2033,
                                        expected_cash_flow=25_000.0, note="fixture")],
    )
    check("undedicated cost to secure is the whole obligation",
          abs(full["cost_to_secure_remaining"] - 500_000.0) < 1.0,
          f"{full['cost_to_secure_remaining']}")
    check("$25,000 dedicated reduces it to $475,000",
          abs(part["cost_to_secure_remaining"] - 475_000.0) < 1.0,
          f"{part['cost_to_secure_remaining']}")


# --- F01, reserved capital is not spendable ------------------------------------

def test_funding_accounting() -> None:
    print("\nF01  a dedicated dollar cannot also be spent on the facility")
    from app.engine import simulate

    flat = {"as_of": "2026-10-05", "source": "fixture", "degraded": False,
            "points": [{"years": y, "yield_pct": 0.0, "tenor": f"{y}y"} for y in range(1, 31)]}
    still = simulate.Assumptions(equity_return=0.0, equity_vol=0.0,
                                 bond_return=0.0, bond_vol=0.0)
    out = simulate.project(equity_weight=0.0, assumptions=still, n_paths=200,
                           ladder_payments_secured=10, flat_yield=0.0, curve=flat)
    check("$450,000 cannot fund $500,000 of payments",
          out["funding_probability"] < 0.5,
          f"probability={out['funding_probability']:.3f}")
    check("and it leaves no facility capacity",
          out["facility_capacity"]["median"] <= 0.0,
          f"median facility={out['facility_capacity']['median']}")


# --- F08, ratios must not mix reporting periods --------------------------------

def test_period_alignment() -> None:
    print("\nF08  every ratio is built from one reporting period")
    from app.providers.sec import Fundamentals, _derive

    f = Fundamentals(ticker="FIX", cik=1, name="Fixture")
    # Revenue and operating income filed through 2025; interest expense stops in
    # 2023, exactly as Apple's filings do.
    f.revenue = {2022: 100.0, 2023: 110.0, 2024: 120.0, 2025: 130.0}
    f.operating_income = {2022: 20.0, 2023: 22.0, 2024: 24.0, 2025: 26.0}
    f.interest_expense = {2022: 2.0, 2023: 2.0}
    f.ocf = {2025: 30.0}
    f.capex = {2025: 5.0}
    _derive(f)
    r = f.ratios

    check("the reference period is the latest complete year", f.reference_year == 2025,
          f"reference_year={f.reference_year}")
    check("a line absent from that year cannot produce a ratio",
          r.get("interest_coverage") is None, f"interest_coverage={r.get('interest_coverage')}")
    check("the absence is recorded, not hidden",
          "interest_expense" in f.lines_absent_in_reference, f"{f.lines_absent_in_reference}")
    check("lines present in that year still compute",
          r.get("operating_margin") is not None and abs(r["operating_margin"] - 20.0) < 0.01,
          f"operating_margin={r.get('operating_margin')}")


def test_cagr_span() -> None:
    print("\nF08  a three year CAGR has to span three years")
    from app.providers.sec import _cagr

    dense = {2022: 100.0, 2023: 110.0, 2024: 120.0, 2025: 133.1}
    check("a complete window computes", _cagr(dense, 3) is not None)
    check("and computes correctly", abs(_cagr(dense, 3) - 10.0) < 0.1, f"{_cagr(dense, 3)}")

    sparse = {2018: 50.0, 2020: 70.0, 2024: 120.0, 2025: 130.0}
    check("a window missing its start year reports nothing",
          _cagr(sparse, 3) is None, f"got {_cagr(sparse, 3)} from four sparse observations")


# --- F08, a trailing figure has to actually trail -------------------------------

def test_trailing_window() -> None:
    print("\nF08  a multiple describes the trailing window, not a finished fiscal year")
    from app.providers.sec import Fundamentals, _derive
    from app.providers.yahoo import TTM

    f = Fundamentals(ticker="FIX", cik=1, name="Fixture")
    f.revenue = {2024: 100.0, 2025: 120.0}
    f.net_income = {2024: 10.0, 2025: 12.0}
    f.eps = {2024: 1.0, 2025: 1.2}
    f.equity = {2025: 60.0}

    _derive(f, None)
    check("with no quarters it falls back to the fiscal year",
          f.ratios.get("eps_latest") == 1.2 and not f.flow_is_ttm, f"{f.ratios.get('eps_latest')}")
    check("and says so plainly", "No quarterly filings" in f.flow_basis, f.flow_basis)

    g = Fundamentals(ticker="FIX", cik=1, name="Fixture")
    g.revenue = {2024: 100.0, 2025: 120.0}
    g.net_income = {2024: 10.0, 2025: 12.0}
    g.eps = {2024: 1.0, 2025: 1.2}
    g.equity = {2025: 60.0}
    trailing = TTM(ok=True, quarters=4, start="2025-10-31", end="2026-07-31",
                   flow={"revenue": 300.0, "net_income": 30.0, "eps_diluted": 3.0},
                   stock={"equity": 90.0})
    _derive(g, trailing)
    check("four quarters on file take precedence over the fiscal year",
          g.ratios.get("eps_latest") == 3.0 and g.flow_is_ttm, f"{g.ratios.get('eps_latest')}")
    check("and the basis names the window", "2026-07-31" in g.flow_basis, g.flow_basis)
    check("the balance sheet comes from the latest quarter too",
          abs((g.ratios.get("roe") or 0) - (30.0 / 90.0 * 100)) < 0.01, f"roe={g.ratios.get('roe')}")


# --- registry drift, reported and never scored ---------------------------------


def test_registry_drift() -> None:
    from app.engine import drift

    print("\nregistry drift is reported, not scored")

    fund = {
        "expense_ratio": 0.15, "top10_weight": 24.5,
        "largest_holding_weight": 5.4, "turnover_pct": 6.0,
        "top_holdings": [["NVDA", 5.4], ["AAPL", 4.6]],
        "as_of": "2026-09-30", "source_url": "https://example.invalid/avus",
    }
    moved = drift.compare("AVUS", fund, {
        "expense_ratio_pct": 0.15, "top10_weight": 30.79,
        "largest_holding_weight": 5.864, "turnover_pct": 2.0,
        "largest_holding": "NVDA",
    })
    by = {r["field"]: r for r in moved["rows"]}
    check("a top ten that has moved six points is flagged",
          by["Top ten weight"]["status"] == "drifted",
          str(by["Top ten weight"]))
    check("an expense ratio that still matches is not",
          by["Expense ratio"]["status"] == "agrees", str(by["Expense ratio"]))
    check("turnover is judged relatively, so 6 against 2 is drift",
          by["Turnover"]["status"] == "drifted", str(by["Turnover"]))
    check("the fund is marked stale", moved["stale"] is True)
    check("and the reading is explicitly not scored", moved["scored"] is False)

    steady = drift.compare("VTI", {
        "expense_ratio": 0.03, "top10_weight": 33.0,
        "largest_holding_weight": 6.8, "turnover_pct": 2.0,
        "top_holdings": [["NVDA", 6.8]],
    }, {
        "expense_ratio_pct": 0.03, "top10_weight": 33.45,
        "largest_holding_weight": 6.875, "turnover_pct": 3.0,
        "largest_holding": "NVDA",
    })
    check("a registry row that still agrees raises nothing",
          steady["stale"] is False and steady["drifted_count"] == 0,
          str(steady["rows"]))

    # A foreign fund reports its top line on the local exchange. TSM and 2330.TW
    # are the same company and flagging them would be noise.
    foreign = drift.compare("VXUS", {
        "expense_ratio": 0.05, "top10_weight": 12.0,
        "largest_holding_weight": 2.3, "turnover_pct": 3.0,
        "top_holdings": [["TSM", 2.3]],
    }, {
        "expense_ratio_pct": 0.05, "top10_weight": 12.8,
        "largest_holding_weight": 2.35, "turnover_pct": 4.0,
        "largest_holding": "2330.TW",
    })
    names = {r["field"]: r for r in foreign["rows"]}["Largest holding"]
    check("a local exchange line is not comparable rather than drifted",
          names["status"] == "not comparable", str(names))
    check("and it does not make the fund stale on its own",
          foreign["stale"] is False, str(foreign["rows"]))

    # The exchange already overrides the expense ratio, so the comparison has to
    # look at what was transcribed rather than at what replaced it.
    overridden = drift.compare("SGOV", {
        "expense_ratio": 0.05, "expense_ratio_registry": 0.09,
        "top_holdings": [],
    }, {"expense_ratio_pct": 0.09})
    er = {r["field"]: r for r in overridden["rows"]}["Expense ratio"]
    check("the transcribed figure is what gets compared, not the live override",
          er["registry"] == 0.09 and er["status"] == "agrees", str(er))


def main() -> int:
    for fn in (test_fund_identities, test_date_eligibility, test_protection_mode,
               test_normalisation, test_liability_ledger, test_funding_accounting,
               test_period_alignment, test_cagr_span, test_trailing_window,
               test_registry_drift):
        try:
            fn()
        except Exception as exc:  # a missing helper is itself a failure to report
            print(f"  ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
            FAILURES.append(f"{fn.__name__}: {exc}")
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
