"""Micro-profit compounding helper for high-frequency style strategies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List


@dataclass
class Opportunity:
    implied_probability: float
    estimated_true_probability: float
    expected_edge: float
    symbol: str


class CompoundingEngine:
    def __init__(self, config: Dict):
        cfg = config or {}
        self.target_daily_return = float(cfg.get("target_daily_return", 0.005) or 0.005)
        self.max_position_size_pct = float(cfg.get("max_position_size_pct", 0.02) or 0.02)
        self.min_probability = float(cfg.get("min_probability", 0.9) or 0.9)
        self.max_trades_per_day = int(cfg.get("max_trades_per_day", 200) or 200)
        self.initial_capital = float(cfg.get("initial_capital", 1000.0) or 1000.0)

    def scan_low_probability_mispricing(self, markets: Iterable[Opportunity]) -> List[Opportunity]:
        opportunities = []
        for market in markets:
            if market.implied_probability < 0.01 and market.estimated_true_probability > self.min_probability:
                opportunities.append(market)
        return opportunities

    def calculate_compounding_projection(self, days: int, daily_return: float) -> float:
        return float(self.initial_capital * ((1.0 + float(daily_return)) ** int(days)))

    def risk_capped_position_size(self, equity: float) -> float:
        return float(max(0.0, equity) * self.max_position_size_pct)
