"""MT5 connector implementing the unified exchange connector interface."""

from __future__ import annotations

import time
from typing import Dict, List, Optional

from .base import ExchangeConnector

try:
    import MetaTrader5 as mt5
except Exception:  # pragma: no cover - runtime environment specific
    mt5 = None


class MT5Connector(ExchangeConnector):
    """Thin reliability wrapper around MetaTrader5 API."""

    _TF_MAP = {
        "M1": getattr(mt5, "TIMEFRAME_M1", 1) if mt5 else 1,
        "M5": getattr(mt5, "TIMEFRAME_M5", 5) if mt5 else 5,
        "M15": getattr(mt5, "TIMEFRAME_M15", 15) if mt5 else 15,
        "M30": getattr(mt5, "TIMEFRAME_M30", 30) if mt5 else 30,
        "H1": getattr(mt5, "TIMEFRAME_H1", 60) if mt5 else 60,
        "H4": getattr(mt5, "TIMEFRAME_H4", 240) if mt5 else 240,
        "D1": getattr(mt5, "TIMEFRAME_D1", 1440) if mt5 else 1440,
        "D": getattr(mt5, "TIMEFRAME_D1", 1440) if mt5 else 1440,
    }

    def __init__(self, path: Optional[str] = None, timeout: int = 5000, max_retries: int = 3, quote_ttl_seconds: float = 2.0):
        self.path = path
        self.timeout = int(timeout or 5000)
        self.max_retries = max(1, int(max_retries or 3))
        self.quote_ttl_seconds = max(0.1, float(quote_ttl_seconds or 2.0))

        self.connected = False
        self._last_error = ""
        self._last_tick_ts: Dict[str, float] = {}

    def initialize(self) -> bool:
        if mt5 is None:
            self.connected = False
            self._last_error = "MetaTrader5 package unavailable"
            return False

        kwargs = {"timeout": self.timeout}
        if self.path:
            kwargs["path"] = self.path

        for _ in range(self.max_retries):
            try:
                if mt5.initialize(**kwargs):
                    self.connected = True
                    self._last_error = ""
                    return True
            except Exception as exc:  # pragma: no cover - depends on terminal state
                self._last_error = str(exc)
            time.sleep(0.5)

        try:
            self._last_error = str(mt5.last_error())
        except Exception:
            pass
        self.connected = False
        return False

    def ensure_connection(self) -> bool:
        if mt5 is None:
            self.connected = False
            self._last_error = "MetaTrader5 package unavailable"
            return False

        try:
            info = mt5.terminal_info()
            if info is None:
                self.connected = False
                return self.initialize()
            self.connected = True
            return True
        except Exception as exc:  # pragma: no cover - terminal side effect
            self._last_error = str(exc)
            self.connected = False
            return self.initialize()

    def get_ticker(self, symbol: str) -> Optional[Dict]:
        if not symbol or not self.ensure_connection():
            return None

        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None

        tick_ts = float(getattr(tick, "time", 0.0) or 0.0)
        now = time.time()
        if tick_ts > 0 and (now - tick_ts) > self.quote_ttl_seconds:
            self._last_tick_ts[symbol] = tick_ts
            return None

        return {
            "bid": float(getattr(tick, "bid", 0.0) or 0.0),
            "ask": float(getattr(tick, "ask", 0.0) or 0.0),
            "timestamp": int(tick_ts or now),
            "exchange": "MT5",
            "symbol": str(symbol),
        }

    def get_ohlcv(self, symbol: str, timeframe: str, count: int) -> List[Dict]:
        if not symbol or count <= 0 or not self.ensure_connection():
            return []

        tf = self._TF_MAP.get(str(timeframe or "M15").upper(), self._TF_MAP["M15"])
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, int(count))
        if rates is None:
            return []

        candles: List[Dict] = []
        for row in rates:
            row_dict = dict(row)
            volume = float(row_dict.get("real_volume", 0.0) or 0.0)
            if volume <= 0:
                volume = float(row_dict.get("tick_volume", 0.0) or 0.0)
            candles.append({
                "time": int(row_dict.get("time", 0) or 0),
                "open": float(row_dict.get("open", 0.0) or 0.0),
                "high": float(row_dict.get("high", 0.0) or 0.0),
                "low": float(row_dict.get("low", 0.0) or 0.0),
                "close": float(row_dict.get("close", 0.0) or 0.0),
                "volume": volume,
            })
        return candles

    def place_order(self, order: Dict) -> str:
        if not isinstance(order, dict) or not self.ensure_connection():
            return ""

        symbol = str(order.get("symbol", "") or "")
        direction = str(order.get("direction", "BUY") or "BUY").upper()
        volume = float(order.get("volume", order.get("lot_size", 0.0)) or 0.0)
        if not symbol or volume <= 0:
            return ""

        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return ""
        if not bool(getattr(symbol_info, "visible", True)):
            mt5.symbol_select(symbol, True)

        order_type = mt5.ORDER_TYPE_BUY if direction == "BUY" else mt5.ORDER_TYPE_SELL
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return ""

        price = float(order.get("price", 0.0) or 0.0)
        if price <= 0:
            price = float(getattr(tick, "ask", 0.0) if direction == "BUY" else getattr(tick, "bid", 0.0))

        request = {
            "action": int(order.get("action", getattr(mt5, "TRADE_ACTION_DEAL", 1))),
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "price": price,
            "deviation": int(order.get("deviation", 20) or 20),
            "magic": int(order.get("magic", 202602) or 202602),
            "comment": str(order.get("comment", "SNIPER_CONNECTOR") or "SNIPER_CONNECTOR"),
            "type_time": int(order.get("type_time", getattr(mt5, "ORDER_TIME_GTC", 0))),
            "type_filling": int(order.get("type_filling", getattr(mt5, "ORDER_FILLING_IOC", 1))),
        }

        sl = float(order.get("sl", order.get("stop_loss", 0.0)) or 0.0)
        tp = float(order.get("tp", order.get("take_profit", 0.0)) or 0.0)
        if sl > 0:
            request["sl"] = sl
        if tp > 0:
            request["tp"] = tp

        try:
            result = mt5.order_send(request)
        except Exception as exc:  # pragma: no cover
            self._last_error = str(exc)
            return ""

        if result is None:
            self._last_error = str(mt5.last_error())
            return ""

        retcode = int(getattr(result, "retcode", 0) or 0)
        done_codes = {
            int(getattr(mt5, "TRADE_RETCODE_DONE", 10009)),
            int(getattr(mt5, "TRADE_RETCODE_PLACED", 10008)),
        }
        if retcode not in done_codes:
            self._last_error = str(retcode)
            return ""

        order_id = int(getattr(result, "order", 0) or 0)
        if order_id <= 0:
            order_id = int(getattr(result, "deal", 0) or 0)
        return str(order_id) if order_id > 0 else ""

    def cancel_order(self, order_id: str) -> bool:
        if not self.ensure_connection():
            return False

        try:
            oid = int(order_id)
        except Exception:
            return False

        request = {
            "action": int(getattr(mt5, "TRADE_ACTION_REMOVE", 8)),
            "order": oid,
        }

        try:
            result = mt5.order_send(request)
        except Exception as exc:  # pragma: no cover
            self._last_error = str(exc)
            return False

        if result is None:
            self._last_error = str(mt5.last_error())
            return False

        retcode = int(getattr(result, "retcode", 0) or 0)
        return retcode == int(getattr(mt5, "TRADE_RETCODE_DONE", 10009))

    def get_positions(self) -> List[Dict]:
        if not self.ensure_connection():
            return []

        positions = mt5.positions_get() or []
        buy_type = int(getattr(mt5, "POSITION_TYPE_BUY", 0))
        payload: List[Dict] = []
        for pos in positions:
            pos_type = int(getattr(pos, "type", 0) or 0)
            payload.append({
                "ticket": int(getattr(pos, "ticket", 0) or 0),
                "symbol": str(getattr(pos, "symbol", "") or ""),
                "direction": "BUY" if pos_type == buy_type else "SELL",
                "volume": float(getattr(pos, "volume", 0.0) or 0.0),
                "price_open": float(getattr(pos, "price_open", 0.0) or 0.0),
                "price_current": float(getattr(pos, "price_current", 0.0) or 0.0),
                "profit": float(getattr(pos, "profit", 0.0) or 0.0),
            })
        return payload

    def get_account_info(self) -> Dict:
        if not self.ensure_connection():
            return {"connected": False, "balance": 0.0, "equity": 0.0}

        info = mt5.account_info()
        if info is None:
            return {"connected": False, "balance": 0.0, "equity": 0.0}

        return {
            "connected": True,
            "balance": float(getattr(info, "balance", 0.0) or 0.0),
            "equity": float(getattr(info, "equity", 0.0) or 0.0),
            "margin": float(getattr(info, "margin", 0.0) or 0.0),
            "free_margin": float(getattr(info, "margin_free", 0.0) or 0.0),
            "currency": str(getattr(info, "currency", "") or ""),
        }

    def health(self) -> Dict:
        now = time.time()
        stale_map = {
            symbol: max(0.0, now - tick_ts)
            for symbol, tick_ts in self._last_tick_ts.items()
        }
        last_error = self._last_error
        if mt5 is not None:
            try:
                last_error = str(mt5.last_error())
            except Exception:
                pass

        return {
            "connected": bool(self.connected),
            "quote_ttl_seconds": self.quote_ttl_seconds,
            "quotes_stale_seconds": stale_map,
            "last_error": last_error,
        }
