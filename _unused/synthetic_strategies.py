"""Dedicated synthetic asset strategy pack for Crash/Boom and Volatility indices."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


class StrategyBase:
    """Minimal strategy base class used by synthetic strategy implementations."""

    def __init__(self, config: Optional[Dict] = None, symbol_data_provider=None):
        self.config = config or {}
        self.symbol_data_provider = symbol_data_provider


@dataclass
class SyntheticSignal:
    strategy: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    timeframe: str = "M15"
    regime: str = "UNKNOWN"
    details: Optional[Dict] = None


class SyntheticStrategyBase(StrategyBase):
    def __init__(self, config: Optional[Dict] = None, symbol_data_provider=None):
        super().__init__(config=config, symbol_data_provider=symbol_data_provider)
        cfg = config or {}
        self.spike_threshold = float(cfg.get("spike_threshold", 2.5) or 2.5)
        self.regime_window = int(cfg.get("regime_window", 100) or 100)

    def _atr(self, df: pd.DataFrame, period: int = 14) -> float:
        if df is None or len(df) < period + 2:
            return 0.0
        hl = df["high"] - df["low"]
        hc = (df["high"] - df["close"].shift(1)).abs()
        lc = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        return float(atr) if np.isfinite(atr) else 0.0

    def _rsi(self, series: pd.Series, period: int = 14) -> float:
        if series is None or len(series) < period + 2:
            return 50.0
        delta = series.diff()
        up = delta.clip(lower=0).rolling(period).mean()
        down = (-delta.clip(upper=0)).rolling(period).mean()
        rs = up / down.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        value = float(rsi.iloc[-1]) if len(rsi) else 50.0
        if not np.isfinite(value):
            return 50.0
        return max(0.0, min(value, 100.0))

    def detect_spike_regime(self, symbol: str, timeframe: str, data: pd.DataFrame) -> Dict:
        """Detect high-volatility spike conditions using rolling return z-score."""
        if data is None or len(data) < max(30, self.regime_window // 3):
            return {"is_spike": False, "zscore": 0.0, "timeframe": timeframe, "symbol": symbol}

        returns = data["close"].pct_change().dropna()
        if len(returns) < 20:
            return {"is_spike": False, "zscore": 0.0, "timeframe": timeframe, "symbol": symbol}

        recent = returns.iloc[-1]
        window = returns.tail(min(len(returns), self.regime_window))
        std = float(window.std()) if np.isfinite(window.std()) else 0.0
        mean = float(window.mean()) if np.isfinite(window.mean()) else 0.0
        zscore = 0.0 if std <= 1e-10 else (float(recent) - mean) / std

        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "is_spike": abs(zscore) >= self.spike_threshold,
            "zscore": float(zscore),
            "return": float(recent),
        }

    def analyze_regime_shift(self, symbol: str, data: pd.DataFrame) -> Dict:
        """Identify calm <-> volatile regime shifts via ATR ratio."""
        if data is None or len(data) < max(60, self.regime_window):
            return {"symbol": symbol, "regime": "UNKNOWN", "vol_ratio": 1.0}

        fast = self._atr(data.tail(40), 10)
        slow = self._atr(data.tail(min(len(data), self.regime_window)), 28)
        vol_ratio = (fast / slow) if slow > 1e-10 else 1.0

        if vol_ratio >= 1.30:
            regime = "VOLATILE"
        elif vol_ratio <= 0.80:
            regime = "CALM"
        else:
            regime = "NORMAL"

        return {"symbol": symbol, "regime": regime, "vol_ratio": float(vol_ratio)}


class CrashSpikeStrategy(SyntheticStrategyBase):
    """Long on Crash indices after deep downside spikes."""

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Optional[SyntheticSignal]:
        if "CRASH" not in str(symbol).upper() or df is None or len(df) < 60:
            return None

        spike = self.detect_spike_regime(symbol, "M15", df)
        if not spike.get("is_spike"):
            return None

        if float(spike.get("zscore", 0.0)) > -self.spike_threshold:
            return None

        close = float(df["close"].iloc[-1])
        atr = self._atr(df, 14)
        if atr <= 0:
            return None

        rsi = self._rsi(df["close"], 14)
        confidence = min(95.0, 65.0 + max(0.0, abs(float(spike["zscore"])) - self.spike_threshold) * 8.0)
        confidence += max(0.0, (35.0 - rsi) * 0.4)

        return SyntheticSignal(
            strategy="crash_spike_reversal",
            direction="LONG",
            entry_price=close,
            stop_loss=close - (atr * 1.6),
            take_profit=close + (atr * 2.8),
            confidence=max(55.0, min(confidence, 97.0)),
            regime="SPIKE_DOWN",
            details={"zscore": float(spike["zscore"]), "rsi": float(rsi)},
        )


class BoomMomentumStrategy(SyntheticStrategyBase):
    """Trend-following on Boom indices."""

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Optional[SyntheticSignal]:
        if "BOOM" not in str(symbol).upper() or df is None or len(df) < 80:
            return None

        close = float(df["close"].iloc[-1])
        ema_fast = float(df["close"].ewm(span=20, adjust=False).mean().iloc[-1])
        ema_slow = float(df["close"].ewm(span=50, adjust=False).mean().iloc[-1])
        recent_high = float(df["high"].tail(20).max())
        atr = self._atr(df, 14)
        if atr <= 0:
            return None

        if not (ema_fast > ema_slow and close >= recent_high - (atr * 0.3)):
            return None

        confidence = 68.0 + min(20.0, ((ema_fast - ema_slow) / max(atr, 1e-10)) * 4.0)
        return SyntheticSignal(
            strategy="boom_momentum_breakout",
            direction="LONG",
            entry_price=close,
            stop_loss=close - (atr * 1.7),
            take_profit=close + (atr * 3.2),
            confidence=max(55.0, min(confidence, 96.0)),
            regime="TREND_UP",
            details={"ema_fast": ema_fast, "ema_slow": ema_slow},
        )


class VolatilityMeanReversionStrategy(SyntheticStrategyBase):
    """Range/mean-reversion for Volatility indices."""

    def generate_signal(self, symbol: str, df: pd.DataFrame) -> Optional[SyntheticSignal]:
        if "VOLATILITY" not in str(symbol).upper() or df is None or len(df) < 80:
            return None

        close_series = df["close"]
        close = float(close_series.iloc[-1])
        mean = float(close_series.rolling(30).mean().iloc[-1])
        std = float(close_series.rolling(30).std().iloc[-1])
        atr = self._atr(df, 14)
        if atr <= 0 or not np.isfinite(std) or std <= 1e-10:
            return None

        z = (close - mean) / std
        regime = self.analyze_regime_shift(symbol, df)
        if regime.get("regime") == "VOLATILE":
            return None

        if z >= 1.7:
            direction = "SHORT"
            stop_loss = close + (atr * 1.5)
            take_profit = close - (atr * 2.5)
            setup = "OVERBOUGHT"
        elif z <= -1.7:
            direction = "LONG"
            stop_loss = close - (atr * 1.5)
            take_profit = close + (atr * 2.5)
            setup = "OVERSOLD"
        else:
            return None

        confidence = 62.0 + min(25.0, abs(z) * 8.0)
        return SyntheticSignal(
            strategy="volatility_mean_reversion",
            direction=direction,
            entry_price=close,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=max(55.0, min(confidence, 95.0)),
            regime=str(regime.get("regime", "NORMAL")),
            details={"zscore": float(z), "setup": setup},
        )


class SyntheticStrategySelector:
    """Selector for dedicated synthetic strategy pack."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.strategies = [
            CrashSpikeStrategy(cfg),
            BoomMomentumStrategy(cfg),
            VolatilityMeanReversionStrategy(cfg),
        ]

    def get_all_signals(self, symbol: str, df: pd.DataFrame) -> List[SyntheticSignal]:
        if not self.enabled:
            return []

        signals: List[SyntheticSignal] = []
        for strategy in self.strategies:
            try:
                signal = strategy.generate_signal(symbol, df)
                if signal is not None:
                    signals.append(signal)
            except Exception:
                continue

        signals.sort(key=lambda s: float(s.confidence), reverse=True)
        return signals

    def get_best_signal(self, symbol: str, df: pd.DataFrame) -> Optional[SyntheticSignal]:
        signals = self.get_all_signals(symbol, df)
        return signals[0] if signals else None
