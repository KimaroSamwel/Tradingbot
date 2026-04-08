"""
SYNTHETIC INDICES STRATEGIES COLLECTION
Specialized setup engine for Crash/Boom and Volatility indices.

Designed around two core behaviors frequently used by profitable synthetic bots:
1. Spike-event reversals (Crash/Boom asymmetry)
2. Regime-driven breakout/reversion selection (volatility expansion vs compression)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class SyntheticSignal:
    """Signal container for synthetic-indices strategies."""

    strategy: str
    direction: str  # LONG or SHORT
    symbol: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    timeframe: str = "M15"
    regime: str = "NORMAL"
    details: Dict = field(default_factory=dict)


class SyntheticStrategySelector:
    """Dedicated selector for synthetic index behavior."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}

        self.enabled = bool(cfg.get("enabled", True))
        self.min_confidence = float(cfg.get("min_confidence", 62.0))

        self.atr_period = int(cfg.get("atr_period", 14))
        self.breakout_lookback = int(cfg.get("breakout_lookback", 20))

        self.spike_atr_multiplier = float(cfg.get("spike_atr_multiplier", 2.2))
        self.wick_ratio_threshold = float(cfg.get("wick_ratio_threshold", 0.52))
        self.breakout_atr_multiplier = float(cfg.get("breakout_atr_multiplier", 1.15))

        self.rsi_period = int(cfg.get("rsi_period", 14))
        self.rsi_oversold = float(cfg.get("rsi_oversold", 28.0))
        self.rsi_overbought = float(cfg.get("rsi_overbought", 72.0))

    def get_all_signals(self, symbol: str, df: pd.DataFrame) -> List[SyntheticSignal]:
        """Run all synthetic-specific rules for one symbol."""
        if not self.enabled:
            return []
        if not self._is_synthetic_symbol(symbol):
            return []
        if df is None or len(df) < max(self.breakout_lookback + 5, 40):
            return []

        signals: List[Optional[SyntheticSignal]] = [
            self._spike_event_reversal(symbol, df),
            self._regime_breakout(symbol, df),
            self._compression_reversion(symbol, df),
        ]

        valid = [s for s in signals if s is not None and s.confidence >= self.min_confidence]
        valid.sort(key=lambda s: s.confidence, reverse=True)
        return valid

    def _is_synthetic_symbol(self, symbol: str) -> bool:
        upper = str(symbol or "").upper()
        return any(
            key in upper
            for key in ("CRASH", "BOOM", "VOLATILITY", "STEP INDEX", "RANGE BREAK", "JUMP INDEX")
        )

    def _is_crash_symbol(self, symbol: str) -> bool:
        return "CRASH" in str(symbol or "").upper()

    def _is_boom_symbol(self, symbol: str) -> bool:
        return "BOOM" in str(symbol or "").upper()

    def _is_volatility_symbol(self, symbol: str) -> bool:
        return "VOLATILITY" in str(symbol or "").upper()

    def _classify_regime(self, df: pd.DataFrame) -> str:
        atr = self._atr(df, self.atr_period)
        if atr <= 0:
            return "NORMAL"

        rolling_atr = self._rolling_atr(df, self.atr_period)
        baseline = float(rolling_atr.iloc[-30:].median()) if len(rolling_atr) >= 30 else float(rolling_atr.iloc[-1])
        if baseline <= 0:
            return "NORMAL"

        ratio = atr / baseline
        if ratio >= 1.35:
            return "EXPANSION"
        if ratio <= 0.80:
            return "COMPRESSION"
        return "NORMAL"

    def _spike_event_reversal(self, symbol: str, df: pd.DataFrame) -> Optional[SyntheticSignal]:
        """
        Crash/Boom spike-event reversal.

        - Crash indices: fast downside spike candle -> mean-reversion LONG setup
        - Boom indices: fast upside spike candle -> mean-reversion SHORT setup
        """
        if not (self._is_crash_symbol(symbol) or self._is_boom_symbol(symbol)):
            return None
        if len(df) < 40:
            return None

        last = df.iloc[-1]
        atr = self._atr(df, self.atr_period)
        if atr <= 0:
            return None

        high = float(last["high"])
        low = float(last["low"])
        open_ = float(last["open"])
        close = float(last["close"])

        candle_range = max(high - low, 1e-9)
        upper_wick = max(high - max(open_, close), 0.0)
        lower_wick = max(min(open_, close) - low, 0.0)
        range_in_atr = candle_range / atr

        if range_in_atr < self.spike_atr_multiplier:
            return None

        if self._is_crash_symbol(symbol):
            wick_ratio = lower_wick / candle_range
            if wick_ratio < self.wick_ratio_threshold:
                return None

            confidence = 68.0 + min((range_in_atr - self.spike_atr_multiplier) * 9.0, 20.0)
            entry = close
            stop = low - (atr * 0.25)
            target = entry + (atr * 2.3)

            if not (stop < entry < target):
                return None

            return SyntheticSignal(
                strategy="crash_spike_reversal",
                direction="LONG",
                symbol=symbol,
                entry_price=entry,
                stop_loss=stop,
                take_profit=target,
                confidence=min(confidence, 95.0),
                timeframe="M15",
                regime="EXPANSION",
                details={
                    "wick_ratio": round(wick_ratio, 4),
                    "range_in_atr": round(range_in_atr, 4),
                    "pattern": "downside_spike_absorption",
                },
            )

        wick_ratio = upper_wick / candle_range
        if wick_ratio < self.wick_ratio_threshold:
            return None

        confidence = 68.0 + min((range_in_atr - self.spike_atr_multiplier) * 9.0, 20.0)
        entry = close
        stop = high + (atr * 0.25)
        target = entry - (atr * 2.3)

        if not (target < entry < stop):
            return None

        return SyntheticSignal(
            strategy="boom_spike_reversal",
            direction="SHORT",
            symbol=symbol,
            entry_price=entry,
            stop_loss=stop,
            take_profit=target,
            confidence=min(confidence, 95.0),
            timeframe="M15",
            regime="EXPANSION",
            details={
                "wick_ratio": round(wick_ratio, 4),
                "range_in_atr": round(range_in_atr, 4),
                "pattern": "upside_spike_exhaustion",
            },
        )

    def _regime_breakout(self, symbol: str, df: pd.DataFrame) -> Optional[SyntheticSignal]:
        """
        Expansion-regime breakout for Volatility indices.

        This follows a common professional pattern used in modular frameworks:
        only chase breakouts when expansion regime is confirmed.
        """
        if not self._is_volatility_symbol(symbol):
            return None
        if len(df) < self.breakout_lookback + 5:
            return None

        regime = self._classify_regime(df)
        if regime != "EXPANSION":
            return None

        atr = self._atr(df, self.atr_period)
        rolling_atr = self._rolling_atr(df, self.atr_period)
        atr_baseline = float(rolling_atr.iloc[-30:].median()) if len(rolling_atr) >= 30 else float(rolling_atr.iloc[-1])
        if atr <= 0 or atr_baseline <= 0:
            return None

        current_close = float(df["close"].iloc[-1])
        upper = float(df["high"].iloc[-self.breakout_lookback - 1 : -1].max())
        lower = float(df["low"].iloc[-self.breakout_lookback - 1 : -1].min())

        if atr < atr_baseline * self.breakout_atr_multiplier:
            return None

        if current_close > upper:
            breakout_strength = (current_close - upper) / max(atr, 1e-9)
            confidence = 66.0 + min(breakout_strength * 25.0, 24.0)
            stop = current_close - (atr * 1.6)
            target = current_close + (atr * 2.8)
            if not (stop < current_close < target):
                return None

            return SyntheticSignal(
                strategy="volatility_expansion_breakout",
                direction="LONG",
                symbol=symbol,
                entry_price=current_close,
                stop_loss=stop,
                take_profit=target,
                confidence=min(confidence, 95.0),
                timeframe="M15",
                regime=regime,
                details={
                    "breakout_level": upper,
                    "breakout_strength_atr": round(breakout_strength, 4),
                },
            )

        if current_close < lower:
            breakout_strength = (lower - current_close) / max(atr, 1e-9)
            confidence = 66.0 + min(breakout_strength * 25.0, 24.0)
            stop = current_close + (atr * 1.6)
            target = current_close - (atr * 2.8)
            if not (target < current_close < stop):
                return None

            return SyntheticSignal(
                strategy="volatility_expansion_breakout",
                direction="SHORT",
                symbol=symbol,
                entry_price=current_close,
                stop_loss=stop,
                take_profit=target,
                confidence=min(confidence, 95.0),
                timeframe="M15",
                regime=regime,
                details={
                    "breakout_level": lower,
                    "breakout_strength_atr": round(breakout_strength, 4),
                },
            )

        return None

    def _compression_reversion(self, symbol: str, df: pd.DataFrame) -> Optional[SyntheticSignal]:
        """Compression-regime mean reversion around Bollinger extremes."""
        if len(df) < 50:
            return None

        regime = self._classify_regime(df)
        if regime != "COMPRESSION":
            return None

        atr = self._atr(df, self.atr_period)
        if atr <= 0:
            return None

        close = df["close"]
        mid = close.rolling(20).mean()
        std = close.rolling(20).std()
        if len(mid) < 25 or pd.isna(mid.iloc[-1]) or pd.isna(std.iloc[-1]):
            return None

        upper = float(mid.iloc[-1] + (2.0 * std.iloc[-1]))
        lower = float(mid.iloc[-1] - (2.0 * std.iloc[-1]))
        mid_price = float(mid.iloc[-1])
        price = float(close.iloc[-1])
        rsi = self._rsi(df, self.rsi_period)

        if price <= lower and rsi <= self.rsi_oversold:
            confidence = 63.0 + min((self.rsi_oversold - rsi) * 0.9, 18.0)
            stop = price - (atr * 1.2)
            target = max(mid_price, price + (atr * 1.8))
            if not (stop < price < target):
                return None

            return SyntheticSignal(
                strategy="synthetic_compression_reversion",
                direction="LONG",
                symbol=symbol,
                entry_price=price,
                stop_loss=stop,
                take_profit=target,
                confidence=min(confidence, 90.0),
                timeframe="M15",
                regime=regime,
                details={
                    "rsi": round(rsi, 2),
                    "band": "lower",
                },
            )

        if price >= upper and rsi >= self.rsi_overbought:
            confidence = 63.0 + min((rsi - self.rsi_overbought) * 0.9, 18.0)
            stop = price + (atr * 1.2)
            target = min(mid_price, price - (atr * 1.8))
            if not (target < price < stop):
                return None

            return SyntheticSignal(
                strategy="synthetic_compression_reversion",
                direction="SHORT",
                symbol=symbol,
                entry_price=price,
                stop_loss=stop,
                take_profit=target,
                confidence=min(confidence, 90.0),
                timeframe="M15",
                regime=regime,
                details={
                    "rsi": round(rsi, 2),
                    "band": "upper",
                },
            )

        return None

    def _rolling_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        return tr.rolling(window=period).mean().fillna(method="bfill")

    def _atr(self, df: pd.DataFrame, period: int = 14) -> float:
        atr_series = self._rolling_atr(df, period)
        atr = float(atr_series.iloc[-1]) if len(atr_series) > 0 else 0.0
        if np.isnan(atr) or atr <= 0:
            return 0.0
        return atr

    def _rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        close = df["close"]
        delta = close.diff()
        gains = delta.clip(lower=0).rolling(period).mean()
        losses = (-delta.clip(upper=0)).rolling(period).mean()

        if len(gains) == 0 or len(losses) == 0:
            return 50.0

        loss_value = float(losses.iloc[-1]) if not pd.isna(losses.iloc[-1]) else 0.0
        gain_value = float(gains.iloc[-1]) if not pd.isna(gains.iloc[-1]) else 0.0

        if loss_value <= 1e-10:
            return 100.0 if gain_value > 0 else 50.0

        rs = gain_value / loss_value
        return float(100.0 - (100.0 / (1.0 + rs)))
