"""Execute the day10 notebook headless and report health from day10_run_meta.json."""
import json
import logging
import subprocess
import sys

import config

log = logging.getLogger("pipeline")


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
        raise RuntimeError(f"Notebook execution failed:\n{proc.stderr[-2000:]}")

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
