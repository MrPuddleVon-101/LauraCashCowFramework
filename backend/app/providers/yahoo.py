"""Yahoo Finance, through yfinance, as a second opinion.

SEC EDGAR stays the primary source: it is the filing itself, it is tier 1, and
measured against it the engine's revenue, margins, earnings multiples and market
capitalisation already come out right. What Yahoo adds is three things EDGAR
cannot give on its own.

First, statements indexed by their actual period end date. EDGAR facts arrive as
a pile of values that have to be bucketed into fiscal years by hand, and that is
where the engine was mixing 2023 interest expense into a 2025 ratio. A frame with
real column dates makes a mismatch detectable instead of invisible.

Second, market data the filings do not contain: traded volume, the 52 week range,
beta, shares outstanding now rather than the weighted average over a past year.

Third, independent corroboration. Data confidence used to claim 100% cross-source
agreement whenever a quote and a price history were both present, even though both
came from the same provider and were never compared. Two genuinely different
sources can be compared, and this is the other one.

yfinance scrapes an undocumented endpoint. It breaks, it rate limits, and Yahoo's
own numbers carry errors. Nothing here is allowed to fail an evaluation: every
call returns None on trouble and the engine carries on with the filing.
"""

from __future__ import annotations

import json
import math
import time
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

warnings.filterwarnings("ignore", module="yfinance")

CACHE_DIR = Path(__file__).resolve().parents[2] / ".cache"
CACHE_DIR.mkdir(exist_ok=True)

MARKET_TTL = 60 * 30          # half an hour for quotes
FUNDAMENTAL_TTL = 60 * 60 * 24  # a day for statements

SOURCE_NAME = "Yahoo Finance, via yfinance"
SOURCE_URL = "https://finance.yahoo.com/quote/"
#: Yahoo aggregates filings rather than publishing them. PRD 11 puts that at
#: tier 2: useful, checkable, and never the thing a number rests on alone.
SOURCE_TIER = 2


def _cache(name: str, ttl: int) -> Any | None:
    p = CACHE_DIR / name
    if not p.exists() or (time.time() - p.stat().st_mtime) > ttl:
        return None
    try:
        return json.loads(p.read_text())
    except (ValueError, OSError):
        return None


def _write(name: str, payload: Any) -> None:
    p = CACHE_DIR / name
    tmp = p.with_suffix(p.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(payload, default=str))
        tmp.replace(p)  # atomic, so a concurrent reader never sees half a file
    except OSError:
        pass


def _num(v: Any) -> float | None:
    """Only a real, finite number survives. NaN is Yahoo's way of saying absent."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


@dataclass
class Period:
    """One reporting period, with the date it actually ended."""

    end: str
    values: dict[str, float] = field(default_factory=dict)

    @property
    def year(self) -> int:
        return int(self.end[:4])


@dataclass
class YahooFacts:
    ticker: str
    currency: str | None = None
    periods: list[Period] = field(default_factory=list)   # newest first
    market: dict[str, float | None] = field(default_factory=dict)
    ok: bool = False

    def latest(self, key: str) -> tuple[float | None, str | None]:
        """The most recent value of a line item, with the period it belongs to."""
        for p in self.periods:
            v = p.values.get(key)
            if v is not None:
                return v, p.end
        return None, None

    def at(self, key: str, end: str) -> float | None:
        """A line item for one specific period end, or nothing."""
        for p in self.periods:
            if p.end == end:
                return p.values.get(key)
        return None

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "currency": self.currency,
            "ok": self.ok,
            "periods": [{"end": p.end, "values": p.values} for p in self.periods],
            "market": self.market,
        }


# Yahoo's row labels mapped onto the names the engine already uses.
LINES = {
    "Total Revenue": "revenue",
    "Operating Income": "operating_income",
    "Net Income": "net_income",
    "EBITDA": "ebitda",
    "Interest Expense": "interest_expense",
    "Diluted EPS": "eps_diluted",
    "Gross Profit": "gross_profit",
    "Basic Average Shares": "shares_basic",
    "Diluted Average Shares": "shares_diluted",
}


def fetch(ticker: str) -> YahooFacts:
    """Everything Yahoo will tell us about one symbol. Never raises."""
    sym = ticker.strip().upper()
    cached = _cache(f"yf_{sym}.json", FUNDAMENTAL_TTL)
    if cached:
        out = YahooFacts(ticker=sym, currency=cached.get("currency"), ok=cached.get("ok", False),
                         market=cached.get("market") or {})
        out.periods = [Period(end=p["end"], values=p["values"]) for p in cached.get("periods", [])]
        return out

    out = YahooFacts(ticker=sym)
    try:
        import yfinance as yf

        t = yf.Ticker(sym)

        try:
            fi = t.fast_info
            out.currency = fi.get("currency")
            out.market = {
                "price": _num(fi.get("lastPrice")),
                "market_cap": _num(fi.get("marketCap")),
                "year_high": _num(fi.get("yearHigh")),
                "year_low": _num(fi.get("yearLow")),
                "volume_10d": _num(fi.get("tenDayAverageVolume")),
                "volume_3m": _num(fi.get("threeMonthAverageVolume")),
                "shares_out": _num(fi.get("shares")),
            }
        except Exception:
            out.market = {}

        inc = t.income_stmt
        if inc is not None and not inc.empty:
            for col in inc.columns:
                end = str(col)[:10]
                vals: dict[str, float] = {}
                for label, key in LINES.items():
                    if label in inc.index:
                        v = _num(inc.loc[label, col])
                        if v is not None:
                            vals[key] = v
                if vals:
                    out.periods.append(Period(end=end, values=vals))
            out.periods.sort(key=lambda p: p.end, reverse=True)
            out.ok = True
    except Exception:
        # A scraper that is down is not a reason to refuse an evaluation.
        out.ok = False

    _write(f"yf_{sym}.json", out.to_dict())
    return out


def market_only(ticker: str) -> dict[str, float | None]:
    """Just the traded figures, on a shorter leash than the statements."""
    sym = ticker.strip().upper()
    cached = _cache(f"yfm_{sym}.json", MARKET_TTL)
    if cached is not None:
        return cached
    data: dict[str, float | None] = {}
    try:
        import yfinance as yf

        fi = yf.Ticker(sym).fast_info
        data = {
            "price": _num(fi.get("lastPrice")),
            "market_cap": _num(fi.get("marketCap")),
            "year_high": _num(fi.get("yearHigh")),
            "year_low": _num(fi.get("yearLow")),
            "volume_10d": _num(fi.get("tenDayAverageVolume")),
            "volume_3m": _num(fi.get("threeMonthAverageVolume")),
            "shares_out": _num(fi.get("shares")),
        }
    except Exception:
        data = {}
    _write(f"yfm_{sym}.json", data)
    return data


def agreement(a: float | None, b: float | None, tolerance: float = 0.02) -> float | None:
    """How closely two independent readings of the same quantity agree, 0 to 1.

    Returns None when either side is absent, because not knowing is not the same
    as agreeing and must never be scored as though it were.
    """
    if a is None or b is None:
        return None
    if a == 0 and b == 0:
        return 1.0
    scale = max(abs(a), abs(b))
    if scale == 0:
        return 1.0
    diff = abs(a - b) / scale
    if diff <= tolerance:
        return 1.0
    # Full marks inside tolerance, nothing at ten times it, straight line between.
    return max(0.0, 1.0 - (diff - tolerance) / (tolerance * 9))
