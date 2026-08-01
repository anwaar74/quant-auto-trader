"""One-off maintenance: flatten the paper book and reset the lot ledger.

Why this exists: the workflow's `git add` batched a pathspec that never existed
(`paper_log.csv`), which made git stage NOTHING on every run. `positions.json`
stayed at `[]`, so `run_exits` never had a lot to sell while `run_entries` kept
buying — the account accumulated positions the bot had no record of.

This script closes that gap by squaring the two sides:
  1. cancels open orders and closes every position at the broker
  2. rewrites positions.json to [] so the ledger agrees with the account

After it runs, the book is flat and in sync, and the normal daily cycle starts
a clean campaign the next trading day.

Paper-only by construction (`TradingClient(..., paper=True)`). Refuses to do
anything without an explicit --yes, so it can't fire by accident.

    python auto_trader/flatten.py            # dry run: shows what it WOULD close
    python auto_trader/flatten.py --yes      # actually close everything
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from alpaca.trading.client import TradingClient

import config
import notify

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("flatten")


def main() -> int:
    confirm = "--yes" in sys.argv
    if not config.ALPACA_API_KEY:
        log.error("ALPACA_API_KEY not set")
        return 1

    client = TradingClient(config.ALPACA_API_KEY, config.ALPACA_SECRET_KEY,
                           paper=True)          # paper endpoint, always
    acct = client.get_account()
    positions = client.get_all_positions()

    if not positions:
        log.info("Account is already flat.")
    else:
        log.info("Equity $%s | %d positions to close:",
                 f"{float(acct.equity):,.0f}", len(positions))
        for p in positions:
            log.info("  %-6s qty %-8s mkt $%-12s P&L $%s",
                     p.symbol, p.qty, f"{float(p.market_value):,.2f}",
                     f"{float(p.unrealized_pl):,.2f}")

    if not confirm:
        log.warning("DRY RUN — nothing was closed. Re-run with --yes to execute.")
        return 0

    closed = []
    if positions:
        # cancel_orders=True also clears any resting orders that would re-open risk
        client.close_all_positions(cancel_orders=True)
        closed = [p.symbol for p in positions]
        log.info("Submitted close orders for: %s", ", ".join(closed))
        log.info("Market may be shut — orders queue for the next open.")

    # Square the ledger with the broker regardless of how many were closed.
    config.POSITIONS_PATH.write_text(json.dumps([], indent=2))
    log.info("Reset %s to []", config.POSITIONS_PATH.name)

    notify.send(
        "🧹 <b>Book flattened</b>\n"
        f"• closed {len(closed)} position(s): {', '.join(closed) or 'none'}\n"
        f"• positions.json reset to []\n"
        "• next daily run starts a clean campaign"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
