"""
Helper Functions
Common utility functions for trading operations
"""

import MetaTrader5 as mt5
from datetime import datetime, time, timedelta
from typing import Optional
import pytz


def calculate_pip_value(symbol: str, lot_size: float = 1.0) -> float:
    """
    Calculate pip value for a symbol
    
    Args:
        symbol: Trading symbol
        lot_size: Lot size
    
    Returns:
        Pip value in account currency
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return 0.0
    
    if 'JPY' in symbol:
        pip_size = 0.01
    else:
        pip_size = 0.0001
    
    tick_value = symbol_info.trade_tick_value
    tick_size = symbol_info.trade_tick_size
    
    pip_value = (pip_size / tick_size) * tick_value * lot_size
    
    return pip_value


def format_currency(amount: float, currency: str = 'USD') -> str:
    """
    Format currency amount
    
    Args:
        amount: Amount to format
        currency: Currency symbol
    
    Returns:
        Formatted string
    """
    if currency == 'USD':
        return f"${amount:,.2f}"
    elif currency == 'EUR':
        return f"€{amount:,.2f}"
    elif currency == 'GBP':
        return f"£{amount:,.2f}"
    else:
        return f"{amount:,.2f} {currency}"


def time_until_session(target_hour: int, target_minute: int = 0, 
                       timezone: str = 'GMT') -> timedelta:
    """
    Calculate time until target session
    
    Args:
        target_hour: Target hour (0-23)
        target_minute: Target minute (0-59)
        timezone: Timezone name
    
    Returns:
        Time until session
    """
    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    
    target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
    
    if target_time <= now:
        target_time += timedelta(days=1)
    
    return target_time - now


def get_session_name(current_time: Optional[datetime] = None) -> str:
    """
    Get current trading session name
    
    Args:
        current_time: Current time (defaults to now)
    
    Returns:
        Session name
    """
    if current_time is None:
        current_time = datetime.now(pytz.timezone('GMT'))
    
    hour = current_time.hour
    
    if 0 <= hour < 8:
        return 'ASIAN'
    elif 8 <= hour < 12:
        return 'LONDON_OPEN'
    elif 12 <= hour < 16:
        return 'OVERLAP'
    elif 16 <= hour < 20:
        return 'NY_AFTERNOON'
    else:
        return 'ASIAN_EVENING'


def is_weekend(current_time: Optional[datetime] = None) -> bool:
    """
    Check if current time is weekend
    
    Args:
        current_time: Current time (defaults to now)
    
    Returns:
        True if weekend
    """
    if current_time is None:
        current_time = datetime.now(pytz.timezone('GMT'))
    
    weekday = current_time.weekday()
    hour = current_time.hour
    
    if weekday == 5:
        return True
    if weekday == 6 and hour < 22:
        return True
    if weekday == 4 and hour >= 22:
        return True
    
    return False
