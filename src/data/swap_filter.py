"""
APEX FX Trading Bot - Swap Filter
PRD Volume II Section 19: Swap/Rollover Protection

Before entries within 2 hours of 22:00 UTC rollover, checks whether
expected profit covers rollover cost by at least 2x.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import threading


class SwapFilter:
    """
    Swap Filter - protects against rollover costs.
    
    Rules:
    - Rollover hour: 22:00 UTC
    - Check window: 2 hours before/after rollover
    - Affected instruments: GBPUSD, USDCHF (short-duration strategies)
    - Minimum profit to rollover ratio: 2.0x
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
            Tuple of (should_delay, reason)
        """
        with self._lock:
            # Only check affected instruments
            if symbol not in self.AFFECTED_INSTRUMENTS:
                return False, 'not_affected'
            
            # Check if within rollover window
            now = datetime.now(timezone.utc)
            
            # Get hours until rollover
            hours_until_rollover = self._hours_until_rollover(now)
            
            if hours_until_rollover > self.ROLLOVER_CHECK_WINDOW_HOURS:
                return False, 'outside_rollover_window'
            
            if hours_until_rollover < -self.ROLLOVER_CHECK_WINDOW_HOURS:
                return False, 'past_rollover_window'
            
            # Get swap cost
            swap_cost = self._get_swap_cost(symbol, direction, 1.0, mt5_connector)
            
            if swap_cost <= 0:
                return False, 'no_swap_cost'
            
            # Check if expected profit covers rollover by 2x
            expected_profit_value = expected_tp_pips * 10  # Simplified pip value
            
            ratio = expected_profit_value / abs(swap_cost) if swap_cost != 0 else 999
            
            if ratio < self.MIN_PROFIT_TO_ROLLOVER_RATIO:
                return True, f'profit_to_rollover_ratio_{ratio:.1f}_below_2.0'
            
            return False, 'rollover_check_passed'
    
    def _hours_until_rollover(self, now: datetime) -> float:
        """Calculate hours until next rollover."""
        rollover_time = now.replace(
            hour=self.ROLLOVER_UTC_HOUR,
            minute=0,
            second=0,
            microsecond=0
        )
        
        # If rollover has passed today, get next day's rollover
        if now.hour >= self.ROLLOVER_UTC_HOUR:
            rollover_time += timedelta(days=1)
        
        return (rollover_time - now).total_seconds() / 3600
    
    def _get_swap_cost(
        self,
        symbol: str,
        direction: str,
        lots: float,
        mt5_connector
    ) -> float:
        """
        Fetch and return the rollover cost in account currency for 1 lot.
        
        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            lots: Position size in lots
            mt5_connector: MT5 connector
            
        Returns:
            Rollover cost (negative for cost, positive for credit)
        """
        try:
            # Get symbol info which includes swap rates
            # In real implementation, would fetch from MT5
            # For now, use mock values
            swap_rates = {
                ('GBPUSD', 'BUY'): -3.5,
                ('GBPUSD', 'SELL'): 1.2,
                ('USDCHF', 'BUY'): -2.8,
                ('USDCHF', 'SELL'): 0.9,
            }
            
            swap_rate = swap_rates.get((symbol, direction.upper()), 0)
            
            # Swap is typically quoted per night, so multiply by expected hold nights
            # For H1 bar-based trading, assume 1 night
            return swap_rate * lots
            
        except Exception as e:
            if self._logger:
                self._logger.warning('swap_fetch_error', symbol=symbol, error=str(e))
            return 0.0
    
    def get_swap_rate(
        self,
        symbol: str,
        direction: str,
        mt5_connector
    ) -> Optional[float]:
        """
        Get raw swap rate for a symbol/direction.
        
        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            mt5_connector: MT5 connector
            
        Returns:
            Swap rate or None if unavailable
        """
        swap_rates = {
            ('GBPUSD', 'BUY'): -3.5,
            ('GBPUSD', 'SELL'): 1.2,
            ('USDCHF', 'BUY'): -2.8,
            ('USDCHF', 'SELL'): 0.9,
        }
        
        return swap_rates.get((symbol, direction.upper()))
    
    def is_within_rollover_window(self, now: Optional[datetime] = None) -> bool:
        """
        Check if currently within the rollover check window.
        
        Args:
            now: Optional datetime (defaults to now)
            
        Returns:
            True if within 2 hours of rollover
        """
        if now is None:
            now = datetime.now(timezone.utc)
        
        hours = self._hours_until_rollover(now)
        return abs(hours) <= self.ROLLOVER_CHECK_WINDOW_HOURS
    
    def get_rollover_time(self) -> datetime:
        """Get next rollover datetime."""
        now = datetime.now(timezone.utc)
        rollover = now.replace(
            hour=self.ROLLOVER_UTC_HOUR,
            minute=0,
            second=0,
            microsecond=0
        )
        
        if now.hour >= self.ROLLOVER_UTC_HOUR:
            rollover += timedelta(days=1)
        
        return rollover


# Global instance
_swap_filter = None


def get_swap_filter(config: Optional[Dict] = None, logger=None) -> SwapFilter:
    """Get global swap filter instance."""
    global _swap_filter
    if _swap_filter is None:
        _swap_filter = SwapFilter(config, logger)
    return _swap_filter