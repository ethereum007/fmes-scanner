"""Telegram bot — formats the daily scan list and pushes to a chat."""

from __future__ import annotations

import asyncio
from typing import Iterable, Optional

import requests

from .config import CONFIG
from .detector import Setup


TG_API_BASE = "https://api.telegram.org/bot"


def _split_messages(text: str, max_len: int = 3900) -> list[str]:
    """Telegram caps messages at 4096 chars. Split on line breaks to stay safe."""
    if len(text) <= max_len:
        return [text]
    chunks = []
    current = []
    current_len = 0
    for line in text.split("\n"):
        if current_len + len(line) + 1 > max_len:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks


def format_setups(
    setups: list[Setup],
    failed_count: int = 0,
    universe_size: int = 0,
    timeframe: str = "Daily",
    win_rate_30d: Optional[dict] = None,
) -> str:
    """Build the Telegram message body."""
    from datetime import datetime

    now = datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip()
    header = f"📊 *FMES Daily Scan — {timeframe} — {now}*\n"
    header += f"_Scanned: {universe_size} symbols   |   Setups: {len(setups)}   |   Failed: {failed_count}_\n"

    # 30-day win rate stat
    if win_rate_30d and win_rate_30d.get("total_closed", 0) > 0:
        wr = win_rate_30d.get("win_rate_pct")
        wins = win_rate_30d.get("wins", 0)
        losses = win_rate_30d.get("losses", 0)
        exp_r = win_rate_30d.get("expectancy_r")
        header += (
            f"_30d perf: {wins}W / {losses}L = *{wr}%* win rate"
            f"   |   Expectancy: *{exp_r}R*/trade_\n"
        )

    if not setups:
        return header + "\n_No fresh setups today._"

    premium = [s for s in setups if s.premium]
    longs_live = [s for s in setups if s.direction == "long" and s.status == "live"]
    shorts_live = [s for s in setups if s.direction == "short" and s.status == "live"]
    longs_pending = [s for s in setups if s.direction == "long" and s.status == "pending"]
    shorts_pending = [s for s in setups if s.direction == "short" and s.status == "pending"]
    won = [s for s in setups if s.status == "won"]
    lost = [s for s in setups if s.status == "lost"]

    parts: list[str] = [header]

    def _fmt_row(s: Setup) -> str:
        sym = s.symbol.replace(".NS", "").replace("=X", "")
        arrow = "🟢" if s.direction == "long" else "🔴"
        prem = "⭐ " if s.premium else ""
        return (
            f"{arrow} {prem}*{sym}*  "
            f"Entry `{s.entry}` | SL `{s.sl}` | TP `{s.tp}` | "
            f"R:R `{s.rr}` | {s.bar_age}b ago"
        )

    if premium:
        parts.append("\n*⭐ PREMIUM (HTF + LQ+ aligned)*")
        for s in premium[:15]:
            parts.append(_fmt_row(s))

    if longs_live or shorts_live:
        parts.append("\n*🔵 LIVE (entry triggered, in trade)*")
        for s in longs_live[:8]:
            parts.append(_fmt_row(s))
        for s in shorts_live[:8]:
            parts.append(_fmt_row(s))

    if longs_pending or shorts_pending:
        parts.append("\n*⏳ PENDING (waiting for entry to fill)*")
        for s in longs_pending[:8]:
            parts.append(_fmt_row(s))
        for s in shorts_pending[:8]:
            parts.append(_fmt_row(s))

    if won:
        parts.append(f"\n_✅ Won (recent): {len(won)} setup(s) hit TP_")
    if lost:
        parts.append(f"_❌ Lost (recent): {len(lost)} setup(s) hit SL_")

    parts.append(
        "\n_Place limit orders at Entry. Risk 0.5–1% per trade. "
        "SL fixed, TP = 2.45R on Fib limit._"
    )
    return "\n".join(parts)


def send_telegram(message: str, token: str = "", chat_id: str = "") -> bool:
    """Send a message to Telegram. Returns True on success."""
    token = token or CONFIG.telegram_token
    chat_id = chat_id or CONFIG.telegram_chat_id

    if not token or not chat_id:
        print("[telegram] Missing TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID — skipping send.")
        return False

    url = f"{TG_API_BASE}{token}/sendMessage"
    ok_all = True
    for chunk in _split_messages(message):
        try:
            r = requests.post(
                url,
                json={
                    "chat_id": chat_id,
                    "text": chunk,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            if r.status_code != 200:
                print(f"[telegram] HTTP {r.status_code}: {r.text[:200]}")
                ok_all = False
        except Exception as e:
            print(f"[telegram] Send failed: {e}")
            ok_all = False
    return ok_all
