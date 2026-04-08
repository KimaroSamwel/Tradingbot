"""Directional market-making (DMAN) controller placeholder."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import pandas as pd

from src.strategies.v2.base_controller import ControllerSignal, DirectionalTradingController


class DManV1Controller(DirectionalTradingController):
    """Directional mean-reverting controller placeholder for future extension."""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        cfg = config or {}
        self.lookback = int(cfg.get("lookback", 40) or 40)

    def get_processed_data(self, symbol: str, candles: pd.DataFrame) -> ControllerSignal:
        if candles is None or len(candles) < self.lookback + 5:
            return ControllerSignal(symbol=symbol, signal=0, confidence=0.0, strategy="dman_v1", timestamp=datetime.now(), meta={})

        close = candles["close"].astype(float)
        mean = close.tail(self.lookback).mean()
        std = close.tail(self.lookback).std()
        current = float(close.iloc[-1])

        if std <= 1e-10:
            return ControllerSignal(symbol=symbol, signal=0, confidence=0.0, strategy="dman_v1", timestamp=datetime.now(), meta={})

        z = (current - mean) / std
        if z <= -1.5:
            signal = 1
            confidence = min(90.0, 60.0 + abs(z) * 12.0)
        elif z >= 1.5:
            signal = -1
            confidence = min(90.0, 60.0 + abs(z) * 12.0)
        else:
            signal = 0
            confidence = 0.0

        return ControllerSignal(
            symbol=str(symbol),
            signal=int(signal),
            confidence=float(confidence),
            strategy="dman_v1",
            timestamp=datetime.now(),
            meta={"zscore": float(z), "mean": float(mean), "std": float(std)},
        )
