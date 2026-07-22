"""Telegram notifications. Fails soft: a Telegram outage never kills the run."""
import logging

import requests

import config

log = logging.getLogger("notify")


def send(text: str) -> None:
    """Send a message to the configured chat. HTML formatting allowed."""
    if "PASTE" in config.TELEGRAM_TOKEN:
        log.warning("Telegram not configured; message was:\n%s", text)
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text[:4000],
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15,
        )
        if not r.ok:
            log.error("Telegram error %s: %s", r.status_code, r.text[:200])
    except Exception:
        log.exception("Telegram send failed")
