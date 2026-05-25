"""Centralized config loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


@dataclass(frozen=True)
class FMESConfig:
    # Detection
    timeframe: str = os.getenv("FMES_TIMEFRAME", "1d")
    pivot_len: int = _env_int("FMES_PIVOT_LEN", 7)
    sweep_window: int = _env_int("FMES_SWEEP_WINDOW", 20)
    require_vol_gap: bool = _env_bool("FMES_REQUIRE_VOL_GAP", True)
    require_htf_trend: bool = _env_bool("FMES_REQUIRE_HTF_TREND", True)
    require_lq_plus: bool = _env_bool("FMES_REQUIRE_LQ_PLUS", True)
    htf_fast_ema: int = _env_int("FMES_HTF_FAST", 20)
    htf_slow_ema: int = _env_int("FMES_HTF_SLOW", 50)
    lq_tolerance_atr: float = _env_float("FMES_LQ_TOLERANCE_ATR", 0.3)
    lq_window_bars: int = _env_int("FMES_LQ_WINDOW", 40)
    hwr_target_rr: float = _env_float("FMES_HWR_RR", 2.0)

    # Output filter
    max_setup_age_bars: int = _env_int("FMES_MAX_SETUP_AGE_BARS", 10)
    history_bars: int = _env_int("FMES_HISTORY_BARS", 200)

    # Universe
    universes: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            u.strip() for u in os.getenv("FMES_UNIVERSES", "nifty500").split(",") if u.strip()
        )
    )

    # Telegram
    telegram_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Fetcher
    yfinance_period: str = os.getenv("YF_PERIOD", "1y")  # daily 1y default
    yfinance_interval: str = os.getenv("YF_INTERVAL", "1d")
    fetcher_max_workers: int = _env_int("FETCHER_MAX_WORKERS", 8)
    fetcher_rate_limit_seconds: float = _env_float("FETCHER_RATE_LIMIT_SECONDS", 0.1)


CONFIG = FMESConfig()
