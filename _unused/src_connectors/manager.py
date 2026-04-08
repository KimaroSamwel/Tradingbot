"""Connector manager with primary/fallback routing for data and execution."""

from __future__ import annotations

from typing import Dict, List, Optional


class ConnectorManager:
    """Routes requests across registered connectors with fallback behavior."""

    def __init__(
        self,
        config: Optional[Dict] = None,
    ):
        cfg = config or {}
        self.connectors: Dict[str, object] = {}
        self.primary_data = str(cfg.get("primary_data_connector", "MT5") or "MT5")
        self.primary_execution = str(cfg.get("primary_execution_connector", "MT5") or "MT5")
        self.fallback_enabled = bool(cfg.get("fallback_enabled", True))
        self.use_for_execution = bool(cfg.get("use_for_execution", False))

    def register(self, name: str, connector: object) -> bool:
        key = str(name or "").strip().upper()
        if not key or connector is None:
            return False
        if not hasattr(connector, "get_ticker"):
            return False
        self.connectors[key] = connector
        return True

    def unregister(self, name: str) -> None:
        key = str(name or "").strip().upper()
        if key:
            self.connectors.pop(key, None)

    def get(self, name: str) -> Optional[object]:
        key = str(name or "").strip().upper()
        if not key:
            return None
        return self.connectors.get(key)

    def list_connectors(self) -> List[str]:
        return sorted(self.connectors.keys())

    def _iter_sources(self, preferred: Optional[str]) -> List[str]:
        if preferred:
            pref_key = str(preferred).strip().upper()
            if pref_key in self.connectors:
                return [pref_key]
            return []

        ordered: List[str] = []
        primary = str(self.primary_data or "").strip().upper()
        if primary and primary in self.connectors:
            ordered.append(primary)

        if self.fallback_enabled:
            for name in self.connectors:
                if name not in ordered:
                    ordered.append(name)

        return ordered

    def get_ticker(self, symbol: str, source: Optional[str] = None) -> Optional[Dict]:
        for name in self._iter_sources(source):
            connector = self.connectors.get(name)
            if connector is None:
                continue
            try:
                quote = connector.get_ticker(symbol)
            except Exception:
                continue
            if quote:
                return quote
        return None

    def get_ohlcv(self, symbol: str, timeframe: str, count: int, source: Optional[str] = None) -> List[Dict]:
        for name in self._iter_sources(source):
            connector = self.connectors.get(name)
            if connector is None or not hasattr(connector, "get_ohlcv"):
                continue
            try:
                rows = connector.get_ohlcv(symbol, timeframe, count)
            except Exception:
                continue
            if rows:
                return rows
        return []

    def place_order(self, order: Dict, executor: Optional[str] = None) -> str:
        conn_name = str(executor or self.primary_execution or "").strip().upper()
        connector = self.connectors.get(conn_name)
        if connector is None or not hasattr(connector, "place_order"):
            return ""
        try:
            return str(connector.place_order(order) or "")
        except Exception:
            return ""

    def cancel_order(self, order_id: str, executor: Optional[str] = None) -> bool:
        conn_name = str(executor or self.primary_execution or "").strip().upper()
        connector = self.connectors.get(conn_name)
        if connector is None or not hasattr(connector, "cancel_order"):
            return False
        try:
            return bool(connector.cancel_order(order_id))
        except Exception:
            return False

    def get_positions(self, source: Optional[str] = None) -> List[Dict]:
        name = str(source or self.primary_execution or "").strip().upper()
        connector = self.connectors.get(name)
        if connector is None or not hasattr(connector, "get_positions"):
            return []
        try:
            rows = connector.get_positions()
        except Exception:
            return []
        return rows if isinstance(rows, list) else []

    def get_account_info(self, source: Optional[str] = None) -> Dict:
        name = str(source or self.primary_execution or "").strip().upper()
        connector = self.connectors.get(name)
        if connector is None or not hasattr(connector, "get_account_info"):
            return {}
        try:
            payload = connector.get_account_info()
        except Exception:
            return {}
        return payload if isinstance(payload, dict) else {}

    def health(self) -> Dict:
        snapshot: Dict[str, Dict] = {}
        for name, connector in self.connectors.items():
            if not hasattr(connector, "health"):
                snapshot[name] = {"available": False}
                continue
            try:
                payload = connector.health()
                snapshot[name] = payload if isinstance(payload, dict) else {"available": True}
            except Exception as exc:
                snapshot[name] = {"available": False, "error": str(exc)}

        return {
            "primary_data_connector": self.primary_data,
            "primary_execution_connector": self.primary_execution,
            "fallback_enabled": self.fallback_enabled,
            "registered": sorted(snapshot.keys()),
            "connectors": snapshot,
        }
