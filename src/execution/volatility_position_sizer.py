"""Volatility-targeting position sizing helper for synthetic-heavy markets."""

from __future__ import annotations

from typing import Dict, Optional


class VolatilityPositionSizer:
    """ATR-aware risk normalizer for lot sizing."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.risk_per_trade_pct = float(cfg.get("risk_per_trade_pct", 0.005) or 0.005)
        self.atr_period = max(2, int(cfg.get("atr_period", 14) or 14))
        self.min_size = float(cfg.get("min_size", 0.01) or 0.01)
        self.max_size = float(cfg.get("max_size", 50.0) or 50.0)
        self.min_stop_atr = float(cfg.get("min_stop_atr", 2.0) or 2.0)

    def get_pip_value(self, symbol: str, entry_price: float) -> float:
        """Return pip value PER STANDARD LOT (1.0 lot), not per micro lot."""
        symbol_u = str(symbol or "").upper()
        if symbol_u.startswith("XAU"):
            return 1.0   # 100 oz * $0.01/pip = $1.00
        if symbol_u.startswith("XAG"):
            return 5.0   # 5000 oz * $0.001/pip = $5.00
        if "JPY" in symbol_u:
            return 6.50  # ~$6.50 per pip per standard lot
        if "INDEX" in symbol_u or "VOLATILITY" in symbol_u or "CRASH" in symbol_u or "BOOM" in symbol_u:
            return max(0.50, abs(float(entry_price or 0.0)) * 0.002)
        return 10.0      # $10.00 per pip per standard lot for Forex majors

    def calculate_size(
        self,
        symbol: str,
        equity: float,
        atr_value: float,
        entry_price: float,
        stop_loss_pips: float,
        pip_value: Optional[float] = None,
    ) -> float:
        if equity <= 0:
            return self.min_size

        risk_amount = float(equity) * max(0.0, self.risk_per_trade_pct)
        atr = max(float(atr_value or 0.0), 1e-8)
        stop_distance = max(float(stop_loss_pips or 0.0), self.min_stop_atr * atr)
        pv = float(pip_value if pip_value is not None else self.get_pip_value(symbol, entry_price) or 0.0)
        if pv <= 0:
            pv = 0.10

        raw_size = risk_amount / max(stop_distance * pv, 1e-8)
        # Emergency cap for small accounts
        effective_max = self.max_size
        if equity < 500:
            effective_max = min(effective_max, 0.02)
        elif equity < 1000:
            effective_max = min(effective_max, 0.05)
        return max(self.min_size, min(effective_max, float(raw_size)))
