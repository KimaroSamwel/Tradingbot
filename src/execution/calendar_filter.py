"""
APEX FX Trading Bot - Calendar Filter
PRD Volume II Section 17: Calendar-Based Position Sizing

Enforces day-of-week rules, month-end/quarter-end size reductions,
and seasonal adjustments.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timezone, timedelta
import threading


class CalendarFilter:
    """
    Calendar Filter - enforces calendar-based rules.
    
    Rules:
    - Monday before 10:00 UTC: blocked
    - Friday after 16:00 UTC: blocked
    - Month-end (last 2 trading days): 50% size
    - Quarter-end (last 5 trading days of Mar/Jun/Sep/Dec): 25% size
    - NFP week (first Friday of month): 50% size
    - FOMC week: 50% size
    """
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize calendar filter.
        
        Args:
            config: Optional configuration
            logger: Optional logger
        """
        self._lock = threading.Lock()
        self._config = config or {}
        self._logger = logger
        
        # Month-end and quarter-end months
        self._quarter_end_months = {3, 6, 9, 12}
    
    def get_size_modifier(self, now_utc: datetime) -> Tuple[float, str]:
        """
        Returns (modifier, reason) to multiply against all position sizes.
        
        Args:
            now_utc: Current UTC datetime
            
        Returns:
            Tuple of (modifier, reason)
        """
        with self._lock:
            modifier = 1.0
            reasons = []
            
            # Check month-end
            if self._is_month_end(now_utc):
                modifier *= 0.5
                reasons.append('month_end')
            
            # Check quarter-end
            if self._is_quarter_end(now_utc):
                modifier *= 0.5
                reasons.append('quarter_end')
            
            # Check NFP week
            if self._is_nfp_week(now_utc):
                modifier *= 0.5
                reasons.append('nfp_week')
            
            # Check FOMC week (simplified - would check calendar)
            if self._is_fomc_week(now_utc):
                modifier *= 0.5
                reasons.append('fomc_week')
            
            reason = '+'.join(reasons) if reasons else 'normal'
            
            return modifier, reason
    
    def is_new_entry_allowed(self, now_utc: datetime) -> Tuple[bool, str]:
        """
        Returns (allowed, reason).
        
        Args:
            now_utc: Current UTC datetime
            
        Returns:
            Tuple of (allowed, reason)
        """
        with self._lock:
            # Check Monday before 10:00 UTC
            if now_utc.weekday() == 0 and now_utc.hour < 10:
                return False, 'Monday before 10:00 UTC'
            
            # Check Friday after 16:00 UTC
            if now_utc.weekday() == 4 and now_utc.hour >= 16:
                return False, 'Friday after 16:00 UTC'
            
            return True, 'Entry allowed'
    
    def _is_month_end(
        self, 
        now_utc: datetime, 
        trading_days_from_end: int = 2
    ) -> bool:
        """True if within the last 2 trading days of the calendar month."""
        # Get last day of month
        if now_utc.month == 12:
            last_day = datetime(now_utc.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
        else:
            last_day = datetime(now_utc.year, now_utc.month + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
        
        # Count back trading days (exclude weekends)
        trading_days_left = 0
        check_date = last_day
        
        while trading_days_left < trading_days_from_end:
            if check_date.weekday() < 5:  # Monday-Friday
                trading_days_left += 1
            check_date -= timedelta(days=1)
        
        return now_utc >= check_date
    
    def _is_quarter_end(self, now_utc: datetime) -> bool:
        """True if within the last 5 trading days of March, June, September, December."""
        if now_utc.month not in self._quarter_end_months:
            return False
        
        # Get last day of quarter month
        if now_utc.month == 12:
            last_day = datetime(now_utc.year + 1, 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
        else:
            last_day = datetime(now_utc.year, now_utc.month + 1, 1, tzinfo=timezone.utc) - timedelta(days=1)
        
        # Count back 5 trading days
        trading_days_left = 0
        check_date = last_day
        
        while trading_days_left < 5:
            if check_date.weekday() < 5:
                trading_days_left += 1
            check_date -= timedelta(days=1)
        
        return now_utc >= check_date
    
    def _is_nfp_week(self, now_utc: datetime) -> bool:
        """True if current week contains the first Friday of the month (NFP day)."""
        # Find first Friday of this month
        first_day = datetime(now_utc.year, now_utc.month, 1, tzinfo=timezone.utc)
        
        # Calculate days until first Friday
        days_to_friday = (4 - first_day.weekday()) % 7
        first_friday = first_day + timedelta(days=days_to_friday)
        
        # Check if current week contains this Friday
        week_start = now_utc - timedelta(days=now_utc.weekday())
        week_end = week_start + timedelta(days=7)
        
        return week_start <= first_friday < week_end
    
    def _is_fomc_week(self, now_utc: datetime) -> bool:
        """True if current week contains FOMC meeting (simplified)."""
        # FOMC meetings are typically in Jan, Mar, May, Jun, Jul, Sep, Nov, Dec
        # Second week of these months is typical
        
        fomc_months = {1, 3, 5, 6, 7, 9, 11, 12}
        
        if now_utc.month not in fomc_months:
            return False
        
        # Simplified check - assume FOMC is around middle of month
        day_of_month = now_utc.day
        return 8 <= day_of_month <= 16
    
    def get_session_window(self, now_utc: datetime) -> str:
        """
        Get current session window name.
        
        Args:
            now_utc: Current UTC datetime
            
        Returns:
            Session window name
        """
        hour = now_utc.hour
        
        if 0 <= hour < 7:
            return 'ASIA'
        elif 7 <= hour < 12:
            return 'LONDON'
        elif 12 <= hour < 16:
            return 'OVERLAP'
        elif 16 <= hour < 21:
            return 'NEW_YORK'
        else:
            return 'ASIA'


# Global instance
_calendar_filter = None


def get_calendar_filter(config: Optional[Dict] = None, logger=None) -> CalendarFilter:
    """Get global calendar filter instance."""
    global _calendar_filter
    if _calendar_filter is None:
        _calendar_filter = CalendarFilter(config, logger)
    return _calendar_filter