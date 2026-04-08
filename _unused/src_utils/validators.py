"""
Input Validation Functions
Validates trading parameters and inputs
"""

import MetaTrader5 as mt5
from typing import Dict, Tuple, Optional


def validate_symbol(symbol: str) -> Tuple[bool, str]:
    """
    Validate trading symbol
    
    Args:
        symbol: Symbol to validate
    
    Returns:
        (is_valid, message)
    """
    if not symbol or len(symbol) < 6:
        return (False, "Invalid symbol format")
    
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return (False, f"Symbol {symbol} not found in MT5")
    
    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            return (False, f"Failed to enable symbol {symbol}")
    
    return (True, "Symbol valid")


def validate_timeframe(timeframe: int) -> Tuple[bool, str]:
    """
    Validate MT5 timeframe
    
    Args:
        timeframe: MT5 timeframe constant
    
    Returns:
        (is_valid, message)
    """
    valid_timeframes = [
        mt5.TIMEFRAME_M1, mt5.TIMEFRAME_M5, mt5.TIMEFRAME_M15, mt5.TIMEFRAME_M30,
        mt5.TIMEFRAME_H1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_D1, mt5.TIMEFRAME_W1
    ]
    
    if timeframe not in valid_timeframes:
        return (False, f"Invalid timeframe: {timeframe}")
    
    return (True, "Timeframe valid")


def validate_order(symbol: str, order_type: int, volume: float, 
                   price: float, sl: float, tp: float) -> Tuple[bool, str]:
    """
    Validate order parameters
    
    Args:
        symbol: Trading symbol
        order_type: Order type (BUY/SELL)
        volume: Lot size
        price: Entry price
        sl: Stop loss
        tp: Take profit
    
    Returns:
        (is_valid, message)
    """
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return (False, f"Symbol {symbol} not found")
    
    if volume < symbol_info.volume_min:
        return (False, f"Volume {volume} below minimum {symbol_info.volume_min}")
    
    if volume > symbol_info.volume_max:
        return (False, f"Volume {volume} above maximum {symbol_info.volume_max}")
    
    volume_step = symbol_info.volume_step
    if round(volume / volume_step) * volume_step != volume:
        return (False, f"Volume {volume} not valid step {volume_step}")
    
    if order_type == mt5.ORDER_TYPE_BUY:
        if sl > 0 and sl >= price:
            return (False, f"BUY stop loss {sl} must be below price {price}")
        if tp > 0 and tp <= price:
            return (False, f"BUY take profit {tp} must be above price {price}")
    
    elif order_type == mt5.ORDER_TYPE_SELL:
        if sl > 0 and sl <= price:
            return (False, f"SELL stop loss {sl} must be above price {price}")
        if tp > 0 and tp >= price:
            return (False, f"SELL take profit {tp} must be below price {price}")
    
    return (True, "Order parameters valid")
