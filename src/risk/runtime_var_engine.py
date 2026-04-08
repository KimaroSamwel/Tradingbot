"""Runtime VaR/CVaR risk engine with pre-trade budget checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np


@dataclass
class VaRSnapshot:
    """Container for most recent risk metrics."""

    var_amount: float
    cvar_amount: float
    var_pct: float
    cvar_pct: float
    confidence_level: float
    sample_size: int


class RuntimeVaREngine:
    """Historical-simulation VaR/CVaR engine for live runtime gating."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", False))
        self.confidence_level = float(cfg.get("confidence_level", 0.95) or 0.95)
        self.historical_window = max(20, int(cfg.get("historical_window", 100) or 100))

        self.max_var_pct = float(cfg.get("max_var_pct", 0.02) or 0.02)
        self.max_cvar_pct = float(cfg.get("max_cvar_pct", 0.03) or 0.03)

        actions_cfg = cfg.get("risk_actions", {}) if isinstance(cfg.get("risk_actions", {}), dict) else {}
        self.level1_threshold = float(actions_cfg.get("level1_threshold", 0.60) or 0.60)
        self.level2_threshold = float(actions_cfg.get("level2_threshold", 0.80) or 0.80)
        self.level3_threshold = float(actions_cfg.get("level3_threshold", 1.00) or 1.00)

        self.current_positions: List[Dict] = []
        self._returns_by_symbol: Dict[str, np.ndarray] = {}
        self._snapshot = VaRSnapshot(
            var_amount=0.0,
            cvar_amount=0.0,
            var_pct=0.0,
            cvar_pct=0.0,
            confidence_level=self.confidence_level,
            sample_size=0,
        )

    def update_positions(self, positions: Iterable[Dict]) -> None:
        self.current_positions = [dict(pos or {}) for pos in (positions or []) if isinstance(pos, dict)]

    def update_symbol_history(self, symbol: str, close_prices: Iterable[float]) -> None:
        symbol_key = str(symbol or "").upper()
        if not symbol_key:
            return

        if close_prices is None:
            return

        arr = np.asarray(list(close_prices), dtype=float)
        arr = arr[np.isfinite(arr)]
        if arr.size < 3:
            return

        returns = np.diff(arr) / np.maximum(arr[:-1], 1e-12)
        returns = returns[np.isfinite(returns)]
        if returns.size < 2:
            return

        if returns.size > self.historical_window:
            returns = returns[-self.historical_window :]
        self._returns_by_symbol[symbol_key] = returns

    def update_from_market_data(self, market_data: Dict[str, object]) -> None:
        if not isinstance(market_data, dict):
            return

        for key, df in market_data.items():
            if not isinstance(key, str) or "_" in key:
                # Skip M15/H1/H4 aliases (symbol_M15, etc.)
                continue
            if not hasattr(df, "columns") or "close" not in getattr(df, "columns", []):
                continue
            try:
                closes = [float(v) for v in df["close"].tail(self.historical_window + 1).tolist()]
            except Exception:
                continue
            self.update_symbol_history(key, closes)

    def _portfolio_return_series(self) -> np.ndarray:
        if not self.current_positions:
            return np.asarray([], dtype=float)

        weighted_series: List[np.ndarray] = []
        weights: List[float] = []

        for pos in self.current_positions:
            symbol = str(pos.get("symbol", "") or "").upper()
            if not symbol:
                continue
            symbol_returns = self._returns_by_symbol.get(symbol)
            if symbol_returns is None or symbol_returns.size < 2:
                continue

            weight = abs(float(pos.get("volume", 0.0) or 0.0))
            if weight <= 0:
                weight = 1.0

            weighted_series.append(symbol_returns)
            weights.append(weight)

        if not weighted_series:
            return np.asarray([], dtype=float)

        min_len = min(series.size for series in weighted_series)
        aligned = np.vstack([series[-min_len:] for series in weighted_series])
        w = np.asarray(weights, dtype=float)
        w = w / np.maximum(w.sum(), 1e-12)

        # Long/short direction aware weighting.
        signed_weights = []
        for idx, pos in enumerate(self.current_positions[: len(weights)]):
            direction = str(pos.get("direction", "BUY") or "BUY").upper()
            signed_weights.append(w[idx] if direction in ("BUY", "LONG") else -w[idx])
        sw = np.asarray(signed_weights, dtype=float)

        returns = np.dot(sw, aligned)
        returns = returns[np.isfinite(returns)]
        if returns.size > self.historical_window:
            returns = returns[-self.historical_window :]
        return returns

    def _compute_percentiles(self, returns: np.ndarray) -> Tuple[float, float]:
        if returns.size == 0:
            return 0.0, 0.0

        tail = max(0.0, min(1.0, 1.0 - self.confidence_level))
        q = float(np.quantile(returns, tail))
        var_pct = abs(min(q, 0.0))

        tail_values = returns[returns <= q]
        if tail_values.size == 0:
            cvar_pct = var_pct
        else:
            cvar_pct = abs(float(np.mean(tail_values)))

        return var_pct, cvar_pct

    def compute_var(self, equity: float) -> Tuple[float, float]:
        returns = self._portfolio_return_series()
        var_pct, cvar_pct = self._compute_percentiles(returns)
        eq = max(float(equity or 0.0), 1e-12)

        var_amount = var_pct * eq
        cvar_amount = cvar_pct * eq
        self._snapshot = VaRSnapshot(
            var_amount=float(var_amount),
            cvar_amount=float(cvar_amount),
            var_pct=float(var_pct),
            cvar_pct=float(cvar_pct),
            confidence_level=self.confidence_level,
            sample_size=int(returns.size),
        )
        return float(var_amount), float(var_pct)

    def compute_cvar(self, equity: float) -> Tuple[float, float]:
        self.compute_var(equity)
        return float(self._snapshot.cvar_amount), float(self._snapshot.cvar_pct)

    def _estimate_order_risk_pct(self, proposed_order: Dict, equity: float) -> float:
        if not isinstance(proposed_order, dict):
            return 0.0

        risk_percent = float(proposed_order.get("risk_percent", 0.0) or 0.0)
        if risk_percent > 0:
            # Existing order objects usually keep this in percentage units.
            return min(risk_percent / 100.0, 1.0)

        entry = float(proposed_order.get("entry_price", 0.0) or 0.0)
        stop = float(proposed_order.get("stop_loss", proposed_order.get("sl", 0.0)) or 0.0)
        volume = float(proposed_order.get("lot_size", proposed_order.get("volume", 0.0)) or 0.0)
        if entry <= 0 or stop <= 0 or volume <= 0:
            return 0.0

        # Approximate notional-at-risk; conservative for synthetic indices and FX.
        # volume is in lots (e.g., 0.01), * 100000 gives units for standard calculation
        # This is a conservative approximation - actual risk uses pip_value which varies by instrument
        risk_amount = abs(entry - stop) * volume * 100000.0
        eq = max(float(equity or 0.0), 1e-12)
        return max(0.0, min(risk_amount / eq, 1.0))

    def check_risk_budget(self, proposed_order: Dict, equity: float) -> Tuple[bool, str, float]:
        if not self.enabled:
            return True, "var_disabled", 0.0

        self.compute_var(equity)
        projected_var_pct = self._snapshot.var_pct + self._estimate_order_risk_pct(proposed_order, equity)
        projected_cvar_pct = self._snapshot.cvar_pct + self._estimate_order_risk_pct(proposed_order, equity)

        if projected_var_pct > self.max_var_pct:
            return (
                False,
                f"Projected VaR {projected_var_pct:.4f} exceeds max {self.max_var_pct:.4f}",
                projected_var_pct,
            )

        if projected_cvar_pct > self.max_cvar_pct:
            return (
                False,
                f"Projected CVaR {projected_cvar_pct:.4f} exceeds max {self.max_cvar_pct:.4f}",
                projected_var_pct,
            )

        return True, "within_budget", projected_var_pct

    def get_risk_actions(self) -> Tuple[int, str]:
        if not self.enabled:
            return 0, "var_disabled"

        utilization = 0.0
        if self.max_var_pct > 0:
            utilization = self._snapshot.var_pct / self.max_var_pct

        if utilization >= self.level3_threshold:
            return 3, f"VaR utilization critical ({utilization:.2f}x)"
        if utilization >= self.level2_threshold:
            return 2, f"VaR utilization high ({utilization:.2f}x)"
        if utilization >= self.level1_threshold:
            return 1, f"VaR utilization elevated ({utilization:.2f}x)"

        return 0, "risk normal"

    def snapshot(self) -> Dict:
        return {
            "enabled": self.enabled,
            "confidence_level": self._snapshot.confidence_level,
            "sample_size": self._snapshot.sample_size,
            "var_amount": float(self._snapshot.var_amount),
            "cvar_amount": float(self._snapshot.cvar_amount),
            "var_pct": float(self._snapshot.var_pct),
            "cvar_pct": float(self._snapshot.cvar_pct),
            "max_var_pct": float(self.max_var_pct),
            "max_cvar_pct": float(self.max_cvar_pct),
        }
