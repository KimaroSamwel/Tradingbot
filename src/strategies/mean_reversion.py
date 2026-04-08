"""Standalone mean-reversion strategy with RSI + Bollinger filters."""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd


class MeanReversionStrategy:
    def __init__(self, config: Dict):
        cfg = config or {}
        self.rsi_period = int(cfg.get("rsi_period", 14) or 14)
        self.rsi_oversold = float(cfg.get("rsi_oversold", 30) or 30)
        self.rsi_overbought = float(cfg.get("rsi_overbought", 70) or 70)
        self.bb_period = int(cfg.get("bb_period", 20) or 20)
        self.bb_std = float(cfg.get("bb_std", 2.0) or 2.0)

    def _rsi(self, close: pd.Series) -> float:
        delta = close.diff()
        up = delta.clip(lower=0).rolling(self.rsi_period).mean()
        down = (-delta.clip(upper=0)).rolling(self.rsi_period).mean()
        rs = up / down.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        value = float(rsi.iloc[-1]) if len(rsi) else 50.0
        if not np.isfinite(value):
            return 50.0
        return value

    def analyze(self, df: pd.DataFrame) -> Optional[Dict]:
        if df is None or len(df) < max(60, self.bb_period + self.rsi_period + 5):
            return None

        close = df["close"].astype(float)
        ma = close.rolling(self.bb_period).mean()
        std = close.rolling(self.bb_period).std()
        upper = ma + (self.bb_std * std)
        lower = ma - (self.bb_std * std)

        current = float(close.iloc[-1])
        upper_last = float(upper.iloc[-1])
        lower_last = float(lower.iloc[-1])
        rsi = self._rsi(close)

        if current <= lower_last and rsi <= self.rsi_oversold:
            return {
                "direction": "LONG",
                "confidence": min(95.0, 60.0 + max(0.0, (self.rsi_oversold - rsi) * 1.2)),
                "entry": current,
                "stop_loss": current - (std.iloc[-1] * 1.5),
                "take_profit": float(ma.iloc[-1]),
            }

        if current >= upper_last and rsi >= self.rsi_overbought:
            return {
                "direction": "SHORT",
                "confidence": min(95.0, 60.0 + max(0.0, (rsi - self.rsi_overbought) * 1.2)),
                "entry": current,
                "stop_loss": current + (std.iloc[-1] * 1.5),
                "take_profit": float(ma.iloc[-1]),
            }

        return None
