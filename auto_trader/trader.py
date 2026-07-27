"""Alpaca paper trading: sell lots past their 5-business-day hold, buy top N.

Same lot mechanics as the local IBKR version. Paper-only by construction:
TradingClient(paper=True) can only ever hit paper-api.alpaca.markets.
"""
import csv
import glob
import json
import logging
import re
from datetime import date

import pandas as pd
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

import config

log = logging.getLogger("trader")


# ---------------------------------------------------------------- state
def load_positions() -> list[dict]:
    if config.POSITIONS_PATH.exists():
        return json.loads(config.POSITIONS_PATH.read_text())
    return []


def save_positions(lots: list[dict]) -> None:
    config.POSITIONS_PATH.write_text(json.dumps(lots, indent=2))


def log_trade(row: dict) -> None:
    new = not config.TRADES_LOG.exists()
    with open(config.TRADES_LOG, "a", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["date", "action", "ticker", "qty",
                                           "order_id", "status", "note"])
        if new:
            w.writeheader()
        w.writerow(row)


# ---------------------------------------------------------------- signals
def latest_signals() -> tuple[pd.DataFrame, str]:
    files = sorted(glob.glob(str(config.BASE_DIR / "signals_*.csv")))
    if not files:
        raise SystemExit("No signals_*.csv found")
    fp = files[-1]
    asof = re.search(r"signals_(\d{8})\.csv$", fp).group(1)
    return pd.read_csv(fp), asof


# ---------------------------------------------------------------- broker
def connect() -> TradingClient:
    if not config.ALPACA_API_KEY:
        raise SystemExit("ALPACA_API_KEY not set")
    client = TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY,
                           paper=True)   # paper endpoint, always
    acct = client.get_account()
    log.info("Connected to Alpaca paper account %s (equity %s)",
             acct.account_number, acct.equity)
    return client


def _place(client: TradingClient, side: OrderSide, ticker: str, qty: int,
           note: str) -> dict:
    order = client.submit_order(MarketOrderRequest(
        symbol=ticker, qty=qty, side=side, time_in_force=TimeInForce.DAY))
    st = str(order.status.value if hasattr(order.status, "value") else order.status)
    log.info("%s %s x%d -> %s", side.value, ticker, qty, st)
    log_trade({"date": date.today().isoformat(), "action": side.value.upper(),
               "ticker": ticker, "qty": qty, "order_id": str(order.id),
               "status": st, "note": note})
    return {"ticker": ticker, "qty": qty, "status": st}


# ---------------------------------------------------------------- main flow
def run_exits(client: TradingClient) -> list[str]:
    today = date.today().isoformat()
    keep, msgs = [], []
    for lot in load_positions():
        if lot["exit_after"] <= today:
            try:
                r = _place(client, OrderSide.SELL, lot["ticker"], lot["qty"],
                           f"exit lot from {lot['entry_date']}")
                msgs.append(f"SELL {lot['ticker']} x{lot['qty']} ({r['status']})")
            except Exception as e:
                log.exception("Exit failed for %s", lot)
                msgs.append(f"SELL {lot['ticker']} FAILED: {e}")
                keep.append(lot)
        else:
            keep.append(lot)
    save_positions(keep)
    return msgs


def run_entries(client: TradingClient, allow_buys: bool) -> list[str]:
    if not allow_buys:
        return ["Buys skipped (campaign ended or signals stale)."]
    sig, asof = latest_signals()
    lots = load_positions()
    entry = date.today()
    if any(l["entry_date"] == entry.isoformat() for l in lots):
        return ["Buys skipped (today's tranche already placed)."]

    # Walk down the ranking, keeping the first TOP_N Shariah-compliant names.
    candidates = sig.sort_values("rank").head(
        config.SHARIAH_MAX_CANDIDATES if config.SHARIAH_SCREEN else config.TOP_N)
    picked, screen_msgs = [], []
    if config.SHARIAH_SCREEN:
        import shariah
        for _, row in candidates.iterrows():
            if len(picked) >= config.TOP_N:
                break
            ok, reason = shariah.is_compliant(row["ticker"])
            if ok:
                picked.append(row)
            else:
                screen_msgs.append(f"⛔ {row['ticker']} (rank {int(row['rank'])}): {reason}")
        if len(picked) < config.TOP_N:
            screen_msgs.append(
                f"only {len(picked)}/{config.TOP_N} compliant names in top "
                f"{config.SHARIAH_MAX_CANDIDATES}")
        checked = len(picked) + sum(1 for m in screen_msgs if m.startswith("⛔"))
        screen_msgs.insert(0, f"☪️ Shariah screen: {checked} checked, "
                              f"{len(picked)} passed, "
                              f"{checked - len(picked)} rejected")
    else:
        picked = [row for _, row in candidates.iterrows()]
    top = pd.DataFrame(picked)
    exit_after = pd.bdate_range(entry, periods=config.HOLD_BDAYS + 1)[-1].date()
    msgs = list(screen_msgs)
    for _, row in top.iterrows():
        px = float(row["last_adj_close"])
        qty = min(int(config.BUDGET_PER_NAME // px), config.MAX_ORDER_QTY)
        if qty < 1:
            msgs.append(f"skip {row['ticker']}: price {px:.2f} > budget")
            continue
        try:
            r = _place(client, OrderSide.BUY, row["ticker"], qty,
                       f"top{config.TOP_N} asof {asof}")
            lots.append({"ticker": row["ticker"], "qty": qty,
                         "entry_date": entry.isoformat(),
                         "exit_after": exit_after.isoformat()})
            msgs.append(f"BUY {row['ticker']} x{qty} @~{px:.2f} "
                        f"rank {int(row['rank'])} ({r['status']})")
        except Exception as e:
            log.exception("Entry failed for %s", row["ticker"])
            msgs.append(f"BUY {row['ticker']} FAILED: {e}")
    save_positions(lots)
    return msgs


def account_snapshot(client: TradingClient) -> str:
    try:
        acct = client.get_account()
        pos = client.get_all_positions()
        pos_str = ", ".join(f"{p.symbol}:{p.qty}" for p in pos) or "flat"
        return f"Equity ${float(acct.equity):,.0f} | positions: {pos_str}"
    except Exception:
        return "account snapshot unavailable"
