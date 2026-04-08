"""V2 strategy controllers inspired by Hummingbot-style architecture."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

import pandas as pd

from src.execution.position_executor import PositionExecutor


@dataclass
class ControllerSignal:
    symbol: str
    signal: int  # 1 long, -1 short, 0 neutral
    confidence: float
    strategy: str
    timestamp: datetime
    meta: Dict


class CandleProvider:
    """Simple candle provider abstraction for controller backends."""

    def __init__(self, candles_exchange: str = "MT5"):
        self.candles_exchange = candles_exchange

    def get_candles(self, symbol: str, timeframe: str = "M15", limit: int = 300) -> pd.DataFrame:
        raise NotImplementedError("Inject your candle source (MT5/websocket) at runtime")


class DirectionalTradingController:
    """Base class for directional strategy controllers."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.config = cfg
        self.candles_provider = CandleProvider(cfg.get("candles_exchange", "MT5"))
        self.position_executors = []
        self.max_executors = int(cfg.get("max_executors", 5) or 5)
        self.cooldown_time = int(cfg.get("cooldown_time", 15) or 15)
        self._last_signal_time: Dict[str, datetime] = {}

    def get_processed_data(self, symbol: str, candles: pd.DataFrame) -> ControllerSignal:
        raise NotImplementedError

    def _cooldown_active(self, symbol: str) -> bool:
        last = self._last_signal_time.get(symbol)
        if last is None:
            return False
        return datetime.now() < last + timedelta(minutes=self.cooldown_time)

    def create_executor(self, signal: ControllerSignal, amount_usd: float) -> Optional[PositionExecutor]:
        if signal.signal == 0:
            return None
        if len(self.position_executors) >= self.max_executors:
            return None
        if self._cooldown_active(signal.symbol):
            return None

        cfg = self.config.get("position_executor", {})
        executor = PositionExecutor(cfg)
        self.position_executors.append(executor)
        self._last_signal_time[signal.symbol] = datetime.now()
        return executor


class MarketMakingController:
    """Base class for market-making style controllers."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.config = cfg
        self.mid_price = None
        self.bid_spread = float(cfg.get("bid_spread", 0.001) or 0.001)
        self.ask_spread = float(cfg.get("ask_spread", 0.001) or 0.001)
        self.order_refresh_time = int(cfg.get("order_refresh_time", 30) or 30)

    def update_mid_price(self, bid: float, ask: float) -> float:
        self.mid_price = (float(bid) + float(ask)) / 2.0
        return self.mid_price

    def generate_quotes(self, volatility_multiplier: float = 1.0) -> Dict[str, float]:
        if self.mid_price is None:
            return {}
        bid_price = self.mid_price * (1.0 - (self.bid_spread * volatility_multiplier))
        ask_price = self.mid_price * (1.0 + (self.ask_spread * volatility_multiplier))
        return {"bid": bid_price, "ask": ask_price}
