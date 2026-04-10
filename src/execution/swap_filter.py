"""
APEX FX Trading Bot - Swap Filter
PRD Volume II Section 16: Swap/Rollover Protection

Before entries within 2 hours of 22:00 UTC rollover, checks whether
expected profit covers rollover cost by at least 2x.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import threading


class SwapFilter:
    """
    Swap Filter - enforces rollover protection rules.
    
    Rules:
    - Rollover occurs at 22:00 UTC
    - Check window: 2 hours before/after rollover
    - Affected instruments: GBPUSD, USDCHF (short-duration strategies)
    - Minimum profit-to-rollover ratio: 2.0x
    """
    
    ROLLOVER_UTC_HOUR = 22
    ROLLOVER_CHECK_WINDOW_HOURS = 2
    AFFECTED_INSTRUMENTS = ['GBPUSD', 'USDCHF']
    MIN_PROFIT_TO_ROLLOVER_RATIO = 2.0
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize swap filter.
        
        Args:
            config: Optional configuration
            logger: Optional logger
        """
        self._lock = threading.Lock()
        self._config = config or {}
        self._logger = logger
    
    def should_delay_entry(
        self,
        symbol: str,
        direction: str,
        expected_tp_pips: float,
        mt5_connector
    ) -> Tuple[bool, str]:
        """
        Returns (should_delay, reason).
        
        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            expected_tp_pips: Expected take-profit in pips
            mt5_connector: MT5 connector for fetching swap rates
            
        Returns:
            Tuple of (should_delay: bool, reason: str)
        """
        with self._lock:
            if symbol not in self.AFFECTED_INSTRUMENTS:
                return False, 'symbol_not_affected'
            
            now_utc = datetime.now(timezone.utc)
            
            if not self._is_within_rollover_window(now_utc):
                return False, 'outside_rollover_window'
            
            swap_cost = self._get_swap_cost(symbol, direction, 1.0, mt5_connector)
            
            if swap_cost <= 0:
                return False, 'no_swap_cost'
            
            expected_profit_pips = expected_tp_pips
            ratio = expected_profit_pips / abs(swap_cost) if swap_cost != 0 else 999
            
            if ratio < self.MIN_PROFIT_TO_ROLLOVER_RATIO:
                return True, f'profit_to_swap_ratio_{ratio:.1f}_below_2.0'
            
            return False, 'ratio_acceptable'
    
    def _is_within_rollover_window(self, now_utc: datetime) -> bool:
        """
        Check if current time is within 2 hours of rollover.
        
        Args:
            now_utc: Current UTC datetime
            
        Returns:
            True if within rollover window
        """
        hour = now_utc.hour
        return (self.ROLLOVER_UTC_HOUR - self.ROLLOVER_CHECK_WINDOW_HOURS <= hour <= self.ROLLOVER_UTC_HOUR + self.ROLLOVER_CHECK_WINDOW_HOURS)
    
    def _get_swap_cost(
        self,
        symbol: str,
        direction: str,
        lots: float,
        mt5_connector
    ) -> float:
        """
        Fetch and return the rollover cost in pips for 1 lot.
        
        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            lots: Number of lots
            mt5_connector: MT5 connector
            
        Returns:
            Rollover cost in pips (negative = cost, positive = credit)
        """
        try:
            symbol_info = mt5_connector.get_symbol_info(symbol)
            if not symbol_info:
                return 0.0
            
            if direction == 'BUY':
                swap = getattr(symbol_info, 'swap_long', 0)
            else:
                swap = getattr(symbol_info, 'swap_short', 0)
            
            return swap * lots
        except Exception:
            return 0.0
    
    def is_affected_symbol(self, symbol: str) -> bool:
        """Check if symbol is affected by swap rules."""
        return symbol in self.AFFECTED_INSTRUMENTS
    
    def get_rollover_window_hours(self) -> Tuple[int, int]:
        """Get the start and end hours of rollover window."""
        start = self.ROLLOVER_UTC_HOUR - self.ROLLOVER_CHECK_WINDOW_HOURS
        end = self.ROLLOVER_UTC_HOUR + self.ROLLOVER_CHECK_WINDOW_HOURS
        return (start, end)


# Global instance
_swap_filter = None


def get_swap_filter(config: Optional[Dict] = None, logger=None) -> SwapFilter:
    """Get global swap filter instance."""
    global _swap_filter
    if _swap_filter is None:
        _swap_filter = SwapFilter(config, logger)
    return _swap_filter
