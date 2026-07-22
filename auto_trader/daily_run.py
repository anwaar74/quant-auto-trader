"""Daily orchestrator: refresh data -> run day10 pipeline -> trade -> Telegram.

Scheduled via Windows Task Scheduler (see README). Safe to rerun; each step
reports to Telegram and any failure sends the error there too.
"""
import logging
import sys
import traceback
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import config
import data_refresh
import notify
import run_pipeline
import trader

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("daily")


def main() -> None:
    today = date.today()
    force = "--force" in sys.argv
    if today.weekday() >= 5 and not force:
        log.info("Weekend — nothing to do. (Use --force to test anyway.)")
        return

    campaign_over = today.isoformat() > config.CAMPAIGN_END
    notify.send(f"🤖 <b>Daily run {today}</b> started"
                + (" (campaign ended — exits only)" if campaign_over else ""))

    # 1. Data refresh
    try:
        msg = data_refresh.refresh()
        notify.send(f"📥 Data: {msg}")
    except Exception as e:
        notify.send(f"❌ Data refresh failed: {e}\nContinuing with existing data.")
        log.exception("refresh failed")

    # 2. Pipeline (skip if campaign over — no new signals needed)
    stale = True
    if not campaign_over:
        try:
            meta = run_pipeline.run()
            stale = bool(meta.get("stale", True))
            warns = meta.get("data_quality", {}).get("warnings", [])
            txt = "🧠 Pipeline done:\n" + run_pipeline.health_summary(meta)
            if warns:
                txt += "\n⚠️ " + "\n⚠️ ".join(warns[:3])
            notify.send(txt)
        except Exception as e:
            notify.send(f"❌ Pipeline failed: {e}")
            log.exception("pipeline failed")

    # 3. Trade
    try:
        client = trader.connect()
        exit_msgs = trader.run_exits(client)
        entry_msgs = trader.run_entries(client, allow_buys=not campaign_over and not stale)
        snap = trader.account_snapshot(client)
        lines = ["💼 <b>Trades</b>"]
        lines += [f"• {m}" for m in (exit_msgs or ["no exits due"])]
        lines += [f"• {m}" for m in entry_msgs]
        lines.append(f"📊 {snap}")
        notify.send("\n".join(lines))
    except Exception as e:
        notify.send(f"❌ Trading failed: {e}\n<pre>{traceback.format_exc()[-800:]}</pre>")
        log.exception("trading failed")
        return

    if campaign_over and not trader.load_positions():
        notify.send("🏁 Campaign complete and book is flat. "
                    "You can disable the scheduled task now.")

    notify.send(f"✅ Run {today} finished.")


if __name__ == "__main__":
    main()
