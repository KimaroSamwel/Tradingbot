"""Execution lifecycle telemetry for reliability auditing."""

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import os
from typing import Dict, List, Optional


@dataclass
class ExecutionLifecycleEvent:
    """Single lifecycle event for one symbol/order path."""

    event_id: str
    timestamp: str
    symbol: str
    strategy: str
    stage: str
    status: str
    details: Dict


class ExecutionTelemetryTracker:
    """Tracks signal->pending->fill->close lifecycle reliability."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.history_file = str(cfg.get("history_file", "logs/execution_telemetry.json"))
        self.max_events = int(cfg.get("max_events", 10000))

        self.events: List[ExecutionLifecycleEvent] = []

    def record_event(
        self,
        symbol: str,
        strategy: str,
        stage: str,
        status: str,
        details: Optional[Dict] = None,
    ) -> None:
        """Append lifecycle event if telemetry is enabled."""
        if not self.enabled:
            return

        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        details_payload = details if isinstance(details, dict) else {}

        event = ExecutionLifecycleEvent(
            event_id=f"{symbol}_{stage}_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            timestamp=now,
            symbol=str(symbol or "UNKNOWN"),
            strategy=str(strategy or "UNKNOWN"),
            stage=str(stage or "UNKNOWN"),
            status=str(status or "UNKNOWN"),
            details=details_payload,
        )

        self.events.append(event)
        if self.max_events > 0 and len(self.events) > self.max_events:
            self.events = self.events[-self.max_events :]

    def _event_to_dict(self, event: ExecutionLifecycleEvent) -> Dict:
        return {
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "symbol": event.symbol,
            "strategy": event.strategy,
            "stage": event.stage,
            "status": event.status,
            "details": event.details,
        }

    def _dict_to_event(self, payload: Dict) -> ExecutionLifecycleEvent:
        return ExecutionLifecycleEvent(
            event_id=str(payload.get("event_id", "")),
            timestamp=str(payload.get("timestamp", datetime.now(timezone.utc).isoformat(timespec="seconds"))),
            symbol=str(payload.get("symbol", "UNKNOWN")),
            strategy=str(payload.get("strategy", "UNKNOWN")),
            stage=str(payload.get("stage", "UNKNOWN")),
            status=str(payload.get("status", "UNKNOWN")),
            details=payload.get("details", {}) if isinstance(payload.get("details", {}), dict) else {},
        )

    def save_history(self) -> int:
        """Persist events to JSON. Returns saved count."""
        if not self.enabled or not self.history_file:
            return 0

        directory = os.path.dirname(self.history_file)
        if directory:
            os.makedirs(directory, exist_ok=True)

        payload = [self._event_to_dict(e) for e in self.events[-self.max_events :]]
        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        return len(payload)

    def load_history(self) -> int:
        """Load persisted telemetry events. Returns loaded count."""
        if not self.enabled or not self.history_file or not os.path.exists(self.history_file):
            return 0

        with open(self.history_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, list):
            return 0

        restored: List[ExecutionLifecycleEvent] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            try:
                restored.append(self._dict_to_event(item))
            except Exception:
                continue

        self.events = restored[-self.max_events :]
        return len(self.events)

    # Failure reasons that are non-transient (permanent at current account size)
    # and should NOT count toward reliability scoring.
    _NON_TRANSIENT_FAILURE_REASONS = frozenset({
        'insufficient_free_margin', 'insufficient_margin',
        'insufficient_equity', 'invalid_account_equity',
        'risk_exceeds_equity_limit', 'lot_size_exceeds_safety_limit',
        'invalid_stop_direction_buy', 'invalid_stop_direction_sell',
        'duplicate_order_replay_protection',
        'margin_infeasible', 'risk_infeasible',
    })

    def get_symbol_metrics(self, symbol: str) -> Dict:
        """Get reliability metrics for one symbol."""
        symbol_upper = str(symbol or "").upper()
        symbol_events = [e for e in self.events if e.symbol.upper() == symbol_upper]

        signals = sum(1 for e in symbol_events if e.stage == "SIGNAL")

        # Count non-transient FAILED events so we can subtract them from attempts.
        non_transient_failures = sum(
            1
            for e in symbol_events
            if e.stage == "ORDER_ATTEMPT"
            and e.status == "FAILED"
            and any(
                r in str(e.details.get("reason", ""))
                for r in self._NON_TRANSIENT_FAILURE_REASONS
            )
        )

        started_attempts = sum(
            1
            for e in symbol_events
            if e.stage == "ORDER_ATTEMPT" and e.status == "STARTED"
        )
        if started_attempts > 0:
            attempts = max(0, started_attempts - non_transient_failures)
        else:
            # Backward-compatible fallback for historical logs that may not have STARTED.
            attempts = sum(
                1
                for e in symbol_events
                if e.stage == "ORDER_ATTEMPT" and e.status in {"SUCCESS", "FAILED"}
            )
            attempts = max(0, attempts - non_transient_failures)

        successful_attempts = sum(
            1
            for e in symbol_events
            if e.stage == "ORDER_ATTEMPT" and e.status == "SUCCESS"
        )

        pending = sum(1 for e in symbol_events if e.stage == "PENDING_PLACED" and e.status == "SUCCESS")
        fills = sum(1 for e in symbol_events if e.stage == "FILLED" and e.status == "SUCCESS")
        closes = sum(1 for e in symbol_events if e.stage == "CLOSED" and e.status == "SUCCESS")
        failures = sum(1 for e in symbol_events if e.status == "FAILED")
        rejects = sum(1 for e in symbol_events if e.status == "REJECTED")

        reliability_score = 0.0
        if attempts > 0:
            reliability_score = max(0.0, min((successful_attempts / attempts) * 100.0, 100.0))

        return {
            "symbol": symbol,
            "signals": signals,
            "attempts": attempts,
            "successful_attempts": successful_attempts,
            "pending_placed": pending,
            "fills": fills,
            "closed": closes,
            "failures": failures,
            "rejections": rejects,
            "reliability_score": reliability_score,
        }

    def get_portfolio_metrics(self) -> Dict:
        """Aggregated telemetry across symbols."""
        symbols = sorted({e.symbol for e in self.events if e.symbol})
        by_symbol = {symbol: self.get_symbol_metrics(symbol) for symbol in symbols}

        total_attempts = sum(m["attempts"] for m in by_symbol.values())
        total_successful_attempts = sum(m.get("successful_attempts", 0) for m in by_symbol.values())
        total_fills = sum(m["fills"] for m in by_symbol.values())
        score = (total_successful_attempts / total_attempts) * 100.0 if total_attempts > 0 else 0.0

        return {
            "symbols": by_symbol,
            "total_symbols": len(symbols),
            "total_attempts": total_attempts,
            "total_successful_attempts": total_successful_attempts,
            "total_fills": total_fills,
            "portfolio_reliability_score": score,
        }
