"""LCCF-2.0.0 regression suite.

Offline by construction. Anything that would need a provider uses a recorded
fixture or a constructed instrument, so a rate limit or a flat network cannot
turn a real regression into a pass, or a passing build into a red one.

    cd backend && ./.venv/bin/python -m tests.test_v2
"""

from __future__ import annotations

import json
import os
import re
import sys
import warnings
from datetime import date
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"  {'PASS' if condition else 'FAIL'}  {name}")
    if not condition:
        FAILURES.append(f"{name}: {detail}")
        if detail:
            print(f"        {detail}")


# --- identifiers ----------------------------------------------------------------

def test_identifiers() -> None:
    from app.main import EvaluateRequest
    import pydantic

    print("\nidentifiers the engine must accept")
    accept = [
        "B-T-4.375-15112039",   # the WInS Treasury the 12 character cap excluded
        "7203:TSE", "0700:HKG", "ASML:AMS", "D05:SGX", "ULVR:LSE", "RELIANCE:NSE",
        "BRK.B", "BRK-B", "AVUS", "U", "SONY", "US0378331005",
    ]
    for t in accept:
        try:
            EvaluateRequest(ticker=t)
            ok = True
        except pydantic.ValidationError:
            ok = False
        check(f"accepts {t}", ok)

    for bad in ["", "a" * 65, "drop table users;", "AA PL"]:
        try:
            EvaluateRequest(ticker=bad)
            ok = False
        except pydantic.ValidationError:
            ok = True
        check(f"rejects {bad[:16]!r}", ok)


# --- the 2039 Treasury ----------------------------------------------------------

def test_treasury() -> None:
    from app.engine import fixedincome as fi

    print("\nB-T-4.375-15112039, from its own terms")
    t = fi.parse_wins_identifier("B-T-4.375-15112039")
    check("the identifier parses at all", t is not None)
    if t is None:
        return
    check("coupon read correctly", t.coupon_rate == 4.375, str(t.coupon_rate))
    check("maturity read as 15 November 2039", t.maturity == date(2039, 11, 15), str(t.maturity))
    check("recognised as a Treasury", t.security_type == "treasury", t.security_type)

    t.settlement = date(2026, 10, 24)
    t.face_value = 100_000.0
    t.price_pct_of_par = 98.5
    d = fi.describe(t, payment_years=list(range(2033, 2043)), payment_amount=50_000.0)

    check("a discount bond yields more than its coupon",
          d["yield_to_maturity_pct"] > t.coupon_rate,
          f"ytm {d['yield_to_maturity_pct']} vs coupon {t.coupon_rate}")
    check("modified duration is below Macaulay",
          d["modified_duration_years"] < d["macaulay_duration_years"],
          f"{d['modified_duration_years']} vs {d['macaulay_duration_years']}")
    check("duration is shorter than the time to maturity",
          d["macaulay_duration_years"] < 13.1, str(d["macaulay_duration_years"]))
    check("the final payment returns principal plus a coupon",
          abs(d["schedule"][-1]["amount"] - (100_000 + 4.375 / 2 * 1000)) < 1.0,
          str(d["schedule"][-1]))
    check("accrued interest is charged on a mid-period purchase",
          d["purchase"]["accrued_interest"] > 0, str(d["purchase"]))
    check("dirty price exceeds clean price by exactly the accrued",
          abs(d["purchase"]["dirty_price"]
              - d["purchase"]["clean_price"]
              - d["purchase"]["accrued_interest"]) < 0.01, str(d["purchase"]))

    cov = d["liability_coverage"]
    check("principal maturing in 2039 reaches the 2040 payment",
          2040 in cov["payments_fully_covered"], str(cov["payments_fully_covered"]))
    check("no dollar is counted against two payments",
          sum(cov["assigned"].values()) <= d["purchase"]["face_value"]
          + d["annual_coupon"] * 14 + 1.0,
          f"assigned {sum(cov['assigned'].values())}")

    # No time travel: a payment due 1 January can only be met by cash that has
    # already landed. The 2033 rung must be funded by exactly the coupons dated
    # before 2033, and by nothing dated after it.
    sched = fi.coupon_schedule(t, from_date=t.settlement)
    before_2033 = sum(c.amount for c in sched if c.date < date(2033, 1, 1))
    assigned_2033 = cov["assigned"].get(2033, 0.0)
    check("a payment is funded only by cash that lands before it is due",
          abs(assigned_2033 - min(before_2033, 50_000.0)) < 0.01,
          f"assigned {assigned_2033} against {before_2033} available before 2033")
    check("the maturity payment is dated after every rung it was credited to",
          all(date(y, 1, 1) > t.settlement for y in cov["payments_fully_covered"]),
          str(cov["payments_fully_covered"]))


# --- the AVUS defect ------------------------------------------------------------

def test_mandate_not_punished() -> None:
    from app.engine import funds
    from app.engine.normalize import ScoreCard

    print("\na broad U.S. fund is not judged for being American")
    fixture = json.loads((ROOT / "tests" / "fixtures" / "broad_us_fund.json").read_text())
    card = ScoreCard("test", {"diversification": 22.0})
    countries = fixture["country_weights"]
    us = sum(w for k, w in countries.items() if k.lower().startswith("united states"))
    card.measure("mandate_adherence", "Mandate adherence", 3.0, "diversification", us,
                 bands=[(60, 20), (75, 45), (85, 68), (92, 85), (97, 96), (100, 100)],
                 units="% U.S.")
    out = card.finalise()
    m = out["categories"][0]["metrics"][0]
    check("a wholly U.S. broad fund scores full marks on mandate adherence",
          m["score"] >= 95, f"score {m['score']}")
    check("the old country-Herfindahl metric is gone from the broad model",
          "geographic_breadth" not in Path(funds.__file__).read_text(),
          "geographic_breadth still present")


# --- missing data ---------------------------------------------------------------

def test_missing_never_flatters() -> None:
    from app.engine.normalize import ScoreCard

    print("\nmissing evidence cannot beat measured evidence")
    measured = ScoreCard("measured", {"c": 100.0})
    measured.measure("a", "a", 100.0, "c", 50.0, bands=[(0, 0), (50, 50), (100, 100)])
    m_out = measured.finalise()

    absent = ScoreCard("absent", {"c": 100.0})
    absent.measure("a", "a", 50.0, "c", 50.0, bands=[(0, 0), (50, 50), (100, 100)])
    absent.measure("b", "b", 50.0, "c", None)
    a_out = absent.finalise()

    check("a median measurement scores its median",
          abs(m_out["score"] - 50.0) < 1.0, str(m_out["score"]))
    check("half the model missing does not raise the score above the measured part",
          a_out["score"] <= m_out["score"] + 0.01,
          f"absent {a_out['score']} vs measured {m_out['score']}")
    check("and the absence is reported as coverage",
          a_out["coverage_pct"] == 50.0, str(a_out.get("coverage_pct")))
    check("and charged to data confidence",
          a_out["missing_weight_share"] >= 0.49, str(a_out["missing_weight_share"]))
    miss = [m for m in a_out["categories"][0]["metrics"] if m["status"] == "MISSING"]
    check("a missing metric carries no score", miss and miss[0]["score"] is None, str(miss))


# --- scoring invariants ---------------------------------------------------------

def test_weights_total() -> None:
    from app.engine import fit

    print("\ncategory weights total 100 for every role")
    for role, weights in fit.ROLE_WEIGHTS.items():
        total = sum(weights.values())
        check(f"{role} weights sum to 100", abs(total - 100.0) < 1e-6, f"{role}={total}")


def test_version_consistency() -> None:
    from app.config import FRAMEWORK_VERSION

    print("\nthe framework version is stated once and used everywhere")
    check("engine reports 2.0.0", FRAMEWORK_VERSION == "LCCF-2.0.0", FRAMEWORK_VERSION)
    hard = []
    for f in (ROOT.parent / "frontend" / "src").rglob("*.tsx"):
        body = f.read_text()
        # A version named in a comment explains history; one in the markup is
        # the defect. Strip comments before looking.
        body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)
        body = re.sub(r"(?m)^\s*//.*$", "", body)
        body = re.sub(r"(?m)\s+//.*$", "", body)
        for m in re.finditer(r"LCCF[ -]v?\d+\.\d+", body):
            hard.append(f"{f.name}: {m.group(0)}")
    check("no hard-coded version string in the interface", not hard, "; ".join(hard))


def test_no_secrets_in_bundle() -> None:
    print("\nno provider key reaches the browser bundle")
    dist = ROOT.parent / "frontend" / "dist" / "assets"
    if not dist.exists():
        check("a built bundle exists to scan", False, "run npm run build first")
        return
    names = ["FMP_API_KEY", "TWELVE_DATA_API_KEY", "OPENFIGI_API_KEY"]
    leaked: list[str] = []
    for f in dist.glob("*.js"):
        body = f.read_text(errors="ignore")
        for n in names:
            # The variable name may legitimately appear; a value must not.
            for m in re.finditer(re.escape(n) + r"\"?\s*[:=]\s*\"([^\"]{8,})\"", body):
                leaked.append(f"{f.name}: {n}")
    check("no key name is bound to a value in the bundle", not leaked, "; ".join(leaked))
    for f in dist.glob("*.js"):
        body = f.read_text(errors="ignore")
        check(f"{f.name} carries no 32-char hex secret",
              not re.search(r"[\"'][0-9a-f]{32}[\"']", body), "possible key literal")


def test_snapshot_is_whole() -> None:
    print("\na published snapshot is complete or it is not published")
    src = (ROOT / "scripts" / "build_snapshot.py").read_text()
    check("a partial refresh is refused rather than published",
          "REFUSED to publish" in src and "shutil.rmtree(staging" in src)
    check("the snapshot is scored against a real portfolio",
          "_positions(\"competition\")" in src)
    check("and refuses to run against an empty one",
          "Refusing to freeze a" in src and "empty" in src.lower())


def test_provider_degradation() -> None:
    from app.providers import router

    print("\nan absent provider is reported, never substituted silently")
    st = router.status()
    for p in st["providers"]:
        if not p["available"]:
            check(f"{p['name']} explains why it is unavailable", bool(p["reason"]), str(p))
    check("capabilities are reported per provider", isinstance(st["capabilities"], dict))
    res = router.search("anything-no-provider-can-answer-zzz")
    check("search says when it could not search globally",
          res["searched_global"] is False or bool(res["providers_used"]), str(res["note"]))


def test_ambiguity_never_silently_resolved() -> None:
    from app.providers import router

    print("\nan ambiguous ticker is never resolved for the reader")
    src = Path(router.__file__).read_text()
    check("the resolver has an explicit ambiguous branch", '"ambiguous": True' in src)
    check("and returns no instrument when it is ambiguous",
          '"resolved": None,\n            "ambiguous": True' in src
          or '"resolved": None' in src)


def main() -> int:
    for fn in (test_identifiers, test_treasury, test_mandate_not_punished,
               test_missing_never_flatters, test_weights_total, test_version_consistency,
               test_no_secrets_in_bundle, test_snapshot_is_whole,
               test_provider_degradation, test_ambiguity_never_silently_resolved):
        try:
            fn()
        except Exception as exc:
            print(f"  ERROR {fn.__name__}: {type(exc).__name__}: {exc}")
            FAILURES.append(f"{fn.__name__}: {exc}")
    print()
    if FAILURES:
        print(f"{len(FAILURES)} check(s) failed:")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("all checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
