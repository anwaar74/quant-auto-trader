"""Telegram notifications. Fails soft: a Telegram outage never kills the run.

Every message is prefixed with the strategy tag so the Stefan Jansen and de Prado
books are distinguishable in a shared chat.

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

DELIVERY — why there is a plain-text retry:
messages go out with `parse_mode=HTML` so 💼 headers can be bold. Telegram then
*rejects the whole message* with HTTP 400 if it contains anything that looks like
an unknown tag — and Python tracebacks are full of them (`<module>`, `<stdin>`,
`<ipython-input-3>`). That is exactly the content of an error alert, so without a
fallback the one message you most need to see is the one that silently vanishes.
Callers should wrap dynamic text in `esc()`; if something slips through anyway,
`send()` retries once as plain text rather than dropping the alert.
"""
import html
import logging
import re

import requests

import config

log = logging.getLogger("notify")

# urllib3 logs the full request URL at DEBUG. Never let that happen.
logging.getLogger("urllib3").setLevel(logging.WARNING)

PREFIX = "📈 <b>[Stefan Jansen]</b> "

_API = "https://api.telegram.org"
# Only OUR OWN formatting tags are stripped for the plain-text retry. Stripping
# every <...> would delete the `<module>` / `<stdin>` frames from a traceback —
# exactly the detail the alert exists to deliver.
_FMT_TAG = re.compile(r"</?(?:b|strong|i|em|u|s|code|pre|a)(?:\s[^>]*)?>", re.I)


def esc(s) -> str:
    """HTML-escape dynamic text (error messages, tracebacks, tickers) so Telegram
    renders it literally instead of rejecting the message."""
    return html.escape(str(s), quote=False)


def _redact(s: str) -> str:
    """Scrub the bot token out of any string before it reaches a log."""
    tok = config.TELEGRAM_TOKEN
    if tok and len(tok) > 8:
        s = s.replace(tok, "<redacted>")
    return s


def _post(text: str, parse_mode: str | None):
    payload = {"chat_id": config.TELEGRAM_CHAT_ID, "text": text[:4000],
               "disable_web_page_preview": True}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return requests.post(f"{_API}/bot{config.TELEGRAM_TOKEN}/sendMessage",
                         json=payload, timeout=15)


def send(text: str) -> None:
    """Send a message to the configured chat. HTML formatting allowed.

    Never raises, and never logs anything containing the bot token.
    """
    text = PREFIX + text
    if not config.TELEGRAM_TOKEN or "PASTE" in config.TELEGRAM_TOKEN:
        log.warning("Telegram not configured; message was:\n%s", text)
        return
    try:
        r = _post(text, "HTML")
    except Exception as e:
        # Deliberately NOT log.exception / str(e): both carry the tokenised URL.
        log.error("Telegram send failed (%s) — message not delivered",
                  type(e).__name__)
        return
    if r.ok:
        return

    body = _redact(r.text[:300])
    # 400 from a stray angle bracket: resend as plain text so the alert survives.
    if r.status_code == 400 and re.search(r"pars|entit|tag", body, re.I):
        plain = html.unescape(_FMT_TAG.sub("", text))
        try:
            r2 = _post(plain, None)
        except Exception as e:
            log.error("Telegram plain-text retry failed (%s)", type(e).__name__)
            return
        if r2.ok:
            log.warning("Telegram rejected HTML (%s) — delivered as plain text", body)
            return
        log.error("Telegram error %s on plain-text retry: %s",
                  r2.status_code, _redact(r2.text[:200]))
        return
    log.error("Telegram error %s: %s", r.status_code, body)
