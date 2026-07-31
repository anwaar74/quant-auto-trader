"""Execute the day10 notebook headless and report health from day10_run_meta.json."""
import json
import logging
import re
import subprocess
import sys

import config

log = logging.getLogger("pipeline")

# nbconvert colourises tracebacks. Those escape sequences render as literal
# "[32m[39m" noise in Telegram, which made the first real failure alert
# almost unreadable. Strip them before the text goes anywhere.
_ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")


def _clean(s: str) -> str:
    return _ANSI.sub("", s)


def _summarise_failure(stderr: str) -> str:
    """Pull the two useful facts out of nbconvert's noise: which cell died and
    what the exception was. Falls back to the tail if the format changes."""
    txt = _clean(stderr)
    parts = []

    # nbconvert prints: "An error occurred while executing the following cell:"
    # followed by the cell source between ------ rules.
    m = re.search(r"An error occurred while executing the following cell:\s*"
                  r"-+\n(.*?)\n-+\n", txt, re.S)
    if m:
        cell = m.group(1).strip().splitlines()
        head = "\n".join(cell[:12])
        if len(cell) > 12:
            head += f"\n… (+{len(cell) - 12} more lines)"
        parts.append("Failing cell:\n" + head)

    # last "SomeError: message" line is the actual exception
    errs = re.findall(r"^([A-Za-z_][\w.]*(?:Error|Exception|Interrupt)): (.+)$",
                      txt, re.M)
    if errs:
        name, msg = errs[-1]
        parts.append(f"{name}: {msg.strip()}")

    return "\n\n".join(parts) if parts else txt[-1500:]


def run() -> dict:
    """Run the notebook; return the parsed run meta. Raises on failure."""
    cmd = [
        sys.executable, "-m", "nbconvert",
        "--to", "notebook", "--execute",
        "--ExecutePreprocessor.timeout", str(config.NOTEBOOK_TIMEOUT_S),
        "--output", str(config.EXECUTED_NOTEBOOK),
        str(config.NOTEBOOK),
    ]
    log.info("Executing notebook (this can take a while)...")
    proc = subprocess.run(cmd, cwd=config.BASE_DIR, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("Notebook execution failed.\n\n"
                           + _summarise_failure(proc.stderr))

    with open(config.META_PATH) as fh:
        meta = json.load(fh)
    return meta


def health_summary(meta: dict) -> str:
    h = meta.get("health", {})
    return (
        f"asof {meta.get('asof')} | stale={meta.get('stale')} "
        f"(staleness {meta.get('staleness_days')}d)\n"
        f"variant={meta.get('variant')} | universe={meta.get('universe')} "
        f"| longs={meta.get('n_long')}\n"
        f"IC={h.get('daily_ic_mean', 0):.4f} (t={h.get('daily_ic_nw_t', 0):.2f}) "
        f"| net Sharpe={h.get('winner_net_sharpe', 0):.2f} "
        f"| checks {h.get('checks_passed')}/{h.get('checks_total')}"
    )
