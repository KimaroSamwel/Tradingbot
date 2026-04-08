"""Track order lifecycle from signal generation to close with persistence helpers."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class OrderLifecycleTracker:
    """Tracks signal -> pending -> fill -> close lifecycle records."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.history_file = str(cfg.get("history_file", "logs/order_lifecycle.json"))
        self.csv_file = str(cfg.get("csv_file", "logs/order_lifecycle.csv"))
        self.max_records = int(cfg.get("max_records", 10000) or 10000)
        self.records: Dict[str, Dict] = {}
        self.latest_signal_by_symbol: Dict[str, str] = {}

    def _now_iso(self) -> str:
        return datetime.now().isoformat()

    def _ensure_record(
        self,
        signal_id: str,
        symbol: str,
        magic: int = 0,
        signal_confidence: float = 0.0,
        signal_strategy: str = "",
    ) -> Dict:
        key = str(signal_id)
        if key not in self.records:
            self.records[key] = {
                "signal_id": key,
                "symbol": str(symbol),
                "magic": int(magic),
                "signal_time": None,
                "signal_confidence": float(signal_confidence),
                "signal_strategy": str(signal_strategy),
                "pending_order_time": None,
                "pending_order_ticket": None,
                "fill_time": None,
                "fill_price": None,
                "fill_volume": None,
                "close_time": None,
                "close_price": None,
                "pnl": None,
                "stages": {
                    "signal_generated": False,
                    "pending_created": False,
                    "filled": False,
                    "partially_closed": False,
                    "closed": False,
                },
            }
        return self.records[key]

    def _derive_signal_id(self, symbol: str, strategy: str, details: Optional[Dict]) -> str:
        d = details or {}
        explicit = d.get("signal_id")
        if explicit:
            return str(explicit)

        ticket = d.get("ticket") or d.get("position_ticket")
        if ticket:
            return f"{symbol}:{strategy}:{ticket}"

        existing = self.latest_signal_by_symbol.get(str(symbol))
        if existing:
            return existing

        return f"{symbol}:{strategy}:{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

    def record_signal_generated(
        self,
        signal_id: str,
        symbol: str,
        magic: int,
        signal_confidence: float,
        signal_strategy: str,
        signal_time: Optional[str] = None,
    ) -> Dict:
        record = self._ensure_record(signal_id, symbol, magic, signal_confidence, signal_strategy)
        record["signal_time"] = signal_time or self._now_iso()
        record["signal_confidence"] = float(signal_confidence)
        record["signal_strategy"] = str(signal_strategy)
        record["stages"]["signal_generated"] = True
        self.latest_signal_by_symbol[str(symbol)] = str(signal_id)
        return record

    def record_pending_order_placed(
        self,
        signal_id: str,
        pending_order_ticket: int,
        pending_order_time: Optional[str] = None,
    ) -> Dict:
        record = self._ensure_record(signal_id, symbol=self.records.get(signal_id, {}).get("symbol", "UNKNOWN"))
        record["pending_order_time"] = pending_order_time or self._now_iso()
        record["pending_order_ticket"] = int(pending_order_ticket)
        record["stages"]["pending_created"] = True
        return record

    def record_order_filled(
        self,
        signal_id: str,
        fill_price: float,
        fill_volume: float,
        fill_time: Optional[str] = None,
    ) -> Dict:
        record = self._ensure_record(signal_id, symbol=self.records.get(signal_id, {}).get("symbol", "UNKNOWN"))
        record["fill_time"] = fill_time or self._now_iso()
        record["fill_price"] = float(fill_price)
        record["fill_volume"] = float(fill_volume)
        record["stages"]["filled"] = True
        return record

    def record_position_closed(
        self,
        signal_id: str,
        close_price: float,
        pnl: float,
        close_time: Optional[str] = None,
    ) -> Dict:
        record = self._ensure_record(signal_id, symbol=self.records.get(signal_id, {}).get("symbol", "UNKNOWN"))
        record["close_time"] = close_time or self._now_iso()
        record["close_price"] = float(close_price)
        record["pnl"] = float(pnl)
        record["stages"]["closed"] = True
        return record

    def record_position_partial_close(
        self,
        signal_id: str,
        close_price: float,
        pnl: float,
        close_time: Optional[str] = None,
    ) -> Dict:
        """Record a partial close event without marking trade as fully closed."""
        record = self._ensure_record(signal_id, symbol=self.records.get(signal_id, {}).get("symbol", "UNKNOWN"))
        record["close_time"] = close_time or self._now_iso()
        record["close_price"] = float(close_price)
        record["pnl"] = float(pnl)
        record["stages"]["partially_closed"] = True
        return record

    def record_stage_event(
        self,
        symbol: str,
        strategy: str,
        stage: str,
        status: str,
        details: Optional[Dict] = None,
        magic: int = 0,
    ) -> Optional[Dict]:
        """Bridge generic execution stages into lifecycle schema."""
        stage_u = str(stage or "").upper()
        status_u = str(status or "").upper()
        signal_id = self._derive_signal_id(symbol, strategy, details)
        self._ensure_record(
            signal_id=signal_id,
            symbol=symbol,
            magic=int(magic),
            signal_confidence=float((details or {}).get("confidence", 0.0) or 0.0),
            signal_strategy=str(strategy or ""),
        )

        if stage_u == "SIGNAL":
            confidence = float((details or {}).get("confidence", 0.0) or 0.0)
            return self.record_signal_generated(
                signal_id=signal_id,
                symbol=symbol,
                magic=int(magic),
                signal_confidence=confidence,
                signal_strategy=strategy,
            )

        if stage_u == "PENDING_PLACED" and status_u == "SUCCESS":
            ticket = int(
                (details or {}).get("ticket")
                or (details or {}).get("order")
                or 0
            )
            return self.record_pending_order_placed(signal_id, ticket)

        if stage_u == "FILLED" and status_u == "SUCCESS":
            fill_price = float(
                (details or {}).get("price")
                or (details or {}).get("entry_price")
                or 0.0
            )
            fill_volume = float(
                (details or {}).get("volume")
                or (details or {}).get("lot_size")
                or 0.0
            )
            return self.record_order_filled(signal_id, fill_price, fill_volume)

        if stage_u == "CLOSE_PARTIAL" and status_u == "SUCCESS":
            close_price = float(
                (details or {}).get("close_price")
                or (details or {}).get("price")
                or 0.0
            )
            pnl = float(
                (details or {}).get("pnl")
                or (details or {}).get("profit")
                or 0.0
            )
            return self.record_position_partial_close(signal_id, close_price, pnl)

        if stage_u == "CLOSED" and status_u == "SUCCESS":
            close_price = float(
                (details or {}).get("close_price")
                or (details or {}).get("price")
                or 0.0
            )
            pnl = float(
                (details or {}).get("pnl")
                or (details or {}).get("profit")
                or 0.0
            )
            return self.record_position_closed(signal_id, close_price, pnl)

        return None

    def save_json(self, file_path: Optional[str] = None) -> int:
        path = Path(file_path or self.history_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        records = list(self.records.values())[-self.max_records :]
        with path.open("w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2)
        return len(records)

    def save_csv(self, file_path: Optional[str] = None) -> int:
        path = Path(file_path or self.csv_file)
        path.parent.mkdir(parents=True, exist_ok=True)

        rows = list(self.records.values())[-self.max_records :]
        if not rows:
            return 0

        fields = [
            "signal_id",
            "symbol",
            "magic",
            "signal_time",
            "signal_confidence",
            "signal_strategy",
            "pending_order_time",
            "pending_order_ticket",
            "fill_time",
            "fill_price",
            "fill_volume",
            "close_time",
            "close_price",
            "pnl",
            "stages",
        ]

        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                out = dict(row)
                out["stages"] = json.dumps(out.get("stages", {}), separators=(",", ":"))
                writer.writerow(out)

        return len(rows)

    def load_json(self, file_path: Optional[str] = None) -> int:
        path = Path(file_path or self.history_file)
        if not path.exists():
            return 0

        with path.open("r", encoding="utf-8") as fh:
            payload = json.load(fh)

        self.records = {}
        for item in payload or []:
            sid = str(item.get("signal_id", ""))
            if sid:
                self.records[sid] = item
                symbol = str(item.get("symbol", ""))
                if symbol:
                    self.latest_signal_by_symbol[symbol] = sid

        return len(self.records)

    def summarize(self) -> Dict:
        total = len(self.records)
        closed = sum(1 for r in self.records.values() if bool(r.get("stages", {}).get("closed")))
        filled = sum(1 for r in self.records.values() if bool(r.get("stages", {}).get("filled")))
        pending = sum(1 for r in self.records.values() if bool(r.get("stages", {}).get("pending_created")))
        partial = sum(1 for r in self.records.values() if bool(r.get("stages", {}).get("partially_closed")))

        return {
            "total_signals": int(total),
            "pending_created": int(pending),
            "filled": int(filled),
            "partial_closes": int(partial),
            "closed": int(closed),
            "fill_rate_percent": float((filled / total) * 100.0) if total > 0 else 0.0,
            "close_rate_percent": float((closed / total) * 100.0) if total > 0 else 0.0,
        }
