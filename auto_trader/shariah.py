"""Approximate AAOIFI-style Shariah screen using free yfinance fundamentals.

Two layers:
  1. Business screen — industry/sector keyword exclusions.
  2. Financial ratios — interest-bearing debt and cash+interest-bearing
     securities each must be < 33% of market capitalisation.

LIMITATION: the non-compliant-income (<5% of revenue) test needs data that
free sources don't provide, so this is an approximation of the standard,
not a certified screening. Missing data => treated as NOT compliant
(conservative). For real-money decisions use a certified screener
(Zoya, Musaffa) or a certified universe (SPUS/HLAL holdings).
"""
import logging

import yfinance as yf

import config

log = logging.getLogger("shariah")

# Industry/sector substrings (lowercase) that fail the business screen.
HARAM_KEYWORDS = [
    "bank", "insurance", "capital markets", "credit services",
    "financial conglomerates", "mortgage", "asset management",
    "alcohol", "brewer", "distill", "winer",
    "tobacco", "gambling", "casino", "lotter",
    "aerospace & defense", "defense",
    "pork", "adult", "cannabis",
]

_cache: dict[str, tuple[bool, str]] = {}


def is_compliant(ticker: str) -> tuple[bool, str]:
    """Return (compliant, reason). Conservative on missing data."""
    if ticker in _cache:
        return _cache[ticker]
    result = _screen(ticker)
    _cache[ticker] = result
    return result


def _screen(ticker: str) -> tuple[bool, str]:
    try:
        info = yf.Ticker(ticker.replace(".", "-")).info or {}
    except Exception as e:
        return False, f"no data ({e.__class__.__name__})"

    sector = str(info.get("sector", "")).lower()
    industry = str(info.get("industry", "")).lower()
    if not sector and not industry:
        return False, "no sector/industry data"
    for kw in HARAM_KEYWORDS:
        if kw in industry or kw in sector:
            return False, f"business screen: {kw}"

    mcap = info.get("marketCap")
    if not mcap:
        return False, "no market cap data"

    debt = info.get("totalDebt")
    if debt is None:
        return False, "no debt data"
    if debt / mcap > config.SHARIAH_MAX_DEBT_RATIO:
        return False, f"debt {debt/mcap:.0%} of mcap (max {config.SHARIAH_MAX_DEBT_RATIO:.0%})"

    cash = info.get("totalCash")
    if cash is None:
        return False, "no cash data"
    if cash / mcap > config.SHARIAH_MAX_CASH_RATIO:
        return False, f"cash {cash/mcap:.0%} of mcap (max {config.SHARIAH_MAX_CASH_RATIO:.0%})"

    return True, "ok"
