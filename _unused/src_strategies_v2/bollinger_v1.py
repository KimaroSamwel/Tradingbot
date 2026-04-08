"""Bollinger-band percentile directional controller."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.strategies.v2.base_controller import ControllerSignal, DirectionalTradingController


class BollingerV1Controller(DirectionalTradingController):
    """Signal: BBP < long_threshold => long, BBP > short_threshold => short."""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        cfg = config or {}
        self.bb_length = int(cfg.get("bb_length", 100) or 100)
        self.bb_std = float(cfg.get("bb_std", 2.0) or 2.0)
        self.bb_long_threshold = float(cfg.get("bb_long_threshold", 0.3) or 0.3)
        self.bb_short_threshold = float(cfg.get("bb_short_threshold", 0.7) or 0.7)

    def calculate_signals(self, candles: pd.DataFrame) -> Dict:
        if candles is None or len(candles) < self.bb_length + 5:
            return {"signal": 0, "confidence": 0.0, "bbp": None}

        close = candles["close"].astype(float)
        ma = close.rolling(self.bb_length).mean()
        std = close.rolling(self.bb_length).std()
        upper = ma + (self.bb_std * std)
        lower = ma - (self.bb_std * std)

        denom = (upper - lower).replace(0, np.nan)
        bbp = (close - lower) / denom
        bbp_last = float(bbp.iloc[-1]) if np.isfinite(bbp.iloc[-1]) else 0.5

        if bbp_last < self.bb_long_threshold:
            signal = 1
            confidence = min(95.0, 60.0 + ((self.bb_long_threshold - bbp_last) * 100.0))
        elif bbp_last > self.bb_short_threshold:
            signal = -1
            confidence = min(95.0, 60.0 + ((bbp_last - self.bb_short_threshold) * 100.0))
        else:
            signal = 0
            confidence = 0.0

        return {
            "signal": int(signal),
            "confidence": float(max(0.0, confidence)),
            "bbp": float(bbp_last),
            "upper": float(upper.iloc[-1]),
            "lower": float(lower.iloc[-1]),
        }

    def get_processed_data(self, symbol: str, candles: pd.DataFrame) -> ControllerSignal:
        payload = self.calculate_signals(candles)
        return ControllerSignal(
            symbol=str(symbol),
            signal=int(payload["signal"]),
            confidence=float(payload["confidence"]),
            strategy="bollinger_v1",
            timestamp=datetime.now(),
            meta=payload,
        )
