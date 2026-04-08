"""Hierarchical signal combiner with adaptive per-regime weights."""

from __future__ import annotations

from typing import Dict, Tuple

from .regime_agent import RegimeAgent
from .strategy_agents import MeanReversionAgent, TrendFollowingAgent, VolatilityBreakoutAgent


class MetaAgent:
    """Combines specialized agent outputs with regime-aware adaptive weighting."""

    def __init__(self, config: Dict | None = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))

        self.regime_agent = RegimeAgent(cfg.get("regime_agent", {}))
        self.agents = {
            "trend": TrendFollowingAgent(cfg.get("trend_agent", {})),
            "mean_reversion": MeanReversionAgent(cfg.get("mean_reversion_agent", cfg.get("mr_agent", {}))),
            "volatility_breakout": VolatilityBreakoutAgent(cfg.get("volatility_breakout_agent", cfg.get("vol_agent", {}))),
        }

        self.regime_weights: Dict[str, Dict[str, float]] = {
            "trending_up": {"trend": 0.55, "mean_reversion": 0.20, "volatility_breakout": 0.25},
            "trending_down": {"trend": 0.55, "mean_reversion": 0.20, "volatility_breakout": 0.25},
            "ranging": {"trend": 0.20, "mean_reversion": 0.55, "volatility_breakout": 0.25},
            "spiking": {"trend": 0.20, "mean_reversion": 0.15, "volatility_breakout": 0.65},
        }

    def update_weights(self, regime: str, agent_performance: Dict[str, float]) -> None:
        regime_key = str(regime or "ranging")
        perf = agent_performance if isinstance(agent_performance, dict) else {}

        base = dict(self.regime_weights.get(regime_key, {}))
        if not base:
            base = {name: 1.0 / max(len(self.agents), 1) for name in self.agents}

        scored = {}
        for name, weight in base.items():
            reward = float(perf.get(name, 0.0) or 0.0)
            scored[name] = max(0.02, float(weight) + (reward * 0.03))

        total = sum(scored.values())
        if total <= 0:
            return

        self.regime_weights[regime_key] = {name: value / total for name, value in scored.items()}

    def update_agent_performance(self, strategy: str, pnl: float) -> None:
        strategy_u = str(strategy or "").upper()
        mapping = {
            "TREND": "trend",
            "MEAN_REVERSION": "mean_reversion",
            "VOLATILITY_BREAKOUT": "volatility_breakout",
        }
        for key, agent_name in mapping.items():
            if key in strategy_u and agent_name in self.agents:
                self.agents[agent_name].update_performance(float(pnl or 0.0))
                break

    def get_combined_signal(self, symbol: str, data) -> Tuple[int, float, Dict]:
        regime, regime_conf = self.regime_agent.detect_regime(symbol, data)
        weights = self.regime_weights.get(regime, self.regime_weights.get("ranging", {}))

        weighted_signal = 0.0
        total_weight = 0.0
        explanation = {
            "regime": regime,
            "regime_confidence": regime_conf,
            "agents": {},
        }

        for name, agent in self.agents.items():
            signal, confidence = agent.generate_signal(data, regime)
            weight = float(weights.get(name, 1.0 / max(len(self.agents), 1)))
            weighted_signal += float(signal) * float(confidence) * weight
            total_weight += weight
            explanation["agents"][name] = {
                "signal": int(signal),
                "confidence": float(confidence),
                "weight": float(weight),
                "rolling_score": float(agent.rolling_score()),
            }

        if total_weight <= 0:
            return 0, 0.0, explanation

        normalized_score = weighted_signal / total_weight
        final_conf = min(1.0, abs(normalized_score)) * max(0.4, float(regime_conf))

        if normalized_score > 0.2:
            final_signal = 1
        elif normalized_score < -0.2:
            final_signal = -1
        else:
            final_signal = 0

        explanation["normalized_score"] = float(normalized_score)
        explanation["final_signal"] = int(final_signal)
        explanation["final_confidence"] = float(final_conf)
        return final_signal, float(final_conf), explanation
