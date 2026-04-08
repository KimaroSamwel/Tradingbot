"""MACD + Bollinger hybrid directional controller."""

from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

import numpy as np
import pandas as pd

from src.strategies.v2.base_controller import ControllerSignal, DirectionalTradingController


class MACDBBV1Controller(DirectionalTradingController):
    """MACD trend filter + Bollinger timing."""

    def __init__(self, config: Optional[Dict] = None):
        super().__init__(config)
        cfg = config or {}
        self.macd_fast = int(cfg.get("macd_fast", 21) or 21)
        self.macd_slow = int(cfg.get("macd_slow", 42) or 42)
        self.macd_signal = int(cfg.get("macd_signal", 9) or 9)
        self.bb_length = int(cfg.get("bb_length", 100) or 100)
        self.bb_std = float(cfg.get("bb_std", 2.0) or 2.0)
        self.bb_long_threshold = float(cfg.get("bb_long_threshold", 0.3) or 0.3)
        self.bb_short_threshold = float(cfg.get("bb_short_threshold", 0.7) or 0.7)

    def calculate_signals(self, candles: pd.DataFrame) -> Dict:
        if candles is None or len(candles) < max(self.bb_length + 5, self.macd_slow + self.macd_signal + 5):
            return {"signal": 0, "confidence": 0.0}

        close = candles["close"].astype(float)

        ema_fast = close.ewm(span=self.macd_fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.macd_slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        signal_line = macd.ewm(span=self.macd_signal, adjust=False).mean()
        macd_hist = macd - signal_line

        ma = close.rolling(self.bb_length).mean()
        std = close.rolling(self.bb_length).std()
        upper = ma + (self.bb_std * std)
        lower = ma - (self.bb_std * std)
        denom = (upper - lower).replace(0, np.nan)
        bbp = (close - lower) / denom

        macd_hist_last = float(macd_hist.iloc[-1])
        bbp_last = float(bbp.iloc[-1]) if np.isfinite(bbp.iloc[-1]) else 0.5

        signal = 0
        confidence = 0.0

        if macd_hist_last > 0 and bbp_last < self.bb_long_threshold:
            signal = 1
            confidence = 65.0 + min(25.0, abs(macd_hist_last) * 1000.0) + max(0.0, (self.bb_long_threshold - bbp_last) * 20.0)
        elif macd_hist_last < 0 and bbp_last > self.bb_short_threshold:
            signal = -1
            confidence = 65.0 + min(25.0, abs(macd_hist_last) * 1000.0) + max(0.0, (bbp_last - self.bb_short_threshold) * 20.0)

        return {
            "signal": int(signal),
            "confidence": float(max(0.0, min(confidence, 98.0))),
            "macd_hist": float(macd_hist_last),
            "bbp": float(bbp_last),
        }

    def get_processed_data(self, symbol: str, candles: pd.DataFrame) -> ControllerSignal:
        payload = self.calculate_signals(candles)
        return ControllerSignal(
            symbol=str(symbol),
            signal=int(payload["signal"]),
            confidence=float(payload["confidence"]),
            strategy="macd_bb_v1",
            timestamp=datetime.now(),
            meta=payload,
        )
