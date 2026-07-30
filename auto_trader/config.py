"""Cloud auto-trader configuration. Secrets come from environment variables
(GitHub Actions secrets); everything else is a plain constant."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent   # repo root

# --- Identity (used in the cross-strategy comparison report) ---
STRATEGY = "stefan_jansen"
STRATEGY_LABEL = "Stefan Jansen (cross-sectional rank)"

# --- Campaign ---
CAMPAIGN_END = "2026-09-19"
TOP_N = 3
BUDGET_PER_NAME = 1000.0
HOLD_BDAYS = 5

# --- Data ---
PARQUET_PATH = BASE_DIR / "raw_ohlcv.parquet"
MARKET = "US"

# --- Pipeline ---
NOTEBOOK = BASE_DIR / "py_study_day10.ipynb"
EXECUTED_NOTEBOOK = Path(__file__).resolve().parent / "day10_last_run.ipynb"
META_PATH = BASE_DIR / "day10_run_meta.json"
NOTEBOOK_TIMEOUT_S = 3600

# --- Shariah screen (approximate AAOIFI ratios; see shariah.py) ---
SHARIAH_SCREEN = True
SHARIAH_MAX_DEBT_RATIO = 0.33
SHARIAH_MAX_CASH_RATIO = 0.33
SHARIAH_MAX_CANDIDATES = 15    # how deep down the ranking to search for TOP_N compliant names

# --- Alpaca (paper only — hardcoded, no live endpoint anywhere) ---
ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY", "")
MAX_ORDER_QTY = 200

# --- Telegram ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# --- State ---
STATE_DIR = Path(__file__).resolve().parent
POSITIONS_PATH = STATE_DIR / "positions.json"
TRADES_LOG = STATE_DIR / "trades_log.csv"
EQUITY_LOG = STATE_DIR / "equity_log.csv"      # daily account snapshot, for comparison
