"""Has the transcribed fund registry gone stale?

The registry in data/etf_registry.json is typed up from issuer factsheets by
hand. That is a deliberate choice and it stays: expense ratios in it are exact,
and every row carries the issuer page it should be checked against, which no
scraped feed gives you.

What a hand-typed file cannot do is notice that the world moved. A fund
rebalances, its top ten drifts, and the transcribed concentration figures go on
being scored as though they were current. This module reads the same fund from
Yahoo and says where the two disagree.

It reports. It does not score. Concentration feeds Security Quality, so letting
a drift reading move data confidence would change verdicts, and under the locked
framework rule that needs a version bump and a full rescore. Until somebody
decides it is worth that, this is an observation printed next to the number, and
the number is unchanged.
"""

from __future__ import annotations

from typing import Any

from ..providers import yahoo

#: How far a transcribed figure may sit from today's reading before it is worth
#: mentioning. Percentage points, except turnover, which is relative because a
#: 2% and a 6% turnover are both small and the gap between them is not.
TOLERANCE: dict[str, float] = {
    "expense_ratio": 0.011,
    "top10_weight": 2.0,
    "largest_holding_weight": 0.8,
}
TURNOVER_RELATIVE = 0.5

FIELDS: list[tuple[str, str, str]] = [
    ("expense_ratio", "expense_ratio_pct", "Expense ratio"),
    ("top10_weight", "top10_weight", "Top ten weight"),
    ("largest_holding_weight", "largest_holding_weight", "Largest holding weight"),
    ("turnover_pct", "turnover_pct", "Turnover"),
]


def _local(sym: str) -> bool:
    """A plain US ticker, as opposed to a foreign line like 2330.TW or 005930.KQ."""
    return "." not in sym and sym.isalpha()


def check(ticker: str, fund: dict | None) -> dict[str, Any] | None:
    """Compare a registry row against Yahoo's current read of the same fund.

    Returns None for anything that is not a registry fund, or when Yahoo has
    nothing to say. An absent second opinion is not evidence of staleness.
    """
    if not fund:
        return None
    try:
        obs = yahoo.fund_facts(ticker)
    except Exception:
        obs = None
    if not obs:
        return None
    return compare(ticker, fund, obs)


def compare(ticker: str, fund: dict, obs: dict) -> dict[str, Any] | None:
    """The comparison itself, with the fetching already done.

    Kept separate from check so the thresholds can be tested without a network
    call, which is the rule the rest of the suite is written to.
    """
    rows: list[dict[str, Any]] = []
    for reg_key, obs_key, label in FIELDS:
        # The exchange already overrides the expense ratio where it has one, so
        # compare against what was transcribed rather than what replaced it.
        ours = fund.get(f"{reg_key}_registry", fund.get(reg_key))
        theirs = obs.get(obs_key)
        if ours is None or theirs is None:
            continue
        delta = round(float(theirs) - float(ours), 3)
        if reg_key == "turnover_pct":
            scale = max(abs(float(ours)), abs(float(theirs)), 1e-9)
            drifted = abs(delta) / scale > TURNOVER_RELATIVE
        else:
            drifted = abs(delta) > TOLERANCE[reg_key]
        rows.append({
            "field": label,
            "registry": round(float(ours), 3),
            "observed": round(float(theirs), 3),
            "delta": delta,
            "units": "%",
            "status": "drifted" if drifted else "agrees",
        })

    # The largest holding by name. A foreign fund reports its top line on the
    # local exchange, so VXUS comes back as 2330.TW where the registry says TSM.
    # Those are the same company and flagging them would be noise, so a name is
    # only compared when both sides are plain US tickers.
    reg_top = (fund.get("top_holdings") or [[None]])[0][0]
    obs_top = obs.get("largest_holding")
    if reg_top and obs_top:
        if _local(str(reg_top)) and _local(str(obs_top)):
            same = str(reg_top).upper() == str(obs_top).upper()
            rows.append({
                "field": "Largest holding",
                "registry": str(reg_top).upper(),
                "observed": str(obs_top).upper(),
                "delta": None,
                "units": "",
                "status": "agrees" if same else "drifted",
            })
        else:
            rows.append({
                "field": "Largest holding",
                "registry": str(reg_top).upper(),
                "observed": str(obs_top).upper(),
                "delta": None,
                "units": "",
                "status": "not comparable",
                "note": "Reported on its local exchange, so the two lines cannot be matched by symbol.",
            })

    if not rows:
        return None

    drifted = [r for r in rows if r["status"] == "drifted"]
    return {
        "checked": True,
        "against": yahoo.SOURCE_NAME,
        "against_url": yahoo.SOURCE_URL + ticker.upper(),
        "authority_tier": yahoo.SOURCE_TIER,
        "registry_as_of": fund.get("as_of"),
        "issuer_url": fund.get("source_url", ""),
        "rows": rows,
        "drifted_count": len(drifted),
        "stale": bool(drifted),
        "scored": False,
        "note": (
            "Reported, not scored. These figures still come from the transcribed "
            "registry and the scores above are unchanged. Yahoo is tier 2 and "
            "unofficial, so a disagreement is a prompt to re-read the issuer "
            "factsheet, not a correction in its own right."
            if drifted else
            "The transcribed registry still matches an independent read of the fund."
        ),
    }
