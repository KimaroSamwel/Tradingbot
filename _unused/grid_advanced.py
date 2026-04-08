"""Dynamic grid strategy helper inspired by Bitsgap/3Commas grid logic."""

from __future__ import annotations

from typing import Dict, List


class AdvancedGridBot:
    """Generate volatility-adjusted grid levels around current price."""

    def __init__(self, config: Dict):
        self.config = config or {}
        self.grid_levels = int(self.config.get("grid_levels", 20) or 20)
        self.grid_spread = float(self.config.get("grid_spread", 0.01) or 0.01)
        self.dynamic_adjustment = bool(self.config.get("dynamic_adjustment", True))
        self.atr_period = int(self.config.get("atr_period", 14) or 14)
        self.baseline_atr = float(self.config.get("baseline_atr", 1.0) or 1.0)

    def generate_grid(self, current_price: float, spread: float) -> List[Dict]:
        levels = []
        price = float(current_price)
        for i in range(1, self.grid_levels + 1):
            step = spread * i
            levels.append(
                {
                    "level": i,
                    "buy_price": price * (1.0 - step),
                    "sell_price": price * (1.0 + step),
                    "spread": spread,
                }
            )
        return levels

    def calculate_dynamic_grid(self, current_price: float, atr: float) -> List[Dict]:
        if self.dynamic_adjustment:
            baseline = max(self.baseline_atr, 1e-10)
            adjusted_spread = self.grid_spread * (float(atr) / baseline)
            adjusted_spread = max(self.grid_spread * 0.5, min(adjusted_spread, self.grid_spread * 3.0))
            return self.generate_grid(current_price, adjusted_spread)
        return self.generate_grid(current_price, self.grid_spread)
