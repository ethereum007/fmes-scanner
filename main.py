"""
Entry point for the FMES scanner.

Run locally:
    python main.py

Or via cron / GitHub Actions:
    Set env vars in .env or the workflow YAML, then run the same command.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fmes.config import CONFIG
from fmes.scanner import scan_default
from fmes.telegram_bot import format_setups, send_telegram
from fmes.universes import resolve_universes


def main() -> int:
    print("=" * 70)
    print("FMES Scanner — daily run")
    print("=" * 70)
    print(f"Universes:    {', '.join(CONFIG.universes)}")
    print(f"Timeframe:    {CONFIG.yfinance_interval} (period={CONFIG.yfinance_period})")
    print(f"Pivot len:    {CONFIG.pivot_len}")
    print(f"Filters:      HTF trend={CONFIG.require_htf_trend}  LQ+={CONFIG.require_lq_plus}  VolGap={CONFIG.require_vol_gap}")
    print(f"Max age:      {CONFIG.max_setup_age_bars} bars")
    print("=" * 70)

    tickers = resolve_universes(CONFIG.universes)
    universe_size = len(tickers)
    print(f"\nResolved {universe_size} tickers across the universes.\n")

    setups, failed = scan_default()

    # Build Telegram message
    timeframe_label = {
        "1d": "Daily",
        "1h": "1 Hour",
        "15m": "15 Min",
        "5m": "5 Min",
        "4h": "4 Hour",
    }.get(CONFIG.yfinance_interval, CONFIG.yfinance_interval)

    message = format_setups(
        setups,
        failed_count=len(failed),
        universe_size=universe_size,
        timeframe=timeframe_label,
    )

    print("\n" + "─" * 70)
    print("Message preview:")
    print("─" * 70)
    print(message)
    print("─" * 70)

    # Save snapshot to disk (handy for the web dashboard later)
    out_dir = Path("data")
    out_dir.mkdir(exist_ok=True)
    snapshot_path = out_dir / "latest_scan.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "setups": [s.to_dict() for s in setups],
                "failed": failed,
                "universe_size": universe_size,
                "timeframe": CONFIG.yfinance_interval,
            },
            indent=2,
            default=str,
        )
    )
    print(f"\nSnapshot saved → {snapshot_path}")

    # Send Telegram
    sent = send_telegram(message)
    if sent:
        print("\n✓ Telegram message sent.")
    else:
        print("\n⚠ Telegram message not sent (missing token/chat_id or send failed).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
