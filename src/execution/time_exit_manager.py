"""
APEX FX Trading Bot - Time Exit Manager
PRD Volume II Section 16: Time-Based Exit Rules

Enforces maximum hold times, forward progress rule, and weekend
position policy on every bar iteration.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import threading


class TimeExitManager:
    """
    Time Exit Manager - enforces time-based exit rules.
    
    Max hold hours per strategy:
    - EURUSD: trend 36h, breakout 36h
    - GBPUSD: momentum 18h, fibonacci 18h
    - USDJPY: carry 48h
    - USDCHF: mean_reversion 12h
    - USDCAD: oil_trend 36h
    - XAUUSD: trend 72h, breakout 72h
    
    Forward progress rule:
    - < 0.3x ATR movement toward TP = no progress
    - After FORWARD_PROGRESS_HOURS_WARN (6h): move SL to breakeven
    - After FORWARD_PROGRESS_HOURS_EXIT (10h): close at market
    
    XAU special: 12h warn, 18h exit
    
    Weekend policy (Friday >= 20:00 UTC):
    - Close all losing positions
    - Tighten profitable trailing stops to 0.5x ATR
    - Only hold through weekend if profit >= 1.0x ATR AND trailing active
    """
    
    MAX_HOLD_HOURS = {
        'EURUSD': {'trend': 36, 'breakout': 36},
        'GBPUSD': {'momentum': 18, 'fibonacci': 18},
        'USDJPY': {'carry': 48},
        'USDCHF': {'mean_reversion': 12},
        'USDCAD': {'oil_trend': 36},
        'XAUUSD': {'trend': 72, 'breakout': 72},
    }
    
    FORWARD_PROGRESS_ATR_THRESHOLD = 0.3
    FORWARD_PROGRESS_HOURS_WARN = 6
    FORWARD_PROGRESS_HOURS_EXIT = 10
    XAU_FORWARD_HOURS_WARN = 12
    XAU_FORWARD_HOURS_EXIT = 18
    
    WEEKEND_CLOSE_HOUR = 20
    WEEKEND_DAY = 4  # Friday
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize time exit manager.
        
        Args:
            config: Optional configuration
            logger: Optional logger
        """
        self._lock = threading.Lock()
        self._config = config or {}
        self._logger = logger
        
        # Track position entry times
        self._entry_times: Dict[int, datetime] = {}
    
    def check_all_positions(
        self,
        positions: List[Dict],
        atr_map: Dict[str, float],
        mt5_connector,
        order_router
    ) -> List[str]:
        """
        Called on every H1 bar close.
        
        Args:
            positions: List of open positions
            atr_map: Dict mapping symbol to ATR value
            mt5_connector: MT5 connector
            order_router: Order router for closing/modifying
            
        Returns:
            List of actions taken (for logging)
        """
        actions = []
        now_utc = datetime.now(timezone.utc)
        
        with self._lock:
            for pos in positions:
                ticket = pos.get('ticket')
                symbol = pos.get('symbol', '')
                strategy = pos.get('strategy', 'trend')
                
                # Check max hold time
                if self._check_max_hold(pos, now_utc):
                    success, msg = order_router.close_position(ticket)
                    actions.append(f"max_hold_exit:{symbol}:{msg}")
                    continue
                
                # Check forward progress
                atr14 = atr_map.get(symbol, 0)
                if atr14 > 0:
                    progress_action = self._check_forward_progress(
                        pos, atr14, now_utc, order_router
                    )
                    if progress_action:
                        actions.append(f"forward_progress:{symbol}:{progress_action}")
            
            # Check weekend policy
            if now_utc.weekday() == self.WEEKEND_DAY and now_utc.hour >= self.WEEKEND_CLOSE_HOUR:
                weekend_actions = self.apply_weekend_policy(positions, atr_map, order_router)
                actions.extend(weekend_actions)
        
        return actions
    
    def _check_max_hold(self, position: Dict, now_utc: datetime) -> bool:
        """Return True if position has exceeded its max hold time."""
        ticket = position.get('ticket')
        symbol = position.get('symbol', '')
        strategy = position.get('strategy', 'trend')
        
        # Get entry time
        if ticket not in self._entry_times:
            # First time seeing this position - record entry time
            self._entry_times[ticket] = now_utc
            return False
        
        entry_time = self._entry_times[ticket]
        hours_held = (now_utc - entry_time).total_seconds() / 3600
        
        # Get max hours for this symbol/strategy
        max_hours = self.MAX_HOLD_HOURS.get(symbol, {}).get(strategy, 24)
        
        return hours_held >= max_hours
    
    def _check_forward_progress(
        self,
        position: Dict,
        atr14: float,
        now_utc: datetime,
        order_router
    ) -> Optional[str]:
        """
        If price has not moved > 0.3x ATR toward TP since entry:
        - After WARN hours: move SL to breakeven
        - After EXIT hours: close position at market
        """
        ticket = position.get('ticket')
        symbol = position.get('symbol', '')
        direction = position.get('type', '')
        entry_price = position.get('price_open', 0)
        current_price = position.get('price_current', 0)
        tp_price = position.get('tp', 0)
        
        if entry_price <= 0 or tp_price <= 0:
            return None
        
        # Get entry time
        entry_time = self._entry_times.get(ticket)
        if not entry_time:
            return None
        
        hours_held = (now_utc - entry_time).total_seconds() / 3600
        
        # Check if we're past warning threshold
        is_xau = 'XAU' in symbol
        warn_hours = self.XAU_FORWARD_HOURS_WARN if is_xau else self.FORWARD_PROGRESS_HOURS_WARN
        exit_hours = self.XAU_FORWARD_HOURS_EXIT if is_xau else self.FORWARD_PROGRESS_HOURS_EXIT
        
        # Calculate progress toward TP
        if direction == 'BUY':
            total_distance = tp_price - entry_price
            current_progress = current_price - entry_price
        else:
            total_distance = entry_price - tp_price
            current_progress = entry_price - current_price
        
        if total_distance <= 0:
            return None
        
        progress_ratio = current_progress / total_distance
        
        # Check if no forward progress (less than 30% of distance covered)
        if progress_ratio < self.FORWARD_PROGRESS_ATR_THRESHOLD:
            if hours_held >= exit_hours:
                # Exit at market
                success, msg = order_router.close_position(ticket)
                return f"exit_no_progress:{msg}"
            elif hours_held >= warn_hours:
                # Move SL to breakeven
                new_sl = entry_price
                success, msg = order_router.modify_position(ticket, sl=new_sl)
                return f"move_to_breakeven:{msg}"
        
        return None
    
    def apply_weekend_policy(
        self,
        positions: List[Dict],
        atr_map: Dict[str, float],
        order_router
    ) -> List[str]:
        """
        Called on Friday >= 20:00 UTC.
        
        - Close all losing positions
        - Tighten profitable trailing stops to 0.5x ATR
        - Only hold through weekend if profit >= 1.0x ATR AND trailing active
        """
        actions = []
        
        for pos in positions:
            ticket = pos.get('ticket')
            symbol = pos.get('symbol', '')
            profit = pos.get('profit', 0)
            current_price = pos.get('price_current', 0)
            sl = pos.get('sl', 0)
            
            atr14 = atr_map.get(symbol, 0)
            min_profit_for_weekend = atr14 if atr14 > 0 else 50
            
            if profit < 0:
                # Close losing positions
                success, msg = order_router.close_position(ticket)
                actions.append(f"weekend_close_losing:{symbol}:{msg}")
            elif profit >= min_profit_for_weekend and sl > 0:
                # Tighten trailing stop to 0.5x ATR
                new_trailing_sl = current_price - (atr14 * 0.5) if pos.get('type') == 'BUY' else current_price + (atr14 * 0.5)
                success, msg = order_router.modify_position(ticket, sl=new_trailing_sl)
                actions.append(f"weekend_tighten_sl:{symbol}:{msg}")
            else:
                # Not enough profit to hold through weekend - close
                success, msg = order_router.close_position(ticket)
                actions.append(f"weekend_close_insufficient_profit:{symbol}:{msg}")
        
        return actions
    
    def record_entry_time(self, ticket: int, entry_time: datetime) -> None:
        """Record entry time for a new position."""
        with self._lock:
            self._entry_times[ticket] = entry_time
    
    def remove_position(self, ticket: int) -> None:
        """Remove position from tracking when closed."""
        with self._lock:
            if ticket in self._entry_times:
                del self._entry_times[ticket]
    
    def get_position_age_hours(self, ticket: int) -> Optional[float]:
        """Get hours since position was opened."""
        with self._lock:
            if ticket in self._entry_times:
                entry_time = self._entry_times[ticket]
                return (datetime.now(timezone.utc) - entry_time).total_seconds() / 3600
            return None


# Global instance
_time_exit_manager = None


def get_time_exit_manager(config: Optional[Dict] = None, logger=None) -> TimeExitManager:
    """Get global time exit manager instance."""
    global _time_exit_manager
    if _time_exit_manager is None:
        _time_exit_manager = TimeExitManager(config, logger)
    return _time_exit_manager