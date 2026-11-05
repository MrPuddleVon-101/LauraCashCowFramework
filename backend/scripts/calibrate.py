"""Does the ladder order securities the way a committee would?

Thresholds that are chosen and then never checked are decoration. This scores a
deliberately mixed panel and reports the distribution, the ordering, and every
case that lands somewhere a reasonable person would not expect.

It tests relationships, not winners. The expectations below are the ones the
framework actually commits to:

  * a diversified core ETF is not red for following its mandate
  * a dated Treasury outranks a perpetual bond fund for a dated liability
  * changing the role moves fit and leaves quality alone
  * changing the size moves portfolio impact
  * a weak business scores below a strong one

    cd backend && ./.venv/bin/python -m scripts.calibrate
"""

from __future__ import annotations

import json
import sys
import warnings
from collections import Counter
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import FRAMEWORK_VERSION, POLICY  # noqa: E402
from app.engine import evaluate as ev  # noqa: E402
from app.main import _positions  # noqa: E402

#: ticker, the bucket it belongs to, and the role it should be judged in.
PANEL: list[tuple[str, str, str | None]] = [
    ("VTI",  "broad core ETF", "CG"),
    ("VOO",  "broad core ETF", "CG"),
    ("AVUS", "broad core ETF", "CG"),
    ("VXUS", "international diversifier", "ID"),
    ("VEA",  "international diversifier", "ID"),
    ("VWO",  "international diversifier", "ID"),
    ("AAPL", "quality profitable stock", "SG"),
    ("MSFT", "quality profitable stock", "SG"),
    ("COST", "quality profitable stock", "SG"),
    ("NVDA", "higher risk growth stock", "SG"),
    ("TSLA", "higher risk growth stock", "SG"),
    ("PLTR", "higher risk growth stock", "SG"),
    ("INTC", "weak or distressed stock", "SG"),
    ("F",    "weak or distressed stock", "SG"),
    ("PFE",  "weak or distressed stock", "SG"),
    ("SGOV", "cash equivalent", "LR"),
    ("VGSH", "cash equivalent", "LR"),
    ("BND",  "perpetual bond fund", "DA"),
    ("TLT",  "perpetual bond fund", "DA"),
    ("IBTM", "defined maturity fund", "LM"),
    ("IBTO", "defined maturity fund", "LM"),
    ("IBTP", "defined maturity fund", "LM"),
    ("SMH",  "sector or thematic ETF", "SG"),
    ("QQQM", "sector or thematic ETF", "SG"),
]

MATURITY = {"IBTM": 2033, "IBTO": 2034, "IBTP": 2035}


def run(ticker: str, role: str | None, pct: float, portfolio) -> dict | None:
    try:
        return ev.evaluate(ticker, role=role, position_pct=pct, portfolio=portfolio,
                           target_payment_year=MATURITY.get(ticker))
    except Exception as exc:
        print(f"  {ticker:<6} FAILED {type(exc).__name__}: {exc}", flush=True)
        return None


def main() -> int:
    portfolio = _positions("competition")
    rows: list[dict] = []
    print(f"Calibrating {FRAMEWORK_VERSION} over {len(PANEL)} securities\n")
    for t, bucket, role in PANEL:
        r = run(t, role, 8.0, portfolio)
        if not r:
            continue
        sc = r["scores"]
        rows.append({
            "ticker": t, "bucket": bucket, "role": role,
            "sqs": sc["security_quality"], "lpfs": sc["laura_fit"],
            "ccs": sc["composite"], "dcs": sc["data_confidence"],
            "signal": r["signal"]["signal"],
            "gate": r["red_gate"]["status"],
            "coverage": r["security_quality"].get("coverage_pct"),
        })
        print(f"  {t:<6}{bucket:<28}{sc['composite']:>6}  {r['signal']['signal']}", flush=True)

    print("\n--- distribution -------------------------------------------------")
    dist = Counter(r["signal"] for r in rows)
    for sig, n in dist.most_common():
        print(f"  {sig:<20}{n:>3}  {n / len(rows):>6.0%}")

    print("\n--- by bucket, mean composite -----------------------------------")
    buckets: dict[str, list[float]] = {}
    for r in rows:
        buckets.setdefault(r["bucket"], []).append(r["ccs"])
    ordered = sorted(buckets.items(), key=lambda kv: -sum(kv[1]) / len(kv[1]))
    for b, vals in ordered:
        print(f"  {b:<28}{sum(vals) / len(vals):>6.1f}   n={len(vals)}")

    print("\n--- relationships the framework commits to ----------------------")
    failures: list[str] = []

    def expect(name: str, ok: bool, detail: str = "") -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
        if not ok:
            failures.append(f"{name}: {detail}")
            if detail:
                print(f"        {detail}")

    core = [r for r in rows if r["bucket"] == "broad core ETF"]
    expect("a diversified core ETF is never red for following its mandate",
           all(r["signal"] != "RED" for r in core),
           ", ".join(f"{r['ticker']}={r['signal']}" for r in core))

    dated = [r["ccs"] for r in rows if r["bucket"] == "defined maturity fund"]
    perp = [r["ccs"] for r in rows if r["bucket"] == "perpetual bond fund"]
    if dated and perp:
        expect("a dated matcher outranks a perpetual bond fund for a dated liability",
               min(dated) > max(perp), f"dated min {min(dated)} vs perpetual max {max(perp)}")

    strong = [r["ccs"] for r in rows if r["bucket"] == "quality profitable stock"]
    weak = [r["ccs"] for r in rows if r["bucket"] == "weak or distressed stock"]
    if strong and weak:
        expect("quality businesses outrank distressed ones on average",
               sum(strong) / len(strong) > sum(weak) / len(weak),
               f"{sum(strong) / len(strong):.1f} vs {sum(weak) / len(weak):.1f}")

    # Role changes fit, never quality.
    a = run("AVUS", "CG", 8.0, portfolio)
    b = run("AVUS", "SG", 8.0, portfolio)
    if a and b:
        expect("changing the role leaves security quality untouched",
               abs(a["scores"]["security_quality"] - b["scores"]["security_quality"]) < 0.05,
               f"{a['scores']['security_quality']} vs {b['scores']['security_quality']}")
        expect("changing the role does move Laura fit",
               abs(a["scores"]["laura_fit"] - b["scores"]["laura_fit"]) > 0.05,
               f"{a['scores']['laura_fit']} vs {b['scores']['laura_fit']}")

    # Size changes portfolio impact.
    small = run("NVDA", "SG", 2.0, portfolio)
    large = run("NVDA", "SG", 25.0, portfolio)
    if small and large:
        sd = small["portfolio_impact"]["delta"]["issuer_hhi"]
        ld = large["portfolio_impact"]["delta"]["issuer_hhi"]
        expect("a larger position crowds the book more", ld > sd, f"{ld} vs {sd}")
        sf = small["funding_after_trade"]["funding_probability"]
        lf = large["funding_after_trade"]["funding_probability"]
        expect("and the funding projection responds to size", sf != lf, f"{sf} vs {lf}")

    print("\n--- outliers ----------------------------------------------------")
    outliers = 0
    for r in rows:
        if r["bucket"] == "broad core ETF" and r["ccs"] < POLICY.amber_min_ccs:
            print(f"  {r['ticker']}: core ETF below the amber floor at {r['ccs']}")
            outliers += 1
        if r["bucket"] == "cash equivalent" and r["signal"] == "RED":
            print(f"  {r['ticker']}: cash equivalent scored red")
            outliers += 1
        if r["dcs"] < POLICY.insufficient_data_dcs:
            print(f"  {r['ticker']}: data confidence {r['dcs']} below the floor")
            outliers += 1
    if not outliers:
        print("  none")

    out = Path(__file__).resolve().parents[1] / "calibration-report.json"
    out.write_text(json.dumps({
        "framework_version": FRAMEWORK_VERSION,
        "panel_size": len(rows),
        "distribution": dict(dist),
        "thresholds": {
            "green": {"sqs": POLICY.green_min_sqs, "lpfs": POLICY.green_min_lpfs,
                      "ccs": POLICY.green_min_ccs, "dcs": POLICY.green_min_dcs},
            "amber_plus": {"ccs": POLICY.amber_plus_min_ccs,
                           "component": POLICY.amber_plus_min_component},
            "amber_floor": POLICY.amber_min_ccs,
            "red_below": POLICY.red_max_sqs,
            "insufficient_dcs": POLICY.insufficient_data_dcs,
        },
        "rows": rows,
        "relationship_failures": failures,
    }, indent=1))
    print(f"\nwrote {out}")

    if failures:
        print(f"\n{len(failures)} relationship(s) failed:")
        for f in failures:
            print("  -", f)
        return 1
    print("\nevery committed relationship holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
