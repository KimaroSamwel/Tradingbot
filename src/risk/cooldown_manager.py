"""Per-symbol cooldown manager for repeated execution failures."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional


@dataclass
class CooldownState:
    """Mutable cooldown state for one symbol."""

    last_failure_time: Optional[datetime] = None
    failure_count: int = 0
    cooldown_until: Optional[datetime] = None
    last_reason: str = ""


class CooldownManager:
    """Tracks per-symbol execution failures and enforces adaptive cooldowns."""

    def __init__(self, config: Dict):
        cfg = config or {}
        self.cooldowns: Dict[str, CooldownState] = {}
        self.max_failures = int(cfg.get("max_failures_per_symbol", 3) or 3)
        self.base_cooldown_minutes = int(cfg.get("base_cooldown_minutes", 60) or 60)
        self.reset_failures_after_minutes = int(cfg.get("reset_failures_after_minutes", 240) or 240)

    def _now(self) -> datetime:
        return datetime.now()

    def _get_state(self, symbol: str) -> CooldownState:
        key = str(symbol or "").upper()
        if key not in self.cooldowns:
            self.cooldowns[key] = CooldownState()
        return self.cooldowns[key]

    def record_failure(self, symbol: str, reason: str = "") -> Dict:
        """Increment failure count and set cooldown if threshold is reached."""
        state = self._get_state(symbol)
        now = self._now()

        if state.last_failure_time is not None:
            minutes_since_last = (now - state.last_failure_time).total_seconds() / 60.0
            if minutes_since_last > float(self.reset_failures_after_minutes):
                state.failure_count = 0
                state.cooldown_until = None

        state.failure_count += 1
        state.last_failure_time = now
        state.last_reason = str(reason or "")

        if state.failure_count >= self.max_failures:
            escalation_step = max(1, state.failure_count - self.max_failures + 1)
            cooldown_minutes = self.base_cooldown_minutes * escalation_step
            state.cooldown_until = now + timedelta(minutes=cooldown_minutes)

        return self.get_symbol_status(symbol)

    def reset_cooldown(self, symbol: str) -> Dict:
        """Reset failure/cooldown state after a successful fill."""
        state = self._get_state(symbol)
        state.failure_count = 0
        state.cooldown_until = None
        state.last_reason = ""
        return self.get_symbol_status(symbol)

    def is_cooldown_active(self, symbol: str) -> bool:
        """Check if symbol is currently blocked by cooldown."""
        state = self._get_state(symbol)
        if state.cooldown_until is None:
            return False
        return self._now() < state.cooldown_until

    def get_remaining_cooldown(self, symbol: str) -> float:
        """Return remaining cooldown in minutes (0.0 if inactive)."""
        state = self._get_state(symbol)
        if state.cooldown_until is None:
            return 0.0

        remaining = (state.cooldown_until - self._now()).total_seconds() / 60.0
        return max(0.0, float(remaining))

    def get_symbol_status(self, symbol: str) -> Dict:
        """Return serializable status for one symbol."""
        state = self._get_state(symbol)
        return {
            "symbol": str(symbol or "").upper(),
            "failure_count": int(state.failure_count),
            "cooldown_active": bool(self.is_cooldown_active(symbol)),
            "remaining_cooldown_minutes": float(round(self.get_remaining_cooldown(symbol), 2)),
            "cooldown_until": state.cooldown_until.isoformat() if state.cooldown_until else None,
            "last_failure_time": state.last_failure_time.isoformat() if state.last_failure_time else None,
            "last_reason": state.last_reason,
        }

    def get_all_status(self) -> Dict[str, Dict]:
        """Return serializable status for all symbols."""
        return {
            symbol: self.get_symbol_status(symbol)
            for symbol in sorted(self.cooldowns.keys())
        }
