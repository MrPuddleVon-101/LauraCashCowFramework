"""Normalisation, evidence and the audit trail.

PRD 12 forbids adding raw financial numbers together: a 25% operating margin is
exceptional in one industry and ordinary in another. Every quantitative metric is
therefore converted to a 0-100 score against a peer group before it is weighted.

PRD 50 requires that every score be auditable, so a Metric carries its value, units,
peer median, percentile, weight, weighted contribution, source and as-of date. The
audit trail is not generated afterwards. It is the data structure the score is made of.
"""

from __future__ import annotations

import math
from numbers import Real
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from typing import Iterable, Literal, Sequence

MetricStatus = Literal["OK", "NOT_APPLICABLE", "MISSING"]

# PRD 11 source hierarchy. Tier 5 may provide a lead but never a numerical score.
TIER_LABELS = {
    1: "Primary filing or issuer document",
    2: "Professional market database",
    3: "Established financial publication",
    4: "News, analyst commentary or interview",
    5: "Unverified aggregator or social media",
}


@dataclass
class Source:
    name: str
    url: str = ""
    source_type: str = "filing"
    authority_tier: int = 1
    publication_date: str | None = None
    claim_supported: str = ""
    accessed_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["authority_label"] = TIER_LABELS.get(self.authority_tier, "Unclassified")
        return d


SEC_FILING = Source(
    name="SEC EDGAR company facts (XBRL)",
    url="https://data.sec.gov/api/xbrl/companyfacts/",
    source_type="filing",
    authority_tier=1,
)


# The percentile is a rank. The score is a judgement about that rank, and the two
# are not the same number.
#
# Mapping rank straight onto the score (p50 -> 50) looks neutral and is not. The
# bands in `score_band` call 50 to 70 "neutral" and 90 or above "exceptional", and
# the signal ladder wants 90 on both scores for a green call. But a card weighs
# twenty or more of these together, and a weighted mean of twenty percentiles
# regresses hard to the middle: on the raw mapping no real company ever reached
# 70, let alone 90, so every candidate came out RED and the signal carried no
# information at all.
#
# The anchors below put the median company at 62, which is what "neutral" is
# supposed to mean here, and reserve the 90s for genuine top-decile readings. The
# curve is strictly monotone, so nothing is reordered: a company that ranked above
# another still scores above it. The raw percentile is still reported on every
# metric, so the audit trail shows the rank as well as the reading of it.
#
# It also puts the two kinds of metric on the same scale. Metrics scored against
# documented threshold bands were always written in this register (a 16x earnings
# multiple is written as 74, not as "whatever fraction of the market is dearer"),
# while peer-scored metrics were in raw rank. Mixing the two inside one weighted
# card was comparing two different scales.
PERCENTILE_CURVE: tuple[tuple[float, float], ...] = (
    (0.00, 8.0),
    (0.05, 20.0),
    (0.10, 30.0),
    (0.20, 42.0),
    (0.30, 50.0),
    (0.40, 56.5),
    (0.50, 62.0),
    (0.60, 67.5),
    (0.70, 73.5),
    (0.80, 80.0),
    (0.90, 88.0),
    (0.95, 93.0),
    (1.00, 98.0),
)

#: What an unmeasured or deliberately unopinionated metric scores. It has to be the
#: curve's own midpoint, or "neutral" would quietly be a penalty.
NEUTRAL = 62.0


def curve_score(rank: float) -> float:
    """Convert a 0..1 rank into a 0..100 score along the documented anchors."""
    r = min(max(rank, 0.0), 1.0)
    pts = PERCENTILE_CURVE
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= r <= x1:
            if x1 == x0:
                return round(y1, 1)
            t = (r - x0) / (x1 - x0)
            return round(y0 + (y1 - y0) * t, 1)
    return round(pts[-1][1], 1)


def score_band(score: float) -> str:
    """PRD 12 score interpretation bands."""
    if score >= 90:
        return "Exceptional"
    if score >= 80:
        return "Strong"
    if score >= 70:
        return "Above average"
    if score >= 50:
        return "Neutral"
    if score >= 30:
        return "Weak"
    return "Serious weakness"


@dataclass
class Metric:
    key: str
    label: str
    weight: float
    category: str
    score: float = NEUTRAL
    value: float | None = None
    units: str = ""
    status: MetricStatus = "OK"
    higher_is_better: bool = True
    percentile: float | None = None
    peer_median: float | None = None
    peer_group: str = ""
    as_of: str | None = None
    source: Source | None = None
    interpretation: str = ""
    note: str = ""
    # Set by ScoreCard.finalise once redistribution is known.
    effective_weight: float = 0.0

    @property
    def contribution(self) -> float:
        return self.effective_weight * self.score / 100.0

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "category": self.category,
            "weight": round(self.weight, 4),
            "effective_weight": round(self.effective_weight, 4),
            "score": round(self.score, 1),
            "band": score_band(self.score),
            "value": self.value,
            "units": self.units,
            "status": self.status,
            "higher_is_better": self.higher_is_better,
            "percentile": None if self.percentile is None else round(self.percentile * 100, 1),
            "peer_median": self.peer_median,
            "peer_group": self.peer_group,
            "as_of": self.as_of,
            "source": self.source.to_dict() if self.source else None,
            "interpretation": self.interpretation,
            "note": self.note,
            "contribution": round(self.contribution, 3),
        }


def winsorise(values: Sequence[float], low: float = 0.05, high: float = 0.95) -> list[float]:
    """Clip to the 5th and 95th percentiles so one outlier cannot distort a rank."""
    if not values:
        return []
    ordered = sorted(values)
    lo = _quantile(ordered, low)
    hi = _quantile(ordered, high)
    return [min(max(v, lo), hi) for v in values]


def _quantile(ordered: Sequence[float], q: float) -> float:
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    pos = q * (len(ordered) - 1)
    lower = math.floor(pos)
    upper = math.ceil(pos)
    if lower == upper:
        return ordered[int(pos)]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (pos - lower)


def finite(value: float | None) -> float | None:
    """Return the value only if it is a real, finite number.

    NaN and infinity used to pass straight through into rankings, JSON responses
    and score comparisons, where NaN compares false against everything and
    quietly lands at one end of a distribution.
    """
    if value is None or isinstance(value, bool) or not isinstance(value, Real):
        return None
    v = float(value)
    return v if math.isfinite(v) else None


def percentile_rank(value: float, peers: Sequence[float]) -> float:
    """Tie-aware rank of `value` within the winsorised peer set, in 0..1.

    Counting everything at or below the value made a complete tie rank 1.0, so a
    candidate identical to every peer scored 98 when higher was better and 8 when
    lower was better: the same company at opposite ends of the scale depending on
    which way the metric pointed. Splitting the tied block puts it at the middle,
    which is what being indistinguishable from your peers actually means.
    """
    clean = [p for p in (finite(x) for x in peers) if p is not None]
    v = finite(value)
    if not clean or v is None:
        return 0.5
    clipped = winsorise(clean)
    lo, hi = min(clipped), max(clipped)
    v = min(max(v, lo), hi)
    below = sum(1 for p in clipped if p < v)
    equal = sum(1 for p in clipped if p == v)
    return (below + equal / 2.0) / len(clipped)


def score_against_peers(
    value: float | None,
    peers: Sequence[float],
    higher_is_better: bool = True,
) -> tuple[float, float | None, float | None]:
    """Returns (score 0-100, percentile 0-1, peer median)."""
    if finite(value) is None or not peers:
        return NEUTRAL, None, None
    pct = percentile_rank(value, peers)
    rank = pct if higher_is_better else 1.0 - pct
    score = curve_score(rank)
    median = _quantile(sorted(peers), 0.5)
    return score, pct, median


def score_against_bands(value: float | None, bands: Sequence[tuple[float, float]], higher_is_better: bool = True) -> float:
    """Documented threshold fallback for when peer data is unavailable (PRD 12).

    `bands` is an ascending list of (threshold, score) pairs expressed in the metric's
    own units. Interpolates linearly between the two bracketing bands so the score
    moves continuously rather than stepping.
    """
    value = finite(value)
    if value is None or not bands:
        return NEUTRAL
    pts = sorted(bands, key=lambda b: b[0])
    if value <= pts[0][0]:
        return float(pts[0][1])
    if value >= pts[-1][0]:
        return float(pts[-1][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= value <= x1:
            if x1 == x0:
                return float(y1)
            t = (value - x0) / (x1 - x0)
            return round(y0 + (y1 - y0) * t, 1)
    return NEUTRAL


class ScoreCard:
    """Collects metrics, applies the PRD 60 missing-data rules, and totals to 100."""

    def __init__(self, model_name: str, categories: dict[str, float]):
        self.model_name = model_name
        self.categories = categories  # category key -> total points available
        self.metrics: list[Metric] = []
        self.empty_categories: list[str] = []
        self._finalised = False

    def add(self, metric: Metric) -> Metric:
        self.metrics.append(metric)
        return metric

    def measure(
        self,
        key: str,
        label: str,
        weight: float,
        category: str,
        value: float | None,
        *,
        peers: Sequence[float] | None = None,
        bands: Sequence[tuple[float, float]] | None = None,
        higher_is_better: bool = True,
        blend: float = 0.0,
        units: str = "",
        peer_group: str = "",
        as_of: str | None = None,
        source: Source | None = None,
        interpretation: str = "",
        not_applicable: bool = False,
        na_reason: str = "",
    ) -> Metric:
        """Score one metric, preferring peer percentile and falling back to bands."""
        if not_applicable:
            m = Metric(
                key=key, label=label, weight=weight, category=category, value=value,
                units=units, status="NOT_APPLICABLE", higher_is_better=higher_is_better,
                as_of=as_of, source=source, note=na_reason or "Not applicable to this security.",
            )
            return self.add(m)

        if finite(value) is None:
            m = Metric(
                key=key, label=label, weight=weight, category=category, value=None,
                units=units, status="MISSING", higher_is_better=higher_is_better,
                score=NEUTRAL, as_of=as_of, source=source,
                note="Not available from a source we trust. Scored neutral and charged against data confidence.",
            )
            return self.add(m)

        pct = None
        median = None
        if peers and bands and blend > 0:
            # Some measures carry an absolute meaning that rank alone destroys. Net
            # debt of 0.38x EBITDA is conservative whatever the peer group does with
            # leverage, and ranking it against a sector full of net-cash balance
            # sheets scores it as though it were risky. `blend` is the weight given
            # to the threshold band, with the remainder on the peer percentile.
            peer_score, pct, median = score_against_peers(value, peers, higher_is_better)
            band_score = score_against_bands(value, bands, higher_is_better)
            score = round(band_score * blend + peer_score * (1 - blend), 1)
        elif peers:
            score, pct, median = score_against_peers(value, peers, higher_is_better)
        elif bands:
            score = score_against_bands(value, bands, higher_is_better)
        else:
            score = NEUTRAL

        m = Metric(
            key=key, label=label, weight=weight, category=category, score=score,
            value=value, units=units, status="OK", higher_is_better=higher_is_better,
            percentile=pct, peer_median=median, peer_group=peer_group, as_of=as_of,
            source=source, interpretation=interpretation,
        )
        return self.add(m)

    def qualitative(
        self,
        key: str,
        label: str,
        weight: float,
        category: str,
        score: float,
        evidence: list[str],
        source: Source | None = None,
        as_of: str | None = None,
    ) -> Metric:
        """PRD 15 and 51. A qualitative claim needs evidence attached or it is not a score."""
        if not evidence:
            m = Metric(
                key=key, label=label, weight=weight, category=category, status="MISSING",
                score=NEUTRAL, source=source, as_of=as_of,
                note="No supporting evidence on file, so this is held at neutral rather than asserted.",
            )
            return self.add(m)
        m = Metric(
            key=key, label=label, weight=weight, category=category, score=score,
            status="OK", source=source, as_of=as_of,
            interpretation=" ".join(evidence),
        )
        return self.add(m)

    def finalise(self) -> dict:
        """Apply redistribution, total the categories, and return the audit trail.

        PRD 60 draws a hard line between two cases. A metric that is genuinely not
        applicable, such as P/E for a company with negative earnings, gives its weight
        back to the related metrics in its own category. A metric that is simply
        missing keeps its weight at a neutral 50 and is charged against data
        confidence instead, so an absent number can never flatter a security.
        """
        by_cat: dict[str, list[Metric]] = {}
        for m in self.metrics:
            by_cat.setdefault(m.category, []).append(m)

        for cat, metrics in by_cat.items():
            na_weight = sum(m.weight for m in metrics if m.status == "NOT_APPLICABLE")
            # Weight released by a not-applicable metric goes only to metrics we could
            # actually measure. Moving it onto a metric that is itself missing would
            # quietly enlarge the neutral-scored share of the model and overstate how
            # much of the security we failed to observe.
            observed = [m for m in metrics if m.status == "OK"]
            observed_weight = sum(m.weight for m in observed)
            for m in metrics:
                if m.status == "NOT_APPLICABLE":
                    m.effective_weight = 0.0
                elif m.status == "OK" and observed_weight > 0:
                    m.effective_weight = m.weight + na_weight * (m.weight / observed_weight)
                else:
                    m.effective_weight = m.weight
            if not observed:
                # Nothing in this category resolved. The released weight has to stay
                # inside the category, or the model silently shrinks: a 50 point
                # category of 40 not-applicable plus 10 missing used to contribute
                # only 10 points, which magnified every category that did resolve and
                # understated how much evidence was actually absent.
                declared = self.categories.get(cat, sum(m.weight for m in metrics))
                missing = [m for m in metrics if m.status == "MISSING"]
                if missing:
                    missing_weight = sum(m.weight for m in missing) or 1.0
                    for m in missing:
                        m.effective_weight = declared * (m.weight / missing_weight)
                else:
                    # Every metric in the category is genuinely inapplicable. Holding
                    # the weight at neutral would invent an opinion, so the category
                    # is recorded as carrying no points and the fact is reported.
                    for m in metrics:
                        m.effective_weight = 0.0
                    self.empty_categories.append(cat)

        total = sum(m.contribution for m in self.metrics)
        available = sum(m.effective_weight for m in self.metrics)
        total_score = (total / available * 100.0) if available else NEUTRAL

        missing_weight = sum(m.effective_weight for m in self.metrics if m.status == "MISSING")
        declared = sum(self.categories.values()) or 100.0
        missing_share = missing_weight / declared if declared else 0.0

        categories = []
        for cat, points in self.categories.items():
            metrics = by_cat.get(cat, [])
            earned = sum(m.contribution for m in metrics)
            avail = sum(m.effective_weight for m in metrics)
            categories.append({
                "key": cat,
                "points_available": round(avail, 2),
                "points_declared": points,
                "points_earned": round(earned, 2),
                "score": round(earned / avail * 100, 1) if avail else NEUTRAL,
                "metrics": [m.to_dict() for m in metrics],
            })

        self._finalised = True
        return {
            "model": self.model_name,
            "score": round(total_score, 1),
            "band": score_band(total_score),
            "points_earned": round(total, 2),
            "points_available": round(available, 2),
            "missing_weight_share": round(missing_share, 4),
            "inapplicable_categories": list(self.empty_categories),
            "categories": categories,
            "metrics": [m.to_dict() for m in self.metrics],
        }


def data_confidence(
    card: dict,
    *,
    source_tiers: Iterable[int],
    freshest_as_of: str | None,
    cross_source_agreement: float = 1.0,
    peer_group_size: int = 0,
    today: date | None = None,
) -> dict:
    """PRD 10. Data confidence is independent of the investment scores.

    Completeness 30, source authority 25, freshness 20, cross-source consistency 15,
    peer-group adequacy 10. The point is that the framework never dresses weak data
    up as precision.
    """
    today = today or date.today()

    # Completeness: share of weight that resolved to a real observation.
    missing_share = card.get("missing_weight_share", 0.0)
    completeness = max(0.0, 1.0 - missing_share) * 100

    # Source authority: tier 1 is full marks, tier 5 scores nothing.
    tiers = [t for t in source_tiers if t]
    if tiers:
        authority = sum(max(0.0, (5 - t) / 4) for t in tiers) / len(tiers) * 100
    else:
        authority = 40.0

    # Freshness: a filing loses confidence as it ages.
    if freshest_as_of:
        try:
            parsed = datetime.strptime(freshest_as_of[:10], "%Y-%m-%d").date()
            age_days = max(0, (today - parsed).days)
            freshness = score_against_bands(
                float(age_days),
                [(0, 100), (95, 97), (200, 88), (400, 70), (730, 40), (1460, 10)],
                higher_is_better=False,
            )
        except ValueError:
            freshness = 50.0
    else:
        freshness = 35.0

    consistency = max(0.0, min(1.0, cross_source_agreement)) * 100

    peer_adequacy = score_against_bands(
        float(peer_group_size), [(0, 10), (3, 40), (6, 65), (10, 85), (20, 100)]
    )

    total = (
        completeness * 0.30
        + authority * 0.25
        + freshness * 0.20
        + consistency * 0.15
        + peer_adequacy * 0.10
    )

    return {
        "score": round(total, 1),
        "components": [
            {"key": "completeness", "label": "Data completeness", "weight": 30, "score": round(completeness, 1)},
            {"key": "authority", "label": "Source authority", "weight": 25, "score": round(authority, 1)},
            {"key": "freshness", "label": "Data freshness", "weight": 20, "score": round(freshness, 1)},
            {"key": "consistency", "label": "Cross-source consistency", "weight": 15, "score": round(consistency, 1)},
            {"key": "peers", "label": "Peer-group adequacy", "weight": 10, "score": round(peer_adequacy, 1)},
        ],
    }
