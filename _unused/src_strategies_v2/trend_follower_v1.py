"""Simple trend follower V1 controller."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import pandas as pd

from src.strategies.v2.base_controller import ControllerSignal, DirectionalTradingController


class TrendFollowerController(DirectionalTradingController):
    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        cfg = config or {}
        self.fast_period = int(cfg.get("fast_period", 20) or 20)
        self.slow_period = int(cfg.get("slow_period", 50) or 50)

    def get_processed_data(self, symbol: str, candles: pd.DataFrame) -> ControllerSignal:
        if candles is None or len(candles) < self.slow_period + 5:
            return ControllerSignal(symbol=symbol, signal=0, confidence=0.0, strategy="trend_follower_v1", timestamp=datetime.now(), meta={})

        close = candles["close"].astype(float)
        fast = close.ewm(span=self.fast_period, adjust=False).mean().iloc[-1]
        slow = close.ewm(span=self.slow_period, adjust=False).mean().iloc[-1]

        if fast > slow:
            signal = 1
            confidence = min(95.0, 60.0 + abs((fast - slow) / max(abs(slow), 1e-10)) * 1000.0)
        elif fast < slow:
            signal = -1
            confidence = min(95.0, 60.0 + abs((fast - slow) / max(abs(slow), 1e-10)) * 1000.0)
        else:
            signal = 0
            confidence = 0.0

        return ControllerSignal(
            symbol=str(symbol),
            signal=int(signal),
            confidence=float(confidence),
            strategy="trend_follower_v1",
            timestamp=datetime.now(),
            meta={"fast": float(fast), "slow": float(slow)},
        )
