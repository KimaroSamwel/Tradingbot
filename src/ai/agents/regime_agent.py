"""Regime detection agent for synthetic and FX markets."""

from __future__ import annotations

from typing import Dict, Tuple

import numpy as np


class RegimeAgent:
    """Classifies regime from volatility and trend context."""

    def __init__(self, config: Dict | None = None):
        cfg = config or {}
        self.lookback = max(20, int(cfg.get("lookback", 100) or 100))
        thresholds = cfg.get("volatility_thresholds", {}) if isinstance(cfg.get("volatility_thresholds", {}), dict) else {}
        self.low_vol_threshold = float(thresholds.get("low", 0.5) or 0.5)
        self.high_vol_threshold = float(thresholds.get("high", 2.0) or 2.0)

    def _atr(self, high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> float:
        if close.size < period + 1:
            return 0.0
        high_low = high - low
        high_close = np.abs(high - np.roll(close, 1))
        low_close = np.abs(low - np.roll(close, 1))
        tr = np.maximum(high_low, np.maximum(high_close, low_close))
        tr = tr[1:]
        return float(np.mean(tr[-period:])) if tr.size >= period else float(np.mean(tr))

    def detect_regime(self, symbol: str, data) -> Tuple[str, float]:
        """Return (regime, confidence)."""
        if data is None or len(data) < 30:
            return "ranging", 0.25

        close = np.asarray(data["close"].tail(self.lookback).values, dtype=float)
        high = np.asarray(data["high"].tail(self.lookback).values, dtype=float)
        low = np.asarray(data["low"].tail(self.lookback).values, dtype=float)
        if close.size < 30:
            return "ranging", 0.25

        atr_now = self._atr(high, low, close, period=14)
        atr_baseline = self._atr(high, low, close, period=min(28, max(15, close.size // 4)))
        if atr_baseline <= 0:
            atr_baseline = atr_now if atr_now > 0 else 1e-6
        atr_ratio = atr_now / max(atr_baseline, 1e-8)

        window = min(20, close.size)
        start = float(close[-window])
        end = float(close[-1])
        slope = (end - start) / max(window - 1, 1)
        drift = abs(end - start) / max(abs(start), 1e-8)

        # Spike-heavy synthetic symbols use larger ATR ratios.
        symbol_u = str(symbol or "").upper()
        spike_bias = 1.0
        if "CRASH" in symbol_u or "BOOM" in symbol_u:
            spike_bias = 0.9

        high_vol_threshold = self.high_vol_threshold * spike_bias

        if atr_ratio >= high_vol_threshold:
            confidence = min(0.95, 0.55 + (atr_ratio - high_vol_threshold) * 0.12)
            return "spiking", float(confidence)

        trend_threshold = 0.0006 if "INDEX" not in symbol_u else 0.0002
        if slope > trend_threshold:
            confidence = min(0.90, 0.50 + drift * 10.0)
            return "trending_up", float(confidence)
        if slope < -trend_threshold:
            confidence = min(0.90, 0.50 + drift * 10.0)
            return "trending_down", float(confidence)

        if atr_ratio <= self.low_vol_threshold:
            return "ranging", 0.75
        return "ranging", 0.55
