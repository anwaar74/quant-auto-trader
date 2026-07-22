# Cloud Auto-Trader — GitHub Actions + Alpaca Paper

The same daily strategy as the laptop version, but running entirely in the cloud
at $0: GitHub Actions is the scheduler+computer, Alpaca provides the paper
trading account (plain REST API — no Gateway, no login sessions, no laptop).

```
GitHub Actions (cron, 17:00 MYT weekdays, free runner)
  ├─ 📥 yfinance → append new bars to raw_ohlcv.parquet (in-run copy)
  ├─ 🧠 execute py_study_day10.ipynb → signals_YYYYMMDD.csv
  ├─ 💼 Alpaca paper API: SELL 5-day-old lots, BUY top 3 ($1,000 each)
  ├─ 📲 Telegram: every step, trades, account equity
  └─ 💾 commit positions.json / trades_log / signals back to the repo (memory)
```

The parquet here is trimmed to 2008+ (pipeline only uses 2010+) to fit GitHub
comfortably; it is NOT committed back daily — each run re-fetches the gap since
this base from yfinance (fast, and picks up split adjustments for free).

## Setup (~15 minutes, all one-time)

### 1. Alpaca paper account
1. Sign up free at https://alpaca.markets (choose Trading API).
2. In the dashboard make sure you're on **Paper** (toggle top-left).
3. Generate API keys → copy **API Key ID** and **Secret Key**.

### 2. GitHub repo
1. Create a **private** repo, e.g. `quant-auto-trader`, at https://github.com/new
2. Push this folder to it:

   ```powershell
   cd "C:\Users\pc\Documents\Quant Series 2026\cloud_trader"
   git init -b main
   git add -A
   git commit -m "cloud auto-trader"
   git remote add origin https://github.com/<your-username>/quant-auto-trader.git
   git push -u origin main
   ```

   (Install git from https://git-scm.com if needed. The parquet is ~65 MB —
   under GitHub's 100 MB limit, first push takes a minute.)

### 3. Secrets
Repo → Settings → Secrets and variables → Actions → New repository secret, four times:

| Name | Value |
|---|---|
| `ALPACA_API_KEY` | from step 1 |
| `ALPACA_SECRET_KEY` | from step 1 |
| `TELEGRAM_TOKEN` | same bot token as the local setup |
| `TELEGRAM_CHAT_ID` | same chat id |

### 4. Test
Repo → Actions tab → `daily-paper-trade` → **Run workflow**. Watch the live log
and your Telegram. First run installs everything (~3 min) then runs the cycle.

### 5. Go live
Nothing else — the cron (`0 9 * * 1-5` UTC = 17:00 MYT weekdays) is already in
`.github/workflows/daily.yml`. Runs happen with your laptop off.

## Once it works

- **Disable the laptop task** so you don't run two parallel campaigns:
  `schtasks /Change /TN "QuantDailyPaperTrade" /DISABLE`
  (The IBKR paper book will wind down by itself if you let the local task run
  until its open lots exit — or just sell them manually in Gateway once.)
- Positions/trades history: visible as daily commits in the repo, plus Telegram.
- Watch the first few runs' timing in the Actions tab. Free tier = 2,000
  min/month for private repos; a ~20-min daily run ≈ 440 min/month. Comfortable.

## Notes & limits

- GitHub cron isn't to-the-second; runs start within ~15 min of 09:00 UTC.
  Anywhere before 13:30 UTC (US open) is fine — orders queue for the open.
- Alpaca paper starts with $100k fake cash; your ~$15k steady-state book fits.
- If a run fails you get ❌ in Telegram and the executed notebook is attached
  as an artifact in the Actions run for debugging.
- Campaign end (2026-09-19) works the same: buys stop, exits continue,
  🏁 message when flat — then disable the workflow (Actions → ⋯ → Disable).
