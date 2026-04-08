"""Smart DCA strategy module inspired by 3Commas-style automation."""

from __future__ import annotations

from typing import Dict, List


class DCASmartBot:
    """DCA helper with safety-order ladder generation and entry gating."""

    def __init__(self, config: Dict):
        self.config = config or {}
        self.base_order_size = float(self.config.get("base_order_size", 1.0) or 1.0)
        self.safety_orders = list(self.config.get("safety_orders", []))
        self.price_deviation = float(self.config.get("price_deviation", 0.02) or 0.02)
        self.volume_threshold = float(self.config.get("volume_threshold", 1.5) or 1.5)

    def calculate_safety_order_chain(self, initial_price: float, direction: str) -> List[Dict]:
        orders = []
        side = str(direction or "buy").lower()

        for i, safety in enumerate(self.safety_orders):
            deviation = float(safety.get("deviation", 0.03 * (i + 1)) or (0.03 * (i + 1)))
            size_multiplier = float(safety.get("size_multiplier", 1.5) or 1.5)
            order_size = self.base_order_size * (size_multiplier ** i)

            if side == "buy":
                price = initial_price * (1.0 - deviation)
            else:
                price = initial_price * (1.0 + deviation)

            orders.append(
                {
                    "index": i + 1,
                    "price": float(price),
                    "size": float(order_size),
                    "deviation": float(deviation),
                    "direction": side,
                }
            )

        return orders

    def should_trigger_safety_order(self, entry_price: float, current_price: float, direction: str) -> bool:
        side = str(direction or "buy").lower()
        entry = float(entry_price)
        current = float(current_price)
        if side == "buy":
            return current <= entry * (1.0 - self.price_deviation)
        return current >= entry * (1.0 + self.price_deviation)

    def volume_filter_passed(self, current_volume: float, average_volume: float) -> bool:
        avg = float(average_volume or 0.0)
        if avg <= 0:
            return False
        return float(current_volume) >= (avg * self.volume_threshold)
