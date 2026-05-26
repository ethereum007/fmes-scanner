"""
Supabase persistence layer.

Writes every scan run + detected setups to Postgres. Reads win-rate
aggregates for inclusion in the Telegram message.

Falls back silently if SUPABASE_URL or SUPABASE_SERVICE_KEY are missing —
the scanner still runs and posts to Telegram without persistence.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

from .detector import Setup

try:
    from supabase import create_client, Client  # type: ignore
    _SUPABASE_AVAILABLE = True
except ImportError:
    _SUPABASE_AVAILABLE = False
    Client = None  # type: ignore


def _get_client() -> Optional["Client"]:
    if not _SUPABASE_AVAILABLE:
        return None
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_KEY", "").strip()
    if not url or not key:
        return None
    try:
        return create_client(url, key)
    except Exception as e:
        print(f"[db] Failed to create Supabase client: {e}")
        return None


def insert_scan(
    universe_size: int,
    setups_found: int,
    failed_count: int,
    timeframe: str,
    universes: list[str],
    metadata: Optional[dict] = None,
) -> Optional[int]:
    """Insert a scan-run row. Returns the new scan_id or None if DB unavailable."""
    client = _get_client()
    if client is None:
        return None
    try:
        resp = (
            client.table("scans")
            .insert(
                {
                    "run_at": datetime.now(timezone.utc).isoformat(),
                    "universe_size": int(universe_size),
                    "setups_found": int(setups_found),
                    "failed_count": int(failed_count),
                    "timeframe": str(timeframe),
                    "universes": list(universes),
                    "metadata": metadata or {},
                }
            )
            .execute()
        )
        if resp.data:
            return int(resp.data[0]["id"])
        return None
    except Exception as e:
        print(f"[db] insert_scan failed: {e}")
        return None


def upsert_setups(setups: list[Setup], scan_id: Optional[int]) -> int:
    """
    Insert detected setups. On conflict (same symbol+direction+signal_date),
    update the row — this lets the scanner refresh status (pending → won/lost).
    Returns the number of rows written.
    """
    client = _get_client()
    if client is None or not setups:
        return 0

    payload = []
    for s in setups:
        payload.append(
            {
                "scan_id": scan_id,
                "symbol": s.symbol,
                "direction": s.direction,
                "signal_date": s.signal_date.isoformat() if hasattr(s.signal_date, "isoformat") else str(s.signal_date),
                "signal_bar": int(s.signal_bar),
                "bar_age": int(s.bar_age),
                "entry": float(s.entry),
                "sl": float(s.sl),
                "tp": float(s.tp),
                "tp1": float(s.tp1) if s.tp1 is not None else None,
                "ob_entry": float(s.ob_entry) if s.ob_entry is not None else None,
                "ob_tp": float(s.ob_tp) if s.ob_tp is not None else None,
                "current_price": float(s.current_price) if s.current_price is not None else None,
                "status": s.status,
                "premium": bool(s.premium),
                "htf_trend": s.htf_trend,
                "has_lq_plus": bool(s.has_lq_plus),
                "risk_pct": float(s.risk_pct_to_sl) if s.risk_pct_to_sl is not None else None,
                "reward_pct": float(s.reward_pct_to_tp) if s.reward_pct_to_tp is not None else None,
                "rr": float(s.rr) if s.rr is not None else None,
            }
        )

    try:
        resp = (
            client.table("setups")
            .upsert(payload, on_conflict="symbol,direction,signal_date")
            .execute()
        )
        return len(resp.data) if resp.data else 0
    except Exception as e:
        print(f"[db] upsert_setups failed: {e}")
        return 0


def get_win_rate_30d() -> Optional[dict]:
    """Read 30-day win-rate aggregates from the v_win_rate_30d view."""
    client = _get_client()
    if client is None:
        return None
    try:
        resp = client.table("v_win_rate_30d").select("*").execute()
        if resp.data and len(resp.data) > 0:
            return resp.data[0]
        return None
    except Exception as e:
        print(f"[db] get_win_rate_30d failed: {e}")
        return None
