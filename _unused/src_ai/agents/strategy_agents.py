"""Specialized strategy agents used by the MetaAgent combiner."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class BaseSignalAgent:
    """Base utility for agent score tracking."""

    name: str
    weight: float = 0.33
    performance_history: List[float] = field(default_factory=list)

    def update_performance(self, pnl: float) -> None:
        self.performance_history.append(float(pnl or 0.0))
        if len(self.performance_history) > 200:
            self.performance_history = self.performance_history[-200:]

    def rolling_score(self, window: int = 30) -> float:
        if not self.performance_history:
            return 0.0
        values = self.performance_history[-window:]
        arr = np.asarray(values, dtype=float)
        return float(np.mean(arr))


class TrendFollowingAgent(BaseSignalAgent):
    def __init__(self, config: Dict | None = None):
        cfg = config or {}
        super().__init__(name="trend", weight=float(cfg.get("initial_weight", 0.33) or 0.33))
        self.fast_period = max(4, int(cfg.get("fast_period", 20) or 20))
        self.slow_period = max(self.fast_period + 1, int(cfg.get("slow_period", 50) or 50))

    def generate_signal(self, data, regime: str) -> Tuple[int, float]:
        if data is None or len(data) < self.slow_period + 5:
            return 0, 0.0

        fast = data["close"].ewm(span=self.fast_period, adjust=False).mean()
        slow = data["close"].ewm(span=self.slow_period, adjust=False).mean()
        diff = float(fast.iloc[-1] - slow.iloc[-1])
        atr = float((data["high"] - data["low"]).tail(14).mean() or 0.0)
        if atr <= 0:
            atr = abs(float(data["close"].iloc[-1])) * 0.001

        ratio = abs(diff) / max(atr, 1e-8)
        confidence = min(1.0, ratio / 2.5)
        if regime == "ranging":
            confidence *= 0.65
        elif regime.startswith("trending"):
            confidence *= 1.15

        if diff > 0:
            return 1, float(max(0.0, min(confidence, 1.0)))
        if diff < 0:
            return -1, float(max(0.0, min(confidence, 1.0)))
        return 0, 0.0


class MeanReversionAgent(BaseSignalAgent):
    def __init__(self, config: Dict | None = None):
        cfg = config or {}
        super().__init__(name="mean_reversion", weight=float(cfg.get("initial_weight", 0.33) or 0.33))
        self.lookback = max(10, int(cfg.get("lookback", 20) or 20))

    def generate_signal(self, data, regime: str) -> Tuple[int, float]:
        if data is None or len(data) < self.lookback + 5:
            return 0, 0.0

        close = data["close"].astype(float)
        mean = float(close.tail(self.lookback).mean())
        std = float(close.tail(self.lookback).std(ddof=0) or 0.0)
        if std <= 0:
            return 0, 0.0

        zscore = (float(close.iloc[-1]) - mean) / std
        confidence = min(1.0, abs(zscore) / 2.5)

        if regime.startswith("trending"):
            confidence *= 0.7
        elif regime == "ranging":
            confidence *= 1.2

        if zscore > 1.2:
            return -1, float(max(0.0, min(confidence, 1.0)))
        if zscore < -1.2:
            return 1, float(max(0.0, min(confidence, 1.0)))
        return 0, 0.0


class VolatilityBreakoutAgent(BaseSignalAgent):
    def __init__(self, config: Dict | None = None):
        cfg = config or {}
        super().__init__(name="volatility_breakout", weight=float(cfg.get("initial_weight", 0.34) or 0.34))
        self.lookback = max(10, int(cfg.get("lookback", 30) or 30))
        self.spike_threshold = float(cfg.get("spike_detection_threshold", 2.5) or 2.5)

    def generate_signal(self, data, regime: str) -> Tuple[int, float]:
        if data is None or len(data) < self.lookback + 3:
            return 0, 0.0

        close = data["close"].astype(float)
        returns = close.pct_change().dropna()
        if len(returns) < self.lookback:
            return 0, 0.0

        recent = returns.tail(self.lookback)
        sigma = float(recent.std(ddof=0) or 0.0)
        if sigma <= 0:
            return 0, 0.0

        current = float(recent.iloc[-1])
        score = current / sigma
        confidence = min(1.0, abs(score) / max(self.spike_threshold, 1e-6))

        if regime == "spiking":
            confidence *= 1.2

        if score >= self.spike_threshold:
            return 1, float(max(0.0, min(confidence, 1.0)))
        if score <= -self.spike_threshold:
            return -1, float(max(0.0, min(confidence, 1.0)))
        return 0, 0.0
