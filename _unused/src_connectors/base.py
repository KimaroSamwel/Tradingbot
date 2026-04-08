"""Unified exchange connector interface for data and execution backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class ExchangeConnector(ABC):
    """Common contract for all exchange/broker connectors."""

    @abstractmethod
    def initialize(self) -> bool:
        """Initialize transport/session resources."""

    @abstractmethod
    def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Return latest quote payload for symbol."""

    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, count: int) -> List[Dict]:
        """Return OHLCV candles for symbol/timeframe."""

    @abstractmethod
    def place_order(self, order: Dict) -> str:
        """Place an order and return provider order id (empty string on failure)."""

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an existing order."""

    @abstractmethod
    def get_positions(self) -> List[Dict]:
        """Return currently open positions."""

    @abstractmethod
    def get_account_info(self) -> Dict:
        """Return account state (balance/equity/etc)."""

    @abstractmethod
    def health(self) -> Dict:
        """Return connector health and diagnostics."""
