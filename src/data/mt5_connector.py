"""
APEX FX Trading Bot - Data Sources
MT5 (Forex), Binance (Crypto), Polygon (Stocks)
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import time


class MT5Connector:
    """MetaTrader5 data source"""
    
    def __init__(self):
        self.connected = False
        self.account_info = {}
        
        # Symbol map for normalization (canonical -> broker-specific)
        self.symbol_map: Dict[str, str] = {
            'EURUSD': 'EURUSD',
            'GBPUSD': 'GBPUSD',
            'USDJPY': 'USDJPY',
            'USDCHF': 'USDCHF',
            'USDCAD': 'USDCAD',
            'XAUUSD': 'XAUUSD'
        }
    
    def normalize_symbol(self, symbol: str) -> str:
        """
        Translate canonical symbol name to broker-specific name.
        
        Args:
            symbol: Canonical symbol name (e.g., 'EURUSD')
            
        Returns:
            Broker-specific symbol name
        """
        return self.symbol_map.get(symbol, symbol)
    
    def validate_symbols(self) -> List[str]:
        """
        At startup, verify all watchlist symbols exist in MT5.
        Log warnings for missing ones.
        
        Returns:
            List of missing canonical symbol names
        """
        if not self.is_connected():
            return list(self.symbol_map.keys())
        
        missing = []
        for canonical, broker_name in self.symbol_map.items():
            info = mt5.symbol_info(broker_name)
            if info is None:
                print(f"WARNING: Symbol not found - canonical: {canonical}, broker_name: {broker_name}")
                missing.append(canonical)
        return missing
        
    def connect(self) -> bool:
        """Connect to MT5"""
        if not mt5.initialize():
            print(f"MT5 init failed: {mt5.last_error()}")
            return False
        
        account = mt5.account_info()
        if account is None:
            print("Failed to get account info")
            return False
        
        self.connected = True
        self.account_info = {
            'login': account.login,
            'balance': account.balance,
            'equity': account.equity,
            'currency': account.currency,
            'leverage': account.leverage,
            'margin_free': account.margin_free,
            'margin_level': account.margin_level
        }
        
        print(f"MT5 Connected: Account {account.login}, Balance: ${account.balance:.2f}")
        return True
    
    def disconnect(self):
        """Disconnect from MT5"""
        mt5.shutdown()
        self.connected = False
    
    def is_connected(self) -> bool:
        """Check connection"""
        return self.connected and mt5.terminal_info() is not None
    
    def get_account(self) -> Dict[str, Any]:
        """Get account info"""
        if not self.is_connected():
            return {}
        
        account = mt5.account_info()
        return {
            'balance': account.balance,
            'equity': account.equity,
            'margin': account.margin,
            'margin_free': account.margin_free,
            'margin_level': account.margin_level,
            'profit': account.profit,
            'currency': account.currency
        }
    
    def get_symbols(self) -> List[str]:
        """Get available symbols"""
        if not self.is_connected():
            return []
        
        symbols = mt5.symbols_get()
        return [s.name for s in symbols]
    
    def get_ohlc(self, symbol: str, timeframe: str, count: int = 100, start_date: datetime = None, use_historic: bool = False) -> Optional[pd.DataFrame]:
        """Get OHLC data"""
        if not self.is_connected():
            return None
        
        tf_map = {
            'M1': mt5.TIMEFRAME_M1,
            'M5': mt5.TIMEFRAME_M5,
            'M15': mt5.TIMEFRAME_M15,
            'M30': mt5.TIMEFRAME_M30,
            'H1': mt5.TIMEFRAME_H1,
            'H4': mt5.TIMEFRAME_H4,
            'D1': mt5.TIMEFRAME_D1,
            'W1': mt5.TIMEFRAME_W1,
            'MN1': mt5.TIMEFRAME_MN1
        }
        
        tf = tf_map.get(timeframe.upper(), mt5.TIMEFRAME_H1)
        
        # For now, use copy_rates_from_pos for all - MT5 doesn't have copy_rates_from_date
        # The start_date parameter is kept for future implementation or alternative data sources
        rates = mt5.copy_rates_from_pos(symbol, tf, 0, count)
        
        if rates is None:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        return df
    
    def get_latest_price(self, symbol: str) -> Optional[Dict[str, float]]:
        """Get latest price for symbol"""
        if not self.is_connected():
            return None
        
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        
        return {
            'bid': tick.bid,
            'ask': tick.ask,
            'last': tick.last,
            'volume': tick.volume,
            'time': tick.time
        }
    
    def get_symbol_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get symbol info"""
        if not self.is_connected():
            return None
        
        info = mt5.symbol_info(symbol)
        if info is None:
            return None
        
        return {
            'name': info.name,
            'point': info.point,
            'digits': info.digits,
            'spread': info.spread,
            'trade_contract_size': info.trade_contract_size,
            'volume_min': info.volume_min,
            'volume_max': info.volume_max,
            'volume_step': info.volume_step
        }
    
    def get_positions(self) -> List[Dict[str, Any]]:
        """Get open positions"""
        if not self.is_connected():
            return []
        
        positions = mt5.positions_get()
        if positions is None:
            return []
        
        result = []
        for pos in positions:
            result.append({
                'ticket': pos.ticket,
                'symbol': pos.symbol,
                'type': 'BUY' if pos.type == mt5.POSITION_TYPE_BUY else 'SELL',
                'volume': pos.volume,
                'price_open': pos.price_open,
                'price_current': pos.price_current,
                'sl': pos.sl,
                'tp': pos.tp,
                'profit': pos.profit,
                'time': pos.time
            })
        
        return result
    
    def open_order(self, symbol: str, direction: str, volume: float, 
                   price: float = 0, sl: float = 0, tp: float = 0,
                   comment: str = "") -> tuple[bool, str]:
        """Open order"""
        if not self.is_connected():
            return False, "Not connected"
        
        # Select symbol
        if not mt5.symbol_select(symbol, True):
            return False, f"Failed to select {symbol}"
        
        # Get price if not provided
        if price == 0:
            tick = mt5.symbol_info_tick(symbol)
            if tick is None:
                return False, f"Failed to get price for {symbol}"
            price = tick.ask if direction.upper() == 'BUY' else tick.bid
        
        # Determine order type
        order_type = mt5.ORDER_TYPE_BUY if direction.upper() == 'BUY' else mt5.ORDER_TYPE_SELL
        
        # Get symbol digits
        symbol_info = mt5.symbol_info(symbol)
        digits = symbol_info.digits if symbol_info else 5
        
        # Prepare request
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': symbol,
            'volume': volume,
            'type': order_type,
            'price': round(price, digits),
            'sl': round(sl, digits) if sl > 0 else 0,
            'tp': round(tp, digits) if tp > 0 else 0,
            'deviation': 10,
            'magic': 2026001,
            'comment': comment,
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_FOK
        }
        
        result = mt5.order_send(request)
        
        if result is None:
            return False, f"Order failed: {mt5.last_error()}"
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return False, f"Order failed: {result.retcode}"
        
        return True, f"Order opened: {result.deal}"
    
    def close_position(self, ticket: int) -> tuple[bool, str]:
        """Close position by ticket"""
        if not self.is_connected():
            return False, "Not connected"
        
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return False, "Position not found"
        
        pos = positions[0]
        
        # Determine opposite direction
        order_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.POSITION_TYPE_BUY else mt5.ORDER_TYPE_BUY
        
        # Get current price
        tick = mt5.symbol_info_tick(pos.symbol)
        if tick is None:
            return False, "Failed to get price"
        
        price = tick.bid if pos.type == mt5.POSITION_TYPE_BUY else tick.ask
        
        request = {
            'action': mt5.TRADE_ACTION_DEAL,
            'symbol': pos.symbol,
            'volume': pos.volume,
            'type': order_type,
            'position': ticket,
            'price': price,
            'deviation': 10,
            'magic': 2026001,
            'comment': "Apex close",
            'type_time': mt5.ORDER_TIME_GTC,
            'type_filling': mt5.ORDER_FILLING_FOK
        }
        
        result = mt5.order_send(request)
        
        if result is None:
            return False, f"Close failed: {mt5.last_error()}"
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            return False, f"Close failed: {result.retcode}"
        
        return True, f"Position {ticket} closed"
    
    def get_history(self, from_date: datetime, to_date: datetime) -> List[Dict]:
        """Get trade history"""
        if not self.is_connected():
            return []
        
        deals = mt5.history_deals_get(from_date, to_date)
        if deals is None:
            return []
        
        result = []
        for deal in deals:
            if deal.profit != 0 or deal.type in [mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL]:
                result.append({
                    'ticket': deal.ticket,
                    'order': deal.order,
                    'symbol': deal.symbol,
                    'type': 'BUY' if deal.type == mt5.DEAL_TYPE_BUY else 'SELL',
                    'volume': deal.volume,
                    'price': deal.price,
                    'profit': deal.profit,
                    'commission': deal.commission,
                    'swap': deal.swap,
                    'time': deal.time
                })
        
        return result


# Global instance
mt5_connector = MT5Connector()


def get_mt5() -> MT5Connector:
    """Get MT5 connector"""
    return mt5_connector