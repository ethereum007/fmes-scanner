"""
Scanner orchestrator: fetch data for a universe, run detection, return setups.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pandas as pd
import yfinance as yf

from .config import CONFIG
from .detector import FMESParams, Setup, detect_setups
from .universes import resolve_universes


def fetch_ohlc(
    ticker: str,
    period: str = "1y",
    interval: str = "1d",
    timeout: int = 15,
) -> Optional[pd.DataFrame]:
    """Fetch OHLC for a single ticker from yfinance."""
    try:
        t = yf.Ticker(ticker)
        df = t.history(period=period, interval=interval, auto_adjust=True, timeout=timeout)
        if df is None or df.empty:
            return None
        # Normalize columns
        df = df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        return df
    except Exception as e:
        # Log silently; the scanner reports skipped tickers
        return None


def scan_universe(
    tickers: list[str],
    params: Optional[FMESParams] = None,
    period: Optional[str] = None,
    interval: Optional[str] = None,
    max_setup_age_bars: Optional[int] = None,
    max_workers: int = 8,
    rate_limit_seconds: float = 0.1,
    verbose: bool = True,
) -> tuple[list[Setup], list[str]]:
    """
    Run FMES detection across a list of tickers concurrently.

    Returns:
        (setups, failed_tickers)
    """
    if params is None:
        params = FMESParams(
            pivot_len=CONFIG.pivot_len,
            sweep_window=CONFIG.sweep_window,
            require_vol_gap=CONFIG.require_vol_gap,
            require_htf_trend=CONFIG.require_htf_trend,
            require_lq_plus=CONFIG.require_lq_plus,
            htf_fast_ema=CONFIG.htf_fast_ema,
            htf_slow_ema=CONFIG.htf_slow_ema,
            lq_tolerance_atr=CONFIG.lq_tolerance_atr,
            lq_window_bars=CONFIG.lq_window_bars,
            hwr_target_rr=CONFIG.hwr_target_rr,
        )
    period = period or CONFIG.yfinance_period
    interval = interval or CONFIG.yfinance_interval
    max_setup_age_bars = max_setup_age_bars if max_setup_age_bars is not None else CONFIG.max_setup_age_bars

    all_setups: list[Setup] = []
    failed: list[str] = []

    def _process(ticker: str) -> tuple[str, list[Setup], bool]:
        df = fetch_ohlc(ticker, period=period, interval=interval)
        if df is None or df.empty:
            return ticker, [], False
        try:
            setups = detect_setups(df, ticker, params=params, max_setup_age_bars=max_setup_age_bars)
            return ticker, setups, True
        except Exception:
            return ticker, [], False

    if verbose:
        print(f"[scanner] Scanning {len(tickers)} tickers (period={period}, interval={interval})...")

    completed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_process, t): t for t in tickers}
        for fut in as_completed(futures):
            ticker, setups, ok = fut.result()
            completed += 1
            if not ok:
                failed.append(ticker)
            else:
                all_setups.extend(setups)
            if verbose and completed % 25 == 0:
                print(f"[scanner]   {completed}/{len(tickers)} done — {len(all_setups)} setups so far")
            if rate_limit_seconds > 0:
                time.sleep(rate_limit_seconds)

    if verbose:
        print(f"[scanner] Done. {len(all_setups)} setups detected. {len(failed)} tickers failed.")

    # Sort: premium first, then by bar_age (freshest first)
    all_setups.sort(key=lambda s: (not s.premium, s.bar_age))
    return all_setups, failed


def scan_default() -> tuple[list[Setup], list[str]]:
    """Convenience: scan all universes specified in CONFIG.universes."""
    tickers = resolve_universes(CONFIG.universes)
    return scan_universe(
        tickers,
        period=CONFIG.yfinance_period,
        interval=CONFIG.yfinance_interval,
        max_workers=CONFIG.fetcher_max_workers,
        rate_limit_seconds=CONFIG.fetcher_rate_limit_seconds,
    )
