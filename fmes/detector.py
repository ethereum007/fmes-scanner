"""
FMES Detection Engine — Python port of the Pine v4 indicator.

Implements:
  M1: Pivots, body-close BOS, wick sweeps
  M2: Protected High / Low (sweep + opposing BOS + volume gap)
  M3: Fibonacci 0/0.71/1, Order Block, Entry/SL/TP
  M4: LQ+ patterns (double / triple tops & bottoms)
  M5: HWR dual-limit (OB entry at 1:2 R:R)
  V4: Quality filters — HTF trend alignment, LQ+ confluence required

Input: pandas DataFrame indexed by datetime with columns [open, high, low, close, volume]
Output: list[Setup] — fresh PSH/PSL signals detected within the lookback window
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import numpy as np
import pandas as pd


# ─── Data classes ────────────────────────────────────────────────────


@dataclass
class FMESParams:
    pivot_len: int = 7
    sweep_window: int = 20
    require_vol_gap: bool = True
    require_htf_trend: bool = True
    require_lq_plus: bool = True
    htf_fast_ema: int = 20
    htf_slow_ema: int = 50
    lq_tolerance_atr: float = 0.3
    lq_window_bars: int = 40
    hwr_target_rr: float = 2.0


@dataclass
class Setup:
    symbol: str
    direction: str  # "long" (PSL) or "short" (PSH)
    signal_bar: int
    signal_date: datetime
    bar_age: int  # bars from signal to last bar
    entry: float
    sl: float
    tp: float
    tp1: float  # -0.27 extension target
    ob_entry: float
    ob_tp: float  # 1:2 RR target from OB
    current_price: float
    status: str  # "pending", "live", "won", "lost"
    premium: bool  # True if all quality filters passed
    htf_trend: str  # "bull" | "bear" | "flat"
    has_lq_plus: bool
    risk_pct_to_sl: float  # how far is SL from entry, in %
    reward_pct_to_tp: float  # how far is TP from entry, in %
    rr: float  # risk:reward ratio

    def to_dict(self) -> dict:
        d = asdict(self)
        d["signal_date"] = self.signal_date.isoformat()
        return d


# ─── Helpers ─────────────────────────────────────────────────────────


def _pivots(series: pd.Series, window: int, mode: str = "high") -> dict[int, float]:
    """
    Return dict {bar_index: pivot_value} for confirmed pivots.

    A pivot at index i requires that series[i] is strictly the max (or min)
    within [i-window, i+window]. The pivot is confirmed only after `window` bars
    to the right have closed.
    """
    pivots: dict[int, float] = {}
    n = len(series)
    arr = series.values
    for i in range(window, n - window):
        center = arr[i]
        left = arr[i - window : i]
        right = arr[i + 1 : i + window + 1]
        if mode == "high":
            if center > left.max() and center > right.max():
                pivots[i] = float(center)
        else:
            if center < left.min() and center < right.min():
                pivots[i] = float(center)
    return pivots


def _atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    """Average True Range using exponential moving average (Wilder-ish)."""
    high = df["high"]
    low = df["low"]
    close = df["close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(span=length, adjust=False).mean()


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _resample_to_htf(df: pd.DataFrame, htf: str) -> pd.DataFrame:
    """Resample OHLC to a higher timeframe. htf examples: '1W' (weekly), '1M' (monthly)."""
    o = df["open"].resample(htf).first()
    h = df["high"].resample(htf).max()
    l = df["low"].resample(htf).min()
    c = df["close"].resample(htf).last()
    v = df["volume"].resample(htf).sum() if "volume" in df.columns else None
    out = pd.DataFrame({"open": o, "high": h, "low": l, "close": c})
    if v is not None:
        out["volume"] = v
    return out.dropna()


def _htf_label(timeframe: str) -> str:
    """
    Given the current timeframe label, pick a sensible HTF for trend filter.
    Mirrors the Pine v4 auto-select.
    """
    tf = timeframe.lower()
    if tf in {"1m", "2m", "5m", "15m"}:
        return "4h"
    if tf in {"30m", "1h", "60m"}:
        return "1d"
    if tf in {"4h", "240m"}:
        return "1d"
    if tf in {"1d", "d", "daily"}:
        return "1w"
    return "1m"  # weekly+ → monthly


def _htf_trend(df: pd.DataFrame, fast: int, slow: int, htf: str) -> str:
    """Resample to HTF, compute EMAs, return current bias: 'bull' | 'bear' | 'flat'."""
    # Map our htf labels to pandas frequency strings
    freq_map = {"4h": "4h", "1d": "1D", "1w": "1W", "1m": "1ME"}
    pandas_freq = freq_map.get(htf, "1W")
    try:
        htf_df = _resample_to_htf(df, pandas_freq)
        if len(htf_df) < slow + 2:
            return "flat"
        fast_e = _ema(htf_df["close"], fast).iloc[-1]
        slow_e = _ema(htf_df["close"], slow).iloc[-1]
        if pd.isna(fast_e) or pd.isna(slow_e):
            return "flat"
        if fast_e > slow_e:
            return "bull"
        if fast_e < slow_e:
            return "bear"
        return "flat"
    except Exception:
        return "flat"


# ─── Main detector ───────────────────────────────────────────────────


def detect_setups(
    df: pd.DataFrame,
    symbol: str,
    params: Optional[FMESParams] = None,
    max_setup_age_bars: int = 10,
) -> list[Setup]:
    """
    Run FMES detection on a price series.

    Args:
        df: DataFrame with columns [open, high, low, close, volume], datetime-indexed
        symbol: ticker (e.g. "RELIANCE.NS")
        params: FMESParams (defaults match the Pine v4 indicator)
        max_setup_age_bars: only return setups within this many bars of the last bar

    Returns:
        list[Setup] — fresh setups sorted by recency (most recent first)
    """
    if params is None:
        params = FMESParams()

    if df is None or len(df) < params.pivot_len * 4 + 20:
        return []

    # Normalize column names (yfinance returns capitalized)
    df = df.rename(
        columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        }
    ).copy()
    df = df.dropna(subset=["open", "high", "low", "close"])
    if len(df) < params.pivot_len * 4 + 20:
        return []

    # HTF trend bias (used for quality filter)
    timeframe_guess = "1d"  # caller can override via resample if needed; for our scanner we always use daily
    htf_label = _htf_label(timeframe_guess)
    htf_bias = _htf_trend(df, params.htf_fast_ema, params.htf_slow_ema, htf_label)

    # ATR for LQ tolerance
    atr_series = _atr(df, 14)

    # Pivot detection
    pivots_high = _pivots(df["high"], params.pivot_len, "high")
    pivots_low = _pivots(df["low"], params.pivot_len, "low")

    # State
    last_high: Optional[float] = None
    last_low: Optional[float] = None
    bos_fired_up = False
    bos_fired_dn = False
    pending_sweep_h: Optional[tuple[float, int]] = None  # (price, bar)
    pending_sweep_l: Optional[tuple[float, int]] = None
    wait_bear_bos = False
    wait_bull_bos = False

    # Recent pivot arrays for LQ+ confluence check
    recent_ph: list[tuple[float, int]] = []
    recent_pl: list[tuple[float, int]] = []

    setups: list[Setup] = []
    n = len(df)
    last_bar = n - 1
    last_price = float(df["close"].iloc[-1])

    highs = df["high"].values
    lows = df["low"].values
    opens = df["open"].values
    closes = df["close"].values
    dates = df.index

    def _has_lq_near(price: float, bar: int, recent: list[tuple[float, int]]) -> bool:
        if not params.require_lq_plus:
            return True
        if bar < 0 or bar >= len(atr_series):
            return False
        atr_val = atr_series.iloc[bar]
        if pd.isna(atr_val):
            return False
        tol = atr_val * params.lq_tolerance_atr
        for prior_price, prior_bar in recent:
            if abs(price - prior_price) <= tol and 3 <= (bar - prior_bar) <= params.lq_window_bars:
                return True
        return False

    for i in range(params.pivot_len, n):
        # Register pivot at i - pivot_len (confirmed pivot at center, looked back from i)
        # Actually our _pivots dict already returns the bar where the pivot OCCURRED.
        # We process at the bar where it becomes CONFIRMED (i = pivot_bar + pivot_len).
        confirm_bar = i - params.pivot_len
        if confirm_bar in pivots_high:
            last_high = pivots_high[confirm_bar]
            bos_fired_up = False
            recent_ph.append((last_high, confirm_bar))
            if len(recent_ph) > 30:
                recent_ph.pop(0)
        if confirm_bar in pivots_low:
            last_low = pivots_low[confirm_bar]
            bos_fired_dn = False
            recent_pl.append((last_low, confirm_bar))
            if len(recent_pl) > 30:
                recent_pl.pop(0)

        # Wick sweep
        if last_high is not None and highs[i] > last_high and closes[i] <= last_high:
            pending_sweep_h = (last_high, i)
            wait_bear_bos = True
        if last_low is not None and lows[i] < last_low and closes[i] >= last_low:
            pending_sweep_l = (last_low, i)
            wait_bull_bos = True

        # BOS (body close past last swing)
        bull_bos = last_high is not None and closes[i] > last_high and not bos_fired_up
        bear_bos = last_low is not None and closes[i] < last_low and not bos_fired_dn
        if bull_bos:
            bos_fired_up = True
        if bear_bos:
            bos_fired_dn = True

        # Volume gap geometry (3-bar pattern centered on current bar)
        if i >= 2:
            bull_gap = highs[i - 2] < lows[i]
            bear_gap = lows[i - 2] > highs[i]
        else:
            bull_gap = False
            bear_gap = False

        # Protected confirmation
        prot_high_ok = (
            wait_bear_bos
            and bear_bos
            and pending_sweep_h is not None
            and (i - pending_sweep_h[1]) <= params.sweep_window
            and (not params.require_vol_gap or bear_gap)
        )
        prot_low_ok = (
            wait_bull_bos
            and bull_bos
            and pending_sweep_l is not None
            and (i - pending_sweep_l[1]) <= params.sweep_window
            and (not params.require_vol_gap or bull_gap)
        )

        # Apply quality filters
        if prot_high_ok:
            sweep_h_price, sweep_h_bar = pending_sweep_h
            psh_trend_ok = (not params.require_htf_trend) or (htf_bias == "bear")
            psh_lq_ok = _has_lq_near(sweep_h_price, i, recent_ph)

            if psh_trend_ok and psh_lq_ok:
                # Compute setup levels
                sw_low = lows[i]
                rng = sweep_h_price - sw_low
                entry_px = sw_low + 0.71 * rng
                sl_px = sweep_h_price
                tp_px = sw_low
                tp1_px = sw_low - 0.27 * rng
                # Order block (body top of sweep bar)
                sweep_bar_ago = i - sweep_h_bar
                ob_bar = i - sweep_bar_ago
                ob_top = highs[ob_bar]
                ob_bot = max(opens[ob_bar], closes[ob_bar])
                ob_entry_px = ob_bot
                ob_risk = sl_px - ob_entry_px
                ob_tp_px = ob_entry_px - ob_risk * params.hwr_target_rr

                # Status — derive from price action AFTER signal
                status = _derive_status(
                    direction="short",
                    entry=entry_px,
                    sl=sl_px,
                    tp=tp_px,
                    bars_after_signal=closes[i + 1 :],
                    bars_after_high=highs[i + 1 :],
                    bars_after_low=lows[i + 1 :],
                    last_price=last_price,
                )

                premium = (
                    (not params.require_vol_gap or bear_gap)
                    and htf_bias == "bear"
                    and _has_lq_near(sweep_h_price, i, recent_ph)
                )

                bar_age = last_bar - i
                if bar_age <= max_setup_age_bars:
                    setups.append(
                        Setup(
                            symbol=symbol,
                            direction="short",
                            signal_bar=i,
                            signal_date=dates[i].to_pydatetime() if hasattr(dates[i], "to_pydatetime") else datetime.fromisoformat(str(dates[i])),
                            bar_age=bar_age,
                            entry=round(entry_px, 4),
                            sl=round(sl_px, 4),
                            tp=round(tp_px, 4),
                            tp1=round(tp1_px, 4),
                            ob_entry=round(ob_entry_px, 4),
                            ob_tp=round(ob_tp_px, 4),
                            current_price=round(last_price, 4),
                            status=status,
                            premium=premium,
                            htf_trend=htf_bias,
                            has_lq_plus=_has_lq_near(sweep_h_price, i, recent_ph),
                            risk_pct_to_sl=round(abs(sl_px - entry_px) / entry_px * 100, 2),
                            reward_pct_to_tp=round(abs(entry_px - tp_px) / entry_px * 100, 2),
                            rr=round(abs(entry_px - tp_px) / abs(sl_px - entry_px), 2) if sl_px != entry_px else 0.0,
                        )
                    )
            wait_bear_bos = False

        if prot_low_ok:
            sweep_l_price, sweep_l_bar = pending_sweep_l
            psl_trend_ok = (not params.require_htf_trend) or (htf_bias == "bull")
            psl_lq_ok = _has_lq_near(sweep_l_price, i, recent_pl)

            if psl_trend_ok and psl_lq_ok:
                sw_high = highs[i]
                rng = sw_high - sweep_l_price
                entry_px = sw_high - 0.71 * rng
                sl_px = sweep_l_price
                tp_px = sw_high
                tp1_px = sw_high + 0.27 * rng
                sweep_bar_ago = i - sweep_l_bar
                ob_bar = i - sweep_bar_ago
                ob_top = min(opens[ob_bar], closes[ob_bar])
                ob_bot = lows[ob_bar]
                ob_entry_px = ob_top
                ob_risk = ob_entry_px - sl_px
                ob_tp_px = ob_entry_px + ob_risk * params.hwr_target_rr

                status = _derive_status(
                    direction="long",
                    entry=entry_px,
                    sl=sl_px,
                    tp=tp_px,
                    bars_after_signal=closes[i + 1 :],
                    bars_after_high=highs[i + 1 :],
                    bars_after_low=lows[i + 1 :],
                    last_price=last_price,
                )

                premium = (
                    (not params.require_vol_gap or bull_gap)
                    and htf_bias == "bull"
                    and _has_lq_near(sweep_l_price, i, recent_pl)
                )

                bar_age = last_bar - i
                if bar_age <= max_setup_age_bars:
                    setups.append(
                        Setup(
                            symbol=symbol,
                            direction="long",
                            signal_bar=i,
                            signal_date=dates[i].to_pydatetime() if hasattr(dates[i], "to_pydatetime") else datetime.fromisoformat(str(dates[i])),
                            bar_age=bar_age,
                            entry=round(entry_px, 4),
                            sl=round(sl_px, 4),
                            tp=round(tp_px, 4),
                            tp1=round(tp1_px, 4),
                            ob_entry=round(ob_entry_px, 4),
                            ob_tp=round(ob_tp_px, 4),
                            current_price=round(last_price, 4),
                            status=status,
                            premium=premium,
                            htf_trend=htf_bias,
                            has_lq_plus=_has_lq_near(sweep_l_price, i, recent_pl),
                            risk_pct_to_sl=round(abs(entry_px - sl_px) / entry_px * 100, 2),
                            reward_pct_to_tp=round(abs(tp_px - entry_px) / entry_px * 100, 2),
                            rr=round(abs(tp_px - entry_px) / abs(entry_px - sl_px), 2) if sl_px != entry_px else 0.0,
                        )
                    )
            wait_bull_bos = False

        # Stale sweep cleanup
        if wait_bear_bos and pending_sweep_h is not None and (i - pending_sweep_h[1]) > params.sweep_window:
            wait_bear_bos = False
        if wait_bull_bos and pending_sweep_l is not None and (i - pending_sweep_l[1]) > params.sweep_window:
            wait_bull_bos = False

    # Return setups sorted by recency (most recent first)
    setups.sort(key=lambda s: s.signal_bar, reverse=True)
    return setups


def _derive_status(
    direction: str,
    entry: float,
    sl: float,
    tp: float,
    bars_after_signal: np.ndarray,
    bars_after_high: np.ndarray,
    bars_after_low: np.ndarray,
    last_price: float,
) -> str:
    """
    Walk through bars after the signal to determine current status:
      - pending: entry hasn't triggered yet
      - live:    entry triggered, neither TP nor SL hit
      - won:     TP hit (after entry triggered)
      - lost:    SL hit (after entry triggered)
    """
    if len(bars_after_signal) == 0:
        return "pending"

    triggered = False
    for j in range(len(bars_after_high)):
        h = bars_after_high[j]
        l = bars_after_low[j]
        if not triggered:
            if (direction == "long" and l <= entry) or (direction == "short" and h >= entry):
                triggered = True
                # On the SAME bar, check if SL or TP also hit (worst case: assume SL hit first)
                if (direction == "long" and l <= sl) or (direction == "short" and h >= sl):
                    return "lost"
                if (direction == "long" and h >= tp) or (direction == "short" and l <= tp):
                    return "won"
        else:
            if (direction == "long" and l <= sl) or (direction == "short" and h >= sl):
                return "lost"
            if (direction == "long" and h >= tp) or (direction == "short" and l <= tp):
                return "won"
    return "live" if triggered else "pending"
