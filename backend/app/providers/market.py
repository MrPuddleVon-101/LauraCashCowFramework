"""Price and quote adapter.

PRD 58 asks for a provider interface rather than one hardcoded website, so the public
surface here is `get_history`, `get_quote` and `risk_profile`. Providers are tried in
order and the first that answers wins. If none answers, the caller gets None and the
scoring engine records the metric as missing rather than inventing a price.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Literal

import httpx

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)
HEADERS = {"User-Agent": BROWSER_UA, "Accept": "application/json"}

PRICE_TTL = 6 * 3600
QUOTE_TTL = 900

AssetClass = Literal["stocks", "etf"]

TRADING_DAYS = 252
BENCHMARK = "SPY"


# --- cache ------------------------------------------------------------------------

def _cache(name: str, ttl: int, build: Callable[[], Any]) -> Any | None:
    p = CACHE_DIR / name
    if p.exists() and time.time() - p.stat().st_mtime < ttl:
        try:
            return json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    value = build()
    if value is not None:
        try:
            p.write_text(json.dumps(value))
        except OSError:
            pass
    return value


def _money(raw: Any) -> float | None:
    if raw is None:
        return None
    s = str(raw).replace("$", "").replace(",", "").strip()
    if not s or s in ("N/A", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# --- providers --------------------------------------------------------------------

def _nasdaq_history(ticker: str, asset_class: AssetClass, years: int) -> list[dict] | None:
    end = date.today()
    start = end - timedelta(days=365 * years + 10)
    url = (
        f"https://api.nasdaq.com/api/quote/{ticker.upper()}/historical"
        f"?assetclass={asset_class}&fromdate={start:%Y-%m-%d}&todate={end:%Y-%m-%d}&limit=9999"
    )
    try:
        r = httpx.get(url, headers=HEADERS, timeout=30.0)
        if r.status_code != 200:
            return None
        payload = r.json().get("data") or {}
        rows = (payload.get("tradesTable") or {}).get("rows") or []
    except (httpx.HTTPError, json.JSONDecodeError, AttributeError):
        return None

    out: list[dict] = []
    for row in rows:
        close = _money(row.get("close"))
        if close is None:
            continue
        try:
            d = datetime.strptime(row["date"], "%m/%d/%Y").date()
        except (ValueError, KeyError):
            continue
        out.append({"date": d.isoformat(), "close": close})
    out.sort(key=lambda x: x["date"])
    return out or None


def _nasdaq_quote(ticker: str, asset_class: AssetClass) -> dict | None:
    url = f"https://api.nasdaq.com/api/quote/{ticker.upper()}/info?assetclass={asset_class}"
    try:
        r = httpx.get(url, headers=HEADERS, timeout=20.0)
        if r.status_code != 200:
            return None
        d = (r.json() or {}).get("data") or {}
    except (httpx.HTTPError, json.JSONDecodeError):
        return None
    if not d or not d.get("symbol"):
        return None
    primary = d.get("primaryData") or {}
    bid, ask = _money(primary.get("bidPrice")), _money(primary.get("askPrice"))
    is_live = bool(primary.get("isRealTime"))
    spread_bps = None
    spread_note = ""
    if bid and ask and ask > 0 and bid > 0 and ask >= bid:
        mid = (ask + bid) / 2
        if mid > 0:
            raw_bps = (ask - bid) / mid * 10_000
            # Outside regular trading hours the book is thin and the quoted spread is
            # not the spread Laura would actually pay. A displayed spread above 1% on a
            # listed fund is almost always a stale pre-market quote, so we decline to
            # score it rather than record a number we would not stand behind.
            if raw_bps <= 100 and is_live:
                spread_bps = raw_bps
            else:
                spread_note = (
                    "Quote taken outside continuous trading. The displayed spread of "
                    f"{raw_bps:.0f} bps reflects a thin book, not executable cost."
                    if raw_bps > 100
                    else "Quote is not flagged real time."
                )
    return {
        "symbol": d.get("symbol"),
        "name": d.get("companyName"),
        "exchange": d.get("exchange"),
        "stock_type": d.get("stockType"),
        "price": _money(primary.get("lastSalePrice")),
        "change_pct": primary.get("percentageChange"),
        "bid": bid,
        "ask": ask,
        "spread_bps": spread_bps,
        "spread_note": spread_note,
        "is_real_time": is_live,
        "as_of": primary.get("lastTradeTimestamp"),
        "source": "Nasdaq market data",
        "source_url": f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}",
    }


HISTORY_PROVIDERS: list[Callable[[str, AssetClass, int], list[dict] | None]] = [_nasdaq_history]
QUOTE_PROVIDERS: list[Callable[[str, AssetClass], dict | None]] = [_nasdaq_quote]


def get_history(ticker: str, asset_class: AssetClass = "stocks", years: int = 5) -> list[dict] | None:
    def build() -> list[dict] | None:
        for provider in HISTORY_PROVIDERS:
            rows = provider(ticker, asset_class, years)
            if rows:
                return rows
        # An equity ticker is sometimes classified as the other asset class upstream.
        other: AssetClass = "etf" if asset_class == "stocks" else "stocks"
        for provider in HISTORY_PROVIDERS:
            rows = provider(ticker, other, years)
            if rows:
                return rows
        return None

    return _cache(f"px_{ticker.upper()}_{asset_class}_{years}.json", PRICE_TTL, build)


def get_quote(ticker: str, asset_class: AssetClass = "stocks") -> dict | None:
    def build() -> dict | None:
        for provider in QUOTE_PROVIDERS:
            q = provider(ticker, asset_class)
            if q:
                return q
        other: AssetClass = "etf" if asset_class == "stocks" else "stocks"
        for provider in QUOTE_PROVIDERS:
            q = provider(ticker, other)
            if q:
                return q
        return None

    return _cache(f"q_{ticker.upper()}_{asset_class}.json", QUOTE_TTL, build)


# --- risk statistics --------------------------------------------------------------

def _returns(closes: list[float]) -> list[float]:
    out = []
    for a, b in zip(closes, closes[1:]):
        if a and a > 0:
            out.append(b / a - 1)
    return out


def _max_drawdown(closes: list[float]) -> float | None:
    if len(closes) < 2:
        return None
    peak = closes[0]
    worst = 0.0
    for c in closes:
        peak = max(peak, c)
        if peak > 0:
            worst = min(worst, c / peak - 1)
    return worst * 100


def _stdev(xs: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return math.sqrt(var)


def _align(a: list[dict], b: list[dict]) -> tuple[list[float], list[float]]:
    bi = {r["date"]: r["close"] for r in b}
    xs, ys = [], []
    for r in a:
        if r["date"] in bi:
            xs.append(r["close"])
            ys.append(bi[r["date"]])
    return xs, ys


@dataclass
class RiskProfile:
    max_drawdown_pct: float | None = None
    annual_volatility_pct: float | None = None
    beta: float | None = None
    downside_capture_pct: float | None = None
    momentum_12_1_pct: float | None = None
    total_return_pct: float | None = None
    cagr_pct: float | None = None
    years_covered: float = 0.0
    first_date: str | None = None
    last_date: str | None = None
    last_close: float | None = None
    sparkline: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "max_drawdown_pct": None if self.max_drawdown_pct is None else round(self.max_drawdown_pct, 2),
            "annual_volatility_pct": None if self.annual_volatility_pct is None else round(self.annual_volatility_pct, 2),
            "beta": None if self.beta is None else round(self.beta, 3),
            "downside_capture_pct": None if self.downside_capture_pct is None else round(self.downside_capture_pct, 1),
            "momentum_12_1_pct": None if self.momentum_12_1_pct is None else round(self.momentum_12_1_pct, 2),
            "price_return_pct": None if self.total_return_pct is None else round(self.total_return_pct, 2),
            "price_cagr_pct": None if self.cagr_pct is None else round(self.cagr_pct, 2),
            "return_basis": "Price only. Distributions are not reinvested, so income-heavy funds read low here.",
            "years_covered": round(self.years_covered, 2),
            "first_date": self.first_date,
            "last_date": self.last_date,
            "last_close": self.last_close,
            "sparkline": self.sparkline,
        }


def risk_profile(ticker: str, asset_class: AssetClass = "stocks", years: int = 5) -> RiskProfile | None:
    rows = get_history(ticker, asset_class, years)
    if not rows or len(rows) < 60:
        return None

    closes = [r["close"] for r in rows]
    rets = _returns(closes)
    sd = _stdev(rets)

    rp = RiskProfile(
        max_drawdown_pct=_max_drawdown(closes),
        annual_volatility_pct=None if sd is None else sd * math.sqrt(TRADING_DAYS) * 100,
        first_date=rows[0]["date"],
        last_date=rows[-1]["date"],
        last_close=closes[-1],
    )

    span_days = (datetime.fromisoformat(rows[-1]["date"]) - datetime.fromisoformat(rows[0]["date"])).days
    rp.years_covered = span_days / 365.25
    if closes[0] > 0:
        rp.total_return_pct = (closes[-1] / closes[0] - 1) * 100
        if rp.years_covered >= 1:
            rp.cagr_pct = ((closes[-1] / closes[0]) ** (1 / rp.years_covered) - 1) * 100

    # Twelve month momentum excluding the most recent month, a standard construction
    # that avoids the short-term reversal effect.
    if len(closes) > 273:
        past, recent = closes[-273], closes[-21]
        if past > 0:
            rp.momentum_12_1_pct = (recent / past - 1) * 100

    if ticker.upper() != BENCHMARK:
        bench = get_history(BENCHMARK, "etf", years)
        if bench:
            a, b = _align(rows, bench)
            if len(a) > 60:
                ra, rb = _returns(a), _returns(b)
                n = min(len(ra), len(rb))
                ra, rb = ra[:n], rb[:n]
                mb = sum(rb) / n
                ma = sum(ra) / n
                cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / (n - 1)
                varb = sum((y - mb) ** 2 for y in rb) / (n - 1)
                if varb > 0:
                    rp.beta = cov / varb
                down = [(x, y) for x, y in zip(ra, rb) if y < 0]
                if len(down) > 10:
                    sec = sum(x for x, _ in down)
                    mkt = sum(y for _, y in down)
                    if mkt != 0:
                        rp.downside_capture_pct = sec / mkt * 100

    step = max(1, len(closes) // 120)
    rp.sparkline = [round(c, 4) for c in closes[::step]][-120:]
    return rp


# --- reference data ---------------------------------------------------------------

def _num(raw: Any) -> float | None:
    """Parse the exchange's display strings: '$1,234.5', '0.15%', '5,638,195,000,000'."""
    if raw is None:
        return None
    s = str(raw).replace("$", "").replace(",", "").replace("%", "").strip()
    if not s or s in ("N/A", "--", "-"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def get_summary(ticker: str, asset_class: AssetClass = "stocks") -> dict | None:
    """Exchange reference data: market cap, sector, expense ratio, beta, 52 week range.

    This replaces two things the engine was previously deriving badly. Market
    capitalisation was being computed as price times the fiscal year's *weighted
    average* diluted share count, which overstates it for any company that has been
    buying stock back; the error reached 4.7% on JPMorgan. Fund assets and expense
    ratios were read from a hand-transcribed registry that had drifted, in one case
    by half. Both are reported directly here.
    """

    def build() -> dict | None:
        for ac in (asset_class, "etf" if asset_class == "stocks" else "stocks"):
            url = f"https://api.nasdaq.com/api/quote/{ticker.upper()}/summary?assetclass={ac}"
            try:
                r = httpx.get(url, headers=HEADERS, timeout=20.0)
                if r.status_code != 200:
                    continue
                d = (r.json() or {}).get("data") or {}
                sd = d.get("summaryData")
                if not sd:
                    continue
            except (httpx.HTTPError, json.JSONDecodeError):
                continue

            val = lambda k: (sd.get(k) or {}).get("value")
            hi = lo = None
            rng = val("FiftTwoWeekHighLow")
            if rng and "/" in str(rng):
                parts = str(rng).split("/")
                hi, lo = _num(parts[0]), _num(parts[1])

            return {
                "asset_class": ac,
                "market_cap": _num(val("MarketCap")),
                "sector": val("Sector"),
                "industry": val("Industry"),
                "exchange": val("Exchange"),
                "expense_ratio": _num(val("ExpenseRatio")),
                "beta": _num(val("Beta")),
                "dividend_yield_pct": _num(val("Yield")),
                "week52_high": hi,
                "week52_low": lo,
                "avg_volume": _num(val("AverageVolume")) or _num(val("AvgDailyVol65Days")),
                "previous_close": _num(val("PreviousClose")),
                "source": "Nasdaq reference data",
                "source_url": f"https://www.nasdaq.com/market-activity/stocks/{ticker.lower()}",
            }
        return None

    return _cache(f"sum_{ticker.upper()}_{asset_class}.json", QUOTE_TTL * 4, build)
