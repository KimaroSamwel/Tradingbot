"""Direct Deriv WebSocket connector (quotes + account + lightweight execution primitives)."""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .base import ExchangeConnector

try:
    import websocket
except Exception:  # pragma: no cover - optional dependency
    websocket = None


class DerivConnector(ExchangeConnector):
    """Synchronous request/response wrapper over Deriv websocket API."""

    def __init__(
        self,
        api_token_env: str = "DERIV_API_TOKEN",
        app_id_env: str = "DERIV_APP_ID",
        app_id: str = "",
        account_mode_env: str = "DERIV_ACCOUNT_MODE",
        account_mode: str = "AUTO",
        demo_token_env: str = "DERIV_API_TOKEN_DEMO",
        real_token_env: str = "DERIV_API_TOKEN_REAL",
        endpoint: str = "wss://ws.derivws.com/websockets/v3",
        quote_ttl_seconds: float = 1.0,
        request_timeout_seconds: float = 2.0,
    ):
        self.api_token_env = str(api_token_env or "DERIV_API_TOKEN")
        self.app_id_env = str(app_id_env or "DERIV_APP_ID")
        self.app_id = str(app_id or "").strip()
        self.account_mode_env = str(account_mode_env or "DERIV_ACCOUNT_MODE")
        self.account_mode = str(account_mode or "AUTO").strip().upper()
        self.demo_token_env = str(demo_token_env or "DERIV_API_TOKEN_DEMO")
        self.real_token_env = str(real_token_env or "DERIV_API_TOKEN_REAL")
        self.endpoint = self._resolve_endpoint(endpoint)
        self.quote_ttl_seconds = max(0.1, float(quote_ttl_seconds or 1.0))
        self.request_timeout_seconds = max(0.5, float(request_timeout_seconds or 2.0))

        self.ws = None
        self.connected = False
        self._authorized = False
        self._lock = threading.Lock()
        self._req_id = 0
        self._last_error = ""
        self._tick_cache: Dict[str, Dict] = {}
        self._active_account_mode = self._resolve_account_mode()
        self._active_token_env = self.api_token_env

    def _resolve_endpoint(self, endpoint: str) -> str:
        """Attach app_id query param when configured (required by Deriv docs)."""
        base = str(endpoint or "wss://ws.derivws.com/websockets/v3").strip()
        app_id = str(self.app_id or os.getenv(self.app_id_env, "") or "").strip()
        if not app_id:
            return base

        try:
            parsed = urlparse(base)
            query = dict(parse_qsl(parsed.query, keep_blank_values=True))
            if not str(query.get("app_id", "") or "").strip():
                query["app_id"] = app_id
            return urlunparse(parsed._replace(query=urlencode(query)))
        except Exception:
            if "app_id=" in base:
                return base
            separator = "&" if "?" in base else "?"
            return f"{base}{separator}app_id={app_id}"

    def _resolve_account_mode(self) -> str:
        """Normalize account mode labels from config/env/account ids."""
        raw = str(self.account_mode or os.getenv(self.account_mode_env, "") or "AUTO").strip().upper()
        if not raw:
            return "AUTO"

        if raw.startswith("VRTC") or raw in {"DEMO", "VIRTUAL", "PRACTICE", "TEST"}:
            return "DEMO"
        if raw.startswith("CR") or raw in {"REAL", "LIVE", "PROD", "PRODUCTION"}:
            return "REAL"
        return "AUTO"

    def _resolve_authorization_token(self) -> Tuple[str, str, str]:
        """Resolve token with backward-compatible priority + safe demo-first auto fallback."""
        direct = str(os.getenv(self.api_token_env, "") or "").strip()
        if direct:
            return direct, self.api_token_env, "DIRECT"

        mode = self._resolve_account_mode()
        if mode == "DEMO":
            candidates = [self.demo_token_env]
        elif mode == "REAL":
            candidates = [self.real_token_env]
        else:
            # Safer default when both are configured.
            candidates = [self.demo_token_env, self.real_token_env]

        for env_name in candidates:
            token = str(os.getenv(env_name, "") or "").strip()
            if token:
                return token, env_name, mode

        fallback_env = candidates[0] if candidates else self.api_token_env
        return "", fallback_env, mode

    def _reset_connection(self) -> None:
        try:
            if self.ws is not None:
                self.ws.close()
        except Exception:
            pass
        self.ws = None
        self.connected = False

    def _next_req_id(self) -> int:
        with self._lock:
            self._req_id += 1
            return self._req_id

    def _connect(self) -> bool:
        if websocket is None:
            self._last_error = "websocket-client package unavailable"
            self.connected = False
            return False

        if self.ws is not None and self.connected:
            return True

        if self.ws is not None and not self.connected:
            self._reset_connection()

        try:
            self.ws = websocket.create_connection(self.endpoint, timeout=self.request_timeout_seconds)
            self.connected = True
            return True
        except Exception as exc:  # pragma: no cover - network environment specific
            self._last_error = str(exc)
            self._reset_connection()
            return False

    def _authorize(self) -> bool:
        token, token_env, mode = self._resolve_authorization_token()
        self._active_token_env = token_env
        self._active_account_mode = mode
        if not token:
            # Allow quote-only public usage without auth.
            self._authorized = False
            return True

        response = self._send_request({"authorize": token}, require_response=True)
        ok = bool(response and "error" not in response and response.get("authorize"))
        self._authorized = ok
        if not ok:
            self._last_error = str(response.get("error", "authorize_failed") if isinstance(response, dict) else "authorize_failed")
        return ok

    def initialize(self) -> bool:
        if not self._connect():
            return False
        return self._authorize()

    def _send_request(self, payload: Dict, require_response: bool = True) -> Dict:
        if (not self.connected or self.ws is None) and not self._connect():
            return {}

        req_id = self._next_req_id()
        message = dict(payload or {})
        message["req_id"] = req_id

        with self._lock:
            try:
                self.ws.send(json.dumps(message))
            except Exception as exc:
                self._last_error = str(exc)
                self._reset_connection()
                return {}

        if not require_response:
            return {"ok": True, "req_id": req_id}

        deadline = time.time() + self.request_timeout_seconds
        while time.time() < deadline:
            try:
                raw = self.ws.recv()
            except Exception as exc:
                self._last_error = str(exc)
                self._reset_connection()
                return {}

            try:
                response = json.loads(raw)
            except Exception:
                continue

            if "tick" in response and isinstance(response.get("tick"), dict):
                tick = response["tick"]
                symbol = str(tick.get("symbol", "") or "")
                quote = float(tick.get("quote", 0.0) or 0.0)
                epoch = int(tick.get("epoch", int(time.time())) or int(time.time()))
                if symbol:
                    self._tick_cache[symbol] = {
                        "bid": quote,
                        "ask": quote,
                        "timestamp": epoch,
                        "exchange": "DERIV",
                        "symbol": symbol,
                    }

            if int(response.get("req_id", -1) or -1) == req_id:
                return response

        self._last_error = f"timeout waiting req_id={req_id}"
        self._reset_connection()
        return {}

    def get_ticker(self, symbol: str) -> Optional[Dict]:
        symbol = str(symbol or "").strip()
        if not symbol:
            return None

        cached = self._tick_cache.get(symbol)
        now = time.time()
        if cached is not None:
            age = now - float(cached.get("timestamp", now) or now)
            if age <= self.quote_ttl_seconds:
                return dict(cached)

        response = self._send_request({"ticks": symbol, "subscribe": 0}, require_response=True)
        if not response:
            return None

        tick = response.get("tick")
        if not isinstance(tick, dict):
            return None

        quote = float(tick.get("quote", 0.0) or 0.0)
        epoch = int(tick.get("epoch", int(now)) or int(now))
        payload = {
            "bid": quote,
            "ask": quote,
            "timestamp": epoch,
            "exchange": "DERIV",
            "symbol": symbol,
        }
        self._tick_cache[symbol] = payload
        return payload

    def get_ohlcv(self, symbol: str, timeframe: str, count: int) -> List[Dict]:
        symbol = str(symbol or "").strip()
        if not symbol or count <= 0:
            return []

        granularity_map = {
            "M1": 60,
            "M5": 300,
            "M15": 900,
            "M30": 1800,
            "H1": 3600,
            "H4": 14400,
            "D": 86400,
            "D1": 86400,
        }
        granularity = granularity_map.get(str(timeframe or "M15").upper(), 900)

        response = self._send_request({
            "ticks_history": symbol,
            "style": "candles",
            "granularity": granularity,
            "count": int(count),
            "end": "latest",
        })
        candles = response.get("candles") if isinstance(response, dict) else None
        if not isinstance(candles, list):
            return []

        payload: List[Dict] = []
        for candle in candles:
            if not isinstance(candle, dict):
                continue
            payload.append({
                "time": int(candle.get("epoch", 0) or 0),
                "open": float(candle.get("open", 0.0) or 0.0),
                "high": float(candle.get("high", 0.0) or 0.0),
                "low": float(candle.get("low", 0.0) or 0.0),
                "close": float(candle.get("close", 0.0) or 0.0),
                "volume": float(candle.get("volume", 0.0) or 0.0),
            })
        return payload

    def place_order(self, order: Dict) -> str:
        """Minimal execution primitive; currently supports direct passthrough payloads."""
        if not isinstance(order, dict):
            return ""

        # Keep safe default behavior until execution mapping is fully validated.
        passthrough = order.get("deriv_request")
        if not isinstance(passthrough, dict):
            self._last_error = "deriv execution requires order['deriv_request'] payload"
            return ""

        response = self._send_request(passthrough, require_response=True)
        if not response or "error" in response:
            self._last_error = str(response.get("error", "deriv_order_failed") if isinstance(response, dict) else "deriv_order_failed")
            return ""

        buy = response.get("buy")
        if isinstance(buy, dict):
            contract_id = int(buy.get("contract_id", 0) or 0)
            if contract_id > 0:
                return str(contract_id)

        order_id = int(response.get("order_id", 0) or 0)
        return str(order_id) if order_id > 0 else ""

    def cancel_order(self, order_id: str) -> bool:
        try:
            cid = int(order_id)
        except Exception:
            return False

        response = self._send_request({"sell": cid, "price": 0}, require_response=True)
        return bool(response and "error" not in response)

    def get_positions(self) -> List[Dict]:
        response = self._send_request({"portfolio": 1}, require_response=True)
        portfolio = response.get("portfolio") if isinstance(response, dict) else None
        contracts = portfolio.get("contracts") if isinstance(portfolio, dict) else None
        if not isinstance(contracts, list):
            return []

        positions: List[Dict] = []
        for contract in contracts:
            if not isinstance(contract, dict):
                continue
            positions.append({
                "ticket": int(contract.get("contract_id", 0) or 0),
                "symbol": str(contract.get("display_name", contract.get("symbol", "")) or ""),
                "direction": str(contract.get("contract_type", "") or ""),
                "volume": float(contract.get("buy_price", 0.0) or 0.0),
                "price_open": float(contract.get("buy_price", 0.0) or 0.0),
                "price_current": float(contract.get("current_spot", 0.0) or 0.0),
                "profit": float(contract.get("profit", 0.0) or 0.0),
            })
        return positions

    def get_account_info(self) -> Dict:
        response = self._send_request({"balance": 1}, require_response=True)
        balance = response.get("balance") if isinstance(response, dict) else None
        if not isinstance(balance, dict):
            return {"connected": bool(self.connected), "balance": 0.0, "equity": 0.0}

        value = float(balance.get("balance", 0.0) or 0.0)
        currency = str(balance.get("currency", "USD") or "USD")
        return {
            "connected": bool(self.connected),
            "balance": value,
            "equity": value,
            "currency": currency,
        }

    def health(self) -> Dict:
        now = time.time()
        stale_seconds = {
            symbol: max(0.0, now - float(payload.get("timestamp", now) or now))
            for symbol, payload in self._tick_cache.items()
        }
        token, _, _ = self._resolve_authorization_token()
        return {
            "connected": bool(self.connected),
            "authorized": bool(self._authorized),
            "last_error": self._last_error,
            "quote_ttl_seconds": self.quote_ttl_seconds,
            "quotes_stale_seconds": stale_seconds,
            "endpoint": self.endpoint,
            "app_id_env": self.app_id_env,
            "app_id_configured": bool(str(self.app_id or os.getenv(self.app_id_env, "") or "").strip()),
            "api_token_env": self.api_token_env,
            "active_token_env": self._active_token_env,
            "token_configured": bool(str(token or "").strip()),
            "account_mode": self._active_account_mode,
            "account_mode_env": self.account_mode_env,
            "demo_token_env": self.demo_token_env,
            "real_token_env": self.real_token_env,
        }
