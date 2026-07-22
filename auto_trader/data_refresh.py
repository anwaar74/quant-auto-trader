"""Append missing daily bars to raw_ohlcv.parquet via yfinance (free, no key).

Fetches only active (non-delisted) tickers, in batches, from the day after the
parquet's last date. Maps Yahoo's Adj Close -> adjusted_close to match the
day9/day10 schema. Atomic write. Returns a summary string.

NOTES:
- Yahoo symbols use '-' where EODHD used '.' for share classes (BRK.B -> BRK-B);
  handled automatically.
- adjusted_close changes retroactively on splits/dividends. Append mode cannot
  see that — refresh recent history fully once in a while (see README).
"""
import logging
import os
from datetime import date, timedelta

import pandas as pd
import yfinance as yf

import config

log = logging.getLogger("refresh")
SCHEMA = ["date", "open", "high", "low", "close", "adjusted_close",
          "volume", "ticker", "market", "delisted"]
BATCH = 100


def _to_yahoo(t: str) -> str:
    return t.replace(".", "-")


def refresh() -> str:
    df = pd.read_parquet(config.PARQUET_PATH)
    us = df[df["market"] == config.MARKET]
    active = us.groupby("ticker")["delisted"].last()
    tickers = active[~active.astype(bool)].index.tolist()
    last_date = pd.Timestamp(us["date"].max()).date()
    start = last_date + timedelta(days=1)
    today = date.today()
    if start >= today:
        return f"Data already current (last date {last_date})."
    log.info("Fetching %d tickers from %s ...", len(tickers), start)

    yahoo_map = {_to_yahoo(t): t for t in tickers}
    new_rows = []
    ysyms = list(yahoo_map)
    for i in range(0, len(ysyms), BATCH):
        chunk = ysyms[i:i + BATCH]
        data = yf.download(chunk, start=start.isoformat(), end=today.isoformat(),
                           interval="1d", auto_adjust=False, actions=False,
                           group_by="ticker", threads=True, progress=False)
        if data.empty:
            continue
        for ysym in chunk:
            try:
                sub = data[ysym] if len(chunk) > 1 else data
            except KeyError:
                continue
            sub = sub.dropna(subset=["Close"])
            for dt, row in sub.iterrows():
                new_rows.append({
                    "date": pd.Timestamp(dt).normalize(),
                    "open": float(row["Open"]), "high": float(row["High"]),
                    "low": float(row["Low"]), "close": float(row["Close"]),
                    "adjusted_close": float(row["Adj Close"]),
                    "volume": float(row["Volume"]) if pd.notna(row["Volume"]) else 0.0,
                    "ticker": yahoo_map[ysym], "market": config.MARKET,
                    "delisted": False,
                })
        log.info("batch %d-%d done (%d rows so far)", i, i + len(chunk), len(new_rows))

    if not new_rows:
        return f"No new bars returned (last date {last_date}) — check yfinance."

    add = pd.DataFrame(new_rows)[SCHEMA]
    # keep only rows strictly after the stored last date, and drop the current
    # (possibly incomplete) session if the US market hasn't closed yet
    add = add[add["date"] > pd.Timestamp(last_date)]
    merged = pd.concat([df, add], ignore_index=True)
    merged = merged.drop_duplicates(subset=["ticker", "market", "date"], keep="last")
    tmp = config.PARQUET_PATH.with_suffix(".tmp.parquet")
    merged.to_parquet(tmp, index=False)
    os.replace(tmp, config.PARQUET_PATH)
    new_max = add["date"].max().date()
    return (f"Appended {len(add)} rows across {add['ticker'].nunique()} tickers "
            f"(now through {new_max}).")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(refresh())
