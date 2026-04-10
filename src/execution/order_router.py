"""
APEX FX Trading Bot - Order Router
Section 6: Execution Engine - Order routing with spread checker and retry logic
"""

import MetaTrader5 as mt5
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import time
import random


class OrderRouter:
    """
    PRD Section 6 - Execution Engine:
    - Order router (MT5 API)
    - Spread checker (pre-trade validation)
    - Spread-to-ATR ratio filter (PRD Vol II 21.1)
    - Slippage monitor
    - Retry logic with 4 attempts per PRD Vol II 21.3
    """
    
    # PRD Vol II Section 21.3 - Exact retry configuration
    RETRY_CONFIG = [
        {'delay_ms': 0,    'slippage_pips': 0.3},
        {'delay_ms': 500,  'slippage_pips': 0.5},
        {'delay_ms': 1500, 'slippage_pips': 0.8},
        {'delay_ms': 4000, 'slippage_pips': 1.2},
    ]
    
    def __init__(self, max_retries: int = 4, retry_delay: float = 1.0):
        self.max_retries = max_retries  # Now 4 per PRD Vol II
        self.retry_delay = retry_delay
        self.max_spread_pips = {
            'EURUSD': 1.5,
            'GBPUSD': 2.0,
            'USDJPY': 2.0,
            'USDCHF': 2.0,
            'USDCAD': 2.0,
            'XAUUSD': 3.0
        }
    
    def get_spread(self, symbol: str) -> Optional[float]:
        """Get current spread in pips"""
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return None
            
            spread = symbol_info.spread
            if symbol in ['XAUUSD']:
                return spread / 10.0  # Gold uses different point units
            return spread
        except Exception as e:
            print(f"Spread check error: {e}")
            return None
    
    def check_spread(self, symbol: str) -> Tuple[bool, str]:
        """Pre-trade spread validation - PRD Section 4.2"""
        spread = self.get_spread(symbol)
        if spread is None:
            return False, "Cannot get spread"
        
        max_spread = self.max_spread_pips.get(symbol, 2.0)
        
        if spread > max_spread:
            return False, f"Spread {spread:.1f} pips exceeds max {max_spread} pips"
        
        return True, "OK"
    
    def check_spread_atr_ratio(self, symbol: str, atr14_price: float) -> Tuple[bool, str]:
        """
        PRD Volume II Section 21.1: Block entry if spread exceeds 15% of ATR.
        This prevents entries during hidden liquidity crises.
        
        Args:
            symbol: Trading symbol
            atr14_price: Current ATR(14) value in price units
            
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        try:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return False, 'Cannot fetch tick data for spread check'
            
            spread_price = tick.ask - tick.bid
            
            if atr14_price <= 0:
                return False, 'ATR is zero — cannot compute spread ratio'
            
            ratio = spread_price / atr14_price
            
            if ratio > 0.15:
                return False, f'Spread/ATR ratio {ratio:.3f} exceeds 0.15 limit'
            
            return True, f'Spread/ATR ratio {ratio:.3f} acceptable'
        except Exception as e:
            return False, f'Spread-ATR check error: {str(e)}'
    
    def place_order(self, symbol: str, direction: str, lots: float,
                    sl: float = None, tp: float = None, comment: str = "") -> Tuple[bool, str, Optional[int]]:
        """
        Place order with PRD Vol II Section 21.3 retry logic:
        - 4 attempts with exact millisecond delays
        - Escalating slippage tolerance (0.3, 0.5, 0.8, 1.2 pips)
        Returns: (success, message, ticket)
        """
        for attempt_idx, cfg in enumerate(self.RETRY_CONFIG):
            try:
                # Apply delay before retry (skip for first attempt)
                if cfg['delay_ms'] > 0:
                    time.sleep(cfg['delay_ms'] / 1000.0)
                
                spread_ok, spread_msg = self.check_spread(symbol)
                if not spread_ok:
                    return False, spread_msg, None
                
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info is None:
                    return False, f"Symbol {symbol} not found", None
                
                if not symbol_info.visible:
                    mt5.symbol_select(symbol, True)
                
                point = symbol_info.point
                
                if direction.upper() == 'BUY':
                    order_type = mt5.ORDER_TYPE_BUY
                    price = mt5.symbol_info_tick(symbol).ask
                    if sl and sl > price:
                        return False, "Invalid SL for BUY", None
                    if tp and tp < price:
                        return False, "Invalid TP for BUY", None
                else:
                    order_type = mt5.ORDER_TYPE_SELL
                    price = mt5.symbol_info_tick(symbol).bid
                    if sl and sl < price:
                        return False, "Invalid SL for SELL", None
                    if tp and tp > price:
                        return False, "Invalid TP for SELL", None
                
                # Calculate deviation in points based on slippage tolerance
                deviation = int(cfg['slippage_pips'] / point)
                
                request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": symbol,
                    "volume": lots,
                    "type": order_type,
                    "price": price,
                    "deviation": deviation,
                    "magic": 234000,
                    "comment": comment,
                    "type_time": mt5.ORDER_TIME_GTC,
                    "type_filling": mt5.ORDER_FILLING_IOC
                }
                
                if sl:
                    request["sl"] = sl
                if tp:
                    request["tp"] = tp
                
                result = mt5.order_send(request)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    return True, f"Order placed successfully", result.order
                
                error_msg = self._get_error_message(result.retcode)
                print(f"Order failed (attempt {attempt_idx + 1}): {error_msg}")
                
            except Exception as e:
                print(f"Order error (attempt {attempt_idx + 1}): {e}")
        
        # All 4 attempts failed - PRD Vol II: log as MISSED_SIGNAL
        print(f"Order failed after 4 attempts for {symbol} {direction}")
        return False, 'Order failed after 4 attempts', None
    
    def close_position(self, ticket: int, lots: float = None) -> Tuple[bool, str]:
        """Close an open position"""
        try:
            position = mt5.position_get(ticket=ticket)
            if position is None:
                return False, "Position not found"
            
            symbol = position.symbol
            
            if direction == "BUY":
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(symbol).ask
            
            volume = lots if lots else position.volume
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": "Close",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return True, "Position closed"
            
            return False, self._get_error_message(result.retcode)
            
        except Exception as e:
            return False, str(e)
    
    def modify_position(self, ticket: int, sl: float = None, tp: float = None) -> Tuple[bool, str]:
        """Modify SL/TP of an existing position"""
        try:
            request = {
                "action": mt5.TRADE_ACTION_SLTP,
                "position": ticket,
            }
            
            if sl is not None:
                request["sl"] = sl
            if tp is not None:
                request["tp"] = tp
            
            if len(request) == 2:
                return False, "No SL or TP provided"
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return True, "Position modified"
            
            return False, self._get_error_message(result.retcode)
            
        except Exception as e:
            return False, str(e)
    
    def _get_error_message(self, retcode: int) -> str:
        """Convert MT5 return code to human-readable message"""
        errors = {
            mt5.TRADE_RETCODE_REQUOTE: "Requote - price changed",
            mt5.TRADE_RETCODE_REJECT: "Request rejected",
            mt5.TRADE_RETCODE_CANCEL: "Request cancelled",
            mt5.TRADE_RETCODE_NO_CONNECTION: "No connection",
            mt5.TRADE_RETCODE_NO_MONEY: "Insufficient margin",
            mt5.TRADE_RETCODE_PRICE_OFF: "Price off",
            mt5.TRADE_RETCODE_INVALID_STOPS: "Invalid stops",
            mt5.TRADE_RETCODE_INVALID_VOLUME: "Invalid volume",
            mt5.TRADE_RETCODE_MARKET_CLOSED: "Market closed",
            mt5.TRADE_RETCODE_NO_RESULT: "No result"
        }
        return errors.get(retcode, f"Error code: {retcode}")
    
    def get_positions(self) -> list:
        """Get all open positions"""
        return mt5.positions_get()
    
    def get_position(self, ticket: int) -> Optional[Dict]:
        """Get specific position by ticket"""
        pos = mt5.position_get(ticket=ticket)
        if pos:
            return {
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'volume': pos.volume,
                'type': 'BUY' if pos.type == 0 else 'SELL',
                'open_price': pos.price_open,
                'sl': pos.sl,
                'tp': pos.tp,
                'profit': pos.profit,
                'time': pos.time
            }
        return None


_order_router = None


def get_order_router() -> OrderRouter:
    """Get global order router instance"""
    global _order_router
    if _order_router is None:
        _order_router = OrderRouter()
    return _order_router