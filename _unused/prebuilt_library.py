"""Pre-built strategy templates inspired by Pionex-style defaults."""

from __future__ import annotations

from typing import Dict


class PrebuiltStrategyLibrary:
    """Collection of no-code ready strategy templates."""

    @staticmethod
    def grid_strategy_basic() -> Dict:
        return {
            "type": "grid",
            "levels": 10,
            "spread": 0.02,
            "investment_per_grid": 0.1,
        }

    @staticmethod
    def infinity_grid() -> Dict:
        return {
            "type": "infinity_grid",
            "dynamic_adjustment": True,
            "reinvest_profits": True,
        }

    @staticmethod
    def rebalancing_bot(target_allocation: Dict[str, float]) -> Dict:
        return {
            "type": "rebalancing",
            "target_allocation": target_allocation,
            "rebalance_threshold": 0.05,
            "rebalance_frequency": "daily",
        }

    @staticmethod
    def dca_accumulator() -> Dict:
        return {
            "type": "dca",
            "interval": "4h",
            "base_order_size": 1.0,
            "safety_orders": [
                {"deviation": 0.03, "size_multiplier": 1.2},
                {"deviation": 0.06, "size_multiplier": 1.4},
            ],
        }
