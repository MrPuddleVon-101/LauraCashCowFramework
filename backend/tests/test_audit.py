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


def main() -> int:
    for fn in (test_fund_identities, test_date_eligibility, test_protection_mode,
               test_normalisation, test_liability_ledger, test_funding_accounting):
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
