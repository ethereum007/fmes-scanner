# FMES Scanner

Python port of the [FMES Trade Setup Detector](https://github.com/ethereum007/fmes-trade-setup-detector) Pine indicator. Scans hundreds of stocks daily, detects fresh PSH/PSL setups using the FMES 5+1 criteria, persists to Supabase, pushes a clean actionable list to Telegram, and renders a live web dashboard.

## Phases

- **Phase 1**: Python scanner + Telegram bot (✅ live)
- **Phase 2**: Supabase persistence + 30-day win-rate tracking (✅ live)
- **Phase 3**: Next.js dashboard at fmes.alphabullacademy.com (✅ live — see [`dashboard/`](dashboard/))

## What it does

1. **Fetches OHLC** for all tickers in your configured universe (Nifty 500, forex majors, US large caps — fully configurable)
2. **Runs FMES detection** (M1–M5 + v4 quality filters) on each
3. **Filters** to fresh setups within the last N bars (default: 10)
4. **Posts to Telegram** a categorized list:
   - ⭐ Premium (HTF trend + LQ+ aligned)
   - 🔵 Live (entry triggered, in trade)
   - ⏳ Pending (waiting for entry to fill)
   - Recent winners / losers count
5. **Saves a JSON snapshot** of every run (for a future web dashboard)

## Quick start (local)

### 1. Install

```bash
git clone https://github.com/ethereum007/fmes-scanner.git
cd fmes-scanner
python -m venv .venv
source .venv/bin/activate         # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create a Telegram bot

1. DM [@BotFather](https://t.me/BotFather) on Telegram → `/newbot` → follow prompts → save the **bot token**
2. DM your new bot once (any message) to start a conversation
3. Get your **chat_id**: DM [@userinfobot](https://t.me/userinfobot) — it replies with your numeric ID

### 3. Configure

```bash
cp .env.example .env
# Edit .env, fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
```

### 4. Run

```bash
python main.py
```

You should see scanner output in the terminal AND a Telegram message arrive.

## Daily automation (GitHub Actions)

Already wired up via [`.github/workflows/daily-scan.yml`](.github/workflows/daily-scan.yml). Runs weekdays at **16:00 IST** (10:30 UTC), after NSE close.

To activate:

1. Push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions → New repository secret**
3. Add two secrets:
   - `TELEGRAM_BOT_TOKEN` (the token from BotFather)
   - `TELEGRAM_CHAT_ID` (your numeric chat ID)
4. Done. The cron job runs automatically every weekday.

To trigger a manual run: go to **Actions → Daily FMES Scan → Run workflow**.

## Configuration

All settings via environment variables (see [`.env.example`](.env.example)):

| Variable | Default | What it does |
|----------|---------|-------------|
| `FMES_TIMEFRAME` | `1d` | Scan timeframe. `1d`, `1h`, `15m`, etc. |
| `FMES_UNIVERSES` | `nifty500` | Comma list: `nifty50`, `nifty100`, `nifty500`, `fo`, `us_majors`, `forex` |
| `FMES_PIVOT_LEN` | `7` | Pivot lookback bars (matches Pine v4) |
| `FMES_SWEEP_WINDOW` | `20` | Max bars between sweep and opposing BOS |
| `FMES_REQUIRE_VOL_GAP` | `true` | Require volume gap on BOS bar |
| `FMES_REQUIRE_HTF_TREND` | `true` | HTF trend alignment filter (boosts win rate) |
| `FMES_REQUIRE_LQ_PLUS` | `true` | DT/TT confluence required (boosts conviction) |
| `FMES_MAX_SETUP_AGE_BARS` | `10` | Only report setups within this many bars |
| `YF_PERIOD` | `1y` | yfinance period to download |
| `YF_INTERVAL` | `1d` | yfinance interval (must match `FMES_TIMEFRAME`) |

## Project layout

```
fmes-scanner/
├── README.md
├── requirements.txt
├── .env.example
├── main.py                            # Entry point
├── fmes/
│   ├── config.py                      # Env var → settings
│   ├── universes.py                   # Nifty 500 + other ticker lists
│   ├── detector.py                    # Core FMES detection (port of Pine v4)
│   ├── scanner.py                     # Concurrent universe scan
│   ├── db.py                          # Supabase persistence
│   └── telegram_bot.py                # Message formatting + delivery
├── supabase/
│   └── schema.sql                     # DB schema (run once in Supabase)
├── dashboard/                         # Next.js 14 web dashboard
│   ├── app/                           #   App Router + RSC
│   ├── components/                    #   Setup table, stats header
│   └── lib/                           #   Supabase client, utils
└── .github/workflows/daily-scan.yml   # Daily cron (4pm IST weekdays)
```

## Supabase setup (Phase 2)

1. Create a project at https://supabase.com (free tier is plenty)
2. In **SQL Editor**, paste & run [`supabase/schema.sql`](supabase/schema.sql)
3. In **Settings → API**, grab:
   - `Project URL` → `SUPABASE_URL`
   - `service_role` key → `SUPABASE_SERVICE_KEY` (used by Python scanner — full write access)
   - `anon` key → `NEXT_PUBLIC_SUPABASE_ANON_KEY` (used by dashboard — read-only via RLS)
4. Add `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` to GitHub repo secrets (Settings → Secrets and variables → Actions)

After that, every scan persists to the `scans` and `setups` tables. The Telegram message gains a `30d perf: XW / YL = Z%` line.

## Dashboard setup (Phase 3)

See [`dashboard/README.md`](dashboard/README.md) for Vercel deploy + custom-domain instructions.

## Extending

### Add more stocks

Edit [`fmes/universes.py`](fmes/universes.py) — append tickers to `NIFTY_500_EXTRA`. For yfinance, NSE stocks need `.NS` suffix.

For the canonical Nifty 500 list, download the CSV from [niftyindices.com](https://www.niftyindices.com/indices/equity/broad-based-indices/nifty-500), append `.NS` to each ticker, and paste into `NIFTY_500_EXTRA`.

### Add a new universe

In `universes.py`, define a new tuple and register it in `UNIVERSES`:

```python
CRYPTO: tuple[str, ...] = ("BTC-USD", "ETH-USD", "SOL-USD")

UNIVERSES["crypto"] = CRYPTO
```

Then set `FMES_UNIVERSES=crypto` in your `.env`.

### Tune the strategy

All defaults match the Pine v4 indicator. Tweak via env vars or edit [`fmes/detector.py`](fmes/detector.py) directly.

## Strategy reference

This implements the FMES (Flipping Markets Entry System) by Marcell at Flipping Markets. The 5+1 criteria:

1. Break of Structure (BOS)
2. Liquidity Sweep
3. Volume Gap
4. Order Block
5. Fibonacci 0.71 entry
6. +1: LQ+ patterns (double/triple tops & bottoms)

See the sibling [fmes-trade-setup-detector](https://github.com/ethereum007/fmes-trade-setup-detector) repo for the Pine Script indicator with visual setups.

## License & disclaimer

Educational use only. Not financial advice. Trading carries risk; past setups don't guarantee future results.

Strategy design: Marcell / Flipping Markets. Code: this repo.
