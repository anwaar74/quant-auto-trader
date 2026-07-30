"""Telegram notifications. Fails soft: a Telegram outage never kills the run.

SECURITY — why this module never logs an exception object or a traceback:
the bot token lives in the request *URL* (`/bot<TOKEN>/sendMessage`), which is how
the Telegram API is designed. requests/urllib3 put that URL into their exception
messages, so a plain `log.exception(...)` would write the token into the CI log.
GitHub does mask registered secrets in Actions output, but that is a safety net,
not a design. Here the token is never handed to the logger in the first place:

  * failures log only the exception *class name*, never str(e) and never a traceback
  * anything echoed back from the API is passed through `_redact()`
  * urllib3 is pinned to WARNING so its DEBUG request-line logging (which prints the
    full URL) can never be switched on by an ambient logging.basicConfig(DEBUG)
"""
import logging

import requests

import config

log = logging.getLogger("notify")

# urllib3 logs the full request URL at DEBUG. Never let that happen.
logging.getLogger("urllib3").setLevel(logging.WARNING)

_API = "https://api.telegram.org"


def _redact(s: str) -> str:
    """Scrub the bot token out of any string before it reaches a log."""
    tok = config.TELEGRAM_TOKEN
    if tok and len(tok) > 8:
        s = s.replace(tok, "<redacted>")
    return s


def send(text: str) -> None:
    """Send a message to the configured chat. HTML formatting allowed.

    Never raises, and never logs anything containing the bot token.
    """
    if not config.TELEGRAM_TOKEN or "PASTE" in config.TELEGRAM_TOKEN:
        log.warning("Telegram not configured; message was:\n%s", text)
        return
    try:
        r = requests.post(
            f"{_API}/bot{config.TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": config.TELEGRAM_CHAT_ID, "text": text[:4000],
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=15,
        )
    except Exception as e:
        # Deliberately NOT log.exception / str(e): both carry the tokenised URL.
        log.error("Telegram send failed (%s) — message not delivered",
                  type(e).__name__)
        return
    if not r.ok:
        log.error("Telegram error %s: %s", r.status_code, _redact(r.text[:200]))
