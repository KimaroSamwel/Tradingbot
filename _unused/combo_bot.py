"""Combo strategy: blend dynamic grid and smart DCA tactics."""

from __future__ import annotations

from typing import Dict

from src.strategies.dca_smart import DCASmartBot
from src.strategies.grid_advanced import AdvancedGridBot


class ComboBot:
    """Combine grid + DCA behaviors for directional or neutral deployment."""

    def __init__(self, config: Dict):
        self.config = config or {}
        self.leverage = int(self.config.get("leverage", 10) or 10)
        self.grid_bot = AdvancedGridBot(self.config)
        self.dca_bot = DCASmartBot(self.config)
        self.combo_mode = str(self.config.get("combo_mode", "alternating") or "alternating")

    def execute_combo_strategy(self, symbol: str, current_price: float, atr: float, direction: str = "buy") -> Dict:
        grid_levels = self.grid_bot.calculate_dynamic_grid(current_price=current_price, atr=atr)
        safety_orders = self.dca_bot.calculate_safety_order_chain(initial_price=current_price, direction=direction)

        return {
            "symbol": symbol,
            "combo_mode": self.combo_mode,
            "leverage": self.leverage,
            "grid_levels": grid_levels,
            "safety_orders": safety_orders,
        }
