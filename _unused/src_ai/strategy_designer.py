"""AI strategy designer (regime-aware strategy selection and blending)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class RegimeProfile:
    regime: str
    trend_strength: float
    volatility_ratio: float


class MarketRegimeClassifier:
    """Lightweight regime classifier using trend + volatility features."""

    def __init__(self, window: int = 100):
        self.window = int(window)

    def classify(self, market_data: pd.DataFrame) -> RegimeProfile:
        if market_data is None or len(market_data) < max(50, self.window // 2):
            return RegimeProfile("unknown", 0.0, 1.0)

        close = market_data["close"].astype(float)
        fast = close.ewm(span=20, adjust=False).mean().iloc[-1]
        slow = close.ewm(span=50, adjust=False).mean().iloc[-1]
        trend_strength = 0.0 if slow == 0 else float((fast - slow) / slow)

        returns = close.pct_change().dropna()
        fast_vol = float(returns.tail(20).std() or 0.0)
        slow_vol = float(returns.tail(min(len(returns), self.window)).std() or 1e-10)
        vol_ratio = float(fast_vol / max(slow_vol, 1e-10))

        if vol_ratio > 1.4:
            regime = "volatile"
        elif abs(trend_strength) > 0.003:
            regime = "trending"
        else:
            regime = "ranging"

        return RegimeProfile(regime=regime, trend_strength=trend_strength, volatility_ratio=vol_ratio)


class AIStrategyDesigner:
    """Regime-aware strategy template selector and blender."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.strategy_library: List[Dict] = cfg.get("strategy_library", [])
        self.performance_history: Dict[str, Dict[str, float]] = cfg.get("performance_history", {})
        self.market_regime_classifier = MarketRegimeClassifier(window=int(cfg.get("regime_detection_window", 100) or 100))

    def evaluate_market_conditions(self, market_data: pd.DataFrame) -> Dict:
        profile = self.market_regime_classifier.classify(market_data)
        return {
            "regime": profile.regime,
            "trend_strength": profile.trend_strength,
            "volatility_ratio": profile.volatility_ratio,
        }

    def select_optimal_strategy(self, regime: str) -> Optional[Dict]:
        regime_key = str(regime or "unknown").lower()
        best_name = None
        best_score = -np.inf

        for strategy_name, metrics in self.performance_history.items():
            score = float(metrics.get(regime_key, metrics.get("overall", 0.0)) or 0.0)
            if score > best_score:
                best_score = score
                best_name = strategy_name

        if best_name is None and self.strategy_library:
            return self.strategy_library[0]

        for strategy in self.strategy_library:
            if str(strategy.get("name", "")) == str(best_name):
                return strategy

        return None

    def blend_strategies(self, strategies: List[Dict], weights: List[float]) -> Dict:
        if not strategies:
            return {"strategies": [], "weights": [], "blended_confidence": 0.0}

        if len(weights) != len(strategies):
            weights = [1.0] * len(strategies)

        total = float(sum(max(0.0, w) for w in weights))
        if total <= 0:
            normalized = [1.0 / len(strategies)] * len(strategies)
        else:
            normalized = [max(0.0, w) / total for w in weights]

        confidence = 0.0
        for strategy, w in zip(strategies, normalized):
            confidence += float(strategy.get("confidence", 0.0) or 0.0) * w

        return {
            "strategies": strategies,
            "weights": normalized,
            "blended_confidence": float(confidence),
        }
