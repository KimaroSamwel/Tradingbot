"""Position executor with triple-barrier risk controls."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional


@dataclass
class PositionState:
    symbol: str
    direction: str
    entry_price: float
    volume: float
    open_time: datetime
    stop_loss_price: float
    take_profit_price: float
    close_time: Optional[datetime] = None
    close_price: Optional[float] = None
    close_reason: Optional[str] = None
    trailing_stop_price: Optional[float] = None


class PositionExecutor:
    """
    Triple-barrier position manager:
      1) stop loss
      2) take profit
      3) time limit
      4) optional trailing stop
    """

    def __init__(self, position_config: Optional[Dict] = None):
        cfg = position_config or {}
        self.stop_loss = float(cfg.get("stop_loss", 0.01) or 0.01)
        self.take_profit = float(cfg.get("take_profit", 0.03) or 0.03)
        self.time_limit = int(cfg.get("time_limit", 21600) or 21600)
        self.trailing_stop_activation = cfg.get("trailing_stop_activation_price_delta")
        self.trailing_stop_delta = cfg.get("trailing_stop_trailing_delta")
        self.position: Optional[PositionState] = None

    def open_position(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        volume: float,
        opened_at: Optional[datetime] = None,
    ) -> PositionState:
        now = opened_at or datetime.now()
        direction_u = str(direction or "LONG").upper()
        entry = float(entry_price)

        if direction_u in ("LONG", "BUY"):
            stop_loss_price = entry * (1.0 - self.stop_loss)
            take_profit_price = entry * (1.0 + self.take_profit)
        else:
            stop_loss_price = entry * (1.0 + self.stop_loss)
            take_profit_price = entry * (1.0 - self.take_profit)

        self.position = PositionState(
            symbol=str(symbol),
            direction=direction_u,
            entry_price=entry,
            volume=float(volume),
            open_time=now,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
        )
        return self.position

    def _update_trailing_stop(self, current_price: float) -> None:
        if self.position is None:
            return
        if self.trailing_stop_activation is None or self.trailing_stop_delta is None:
            return

        activation_delta = float(self.trailing_stop_activation)
        trail_delta = float(self.trailing_stop_delta)
        direction = self.position.direction

        if direction in ("LONG", "BUY"):
            gain = current_price - self.position.entry_price
            if gain < activation_delta:
                return
            candidate = current_price - trail_delta
            if self.position.trailing_stop_price is None:
                self.position.trailing_stop_price = candidate
            else:
                self.position.trailing_stop_price = max(self.position.trailing_stop_price, candidate)
        else:
            gain = self.position.entry_price - current_price
            if gain < activation_delta:
                return
            candidate = current_price + trail_delta
            if self.position.trailing_stop_price is None:
                self.position.trailing_stop_price = candidate
            else:
                self.position.trailing_stop_price = min(self.position.trailing_stop_price, candidate)

    def monitor_position(self, current_price: float, now: Optional[datetime] = None) -> Dict:
        """Return monitoring snapshot and close reason if barrier is hit."""
        if self.position is None:
            return {"active": False, "reason": "no_position"}

        ts = now or datetime.now()
        price = float(current_price)
        p = self.position

        self._update_trailing_stop(price)

        # Time barrier
        if ts >= p.open_time + timedelta(seconds=self.time_limit):
            return self._close(price, ts, "time_limit")

        is_long = p.direction in ("LONG", "BUY")

        # Stop-loss barrier
        if is_long and price <= p.stop_loss_price:
            return self._close(price, ts, "stop_loss")
        if (not is_long) and price >= p.stop_loss_price:
            return self._close(price, ts, "stop_loss")

        # Take-profit barrier
        if is_long and price >= p.take_profit_price:
            return self._close(price, ts, "take_profit")
        if (not is_long) and price <= p.take_profit_price:
            return self._close(price, ts, "take_profit")

        # Trailing-stop barrier
        if p.trailing_stop_price is not None:
            if is_long and price <= p.trailing_stop_price:
                return self._close(price, ts, "trailing_stop")
            if (not is_long) and price >= p.trailing_stop_price:
                return self._close(price, ts, "trailing_stop")

        return {
            "active": True,
            "symbol": p.symbol,
            "direction": p.direction,
            "entry_price": p.entry_price,
            "current_price": price,
            "stop_loss_price": p.stop_loss_price,
            "take_profit_price": p.take_profit_price,
            "trailing_stop_price": p.trailing_stop_price,
        }

    def _close(self, close_price: float, close_time: datetime, reason: str) -> Dict:
        assert self.position is not None
        p = self.position
        p.close_price = float(close_price)
        p.close_time = close_time
        p.close_reason = str(reason)

        is_long = p.direction in ("LONG", "BUY")
        pnl_per_unit = (p.close_price - p.entry_price) if is_long else (p.entry_price - p.close_price)
        pnl = pnl_per_unit * p.volume

        snapshot = {
            "active": False,
            "symbol": p.symbol,
            "direction": p.direction,
            "entry_price": p.entry_price,
            "close_price": p.close_price,
            "volume": p.volume,
            "pnl": float(pnl),
            "close_reason": p.close_reason,
            "open_time": p.open_time.isoformat(),
            "close_time": p.close_time.isoformat(),
        }

        self.position = None
        return snapshot
