"""
APEX FX Trading Bot - Binance Data Source
Crypto data from Binance
"""

import requests
import pandas as pd
import time
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class BinanceConnector:
    """Binance API connector for crypto data"""
    
    BASE_URL = "https://api.binance.com"
    
    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = requests.Session()
        
    def _get(self, endpoint: str, params: Dict = None) -> Dict:
        """Make GET request"""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Binance API error: {e}")
            return {}
    
    def _get_signed(self, endpoint: str, params: Dict = None) -> Dict:
        """Make authenticated GET request"""
        if not self.api_key or not self.api_secret:
            return self._get(endpoint, params)
        
        # In production, would create proper signature
        return self._get(endpoint, params)
    
    def get_symbols(self, quote: str = 'USDT') -> List[str]:
        """Get available symbols"""
        data = self._get("/api/v3/exchangeInfo", {'symbol': quote})
        if 'symbols' in data:
            return [s['symbol'] for s in data['symbols'] if s['status'] == 'TRADING']
        return []
    
    def get_klines(self, symbol: str, interval: str = '1h', 
                   limit: int = 100, start_time: int = None) -> Optional[pd.DataFrame]:
        """Get candlestick data"""
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        if start_time:
            params['startTime'] = start_time
        
        data = self._get("/api/v3/klines", params)
        if not data:
            return None
        
        df = pd.DataFrame(data, columns=[
            'open_time', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades', 'taker_buy_base', 'taker_buy_quote', 'ignore'
        ])
        
        df['open_time'] = pd.to_datetime(df['open_time'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col])
        
        df.set_index('open_time', inplace=True)
        return df[['open', 'high', 'low', 'close', 'volume']]
    
    def get_ticker(self, symbol: str = None) -> Dict[str, Any]:
        """Get 24h ticker"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        data = self._get("/api/v3/ticker/24hr", params)
        
        if symbol:
            return {
                'symbol': data.get('symbol'),
                'last_price': float(data.get('lastPrice', 0)),
                'bid_price': float(data.get('bidPrice', 0)),
                'ask_price': float(data.get('askPrice', 0)),
                'high_24h': float(data.get('highPrice', 0)),
                'low_24h': float(data.get('lowPrice', 0)),
                'volume_24h': float(data.get('volume', 0)),
                'price_change_24h': float(data.get('priceChange', 0)),
                'price_change_pct': float(data.get('priceChangePercent', 0))
            }
        
        return data
    
    def get_order_book(self, symbol: str, limit: int = 20) -> Dict[str, List]:
        """Get order book"""
        data = self._get("/api/v3/depth", {'symbol': symbol, 'limit': limit})
        return {
            'bids': [[float(p), float(q)] for p, q in data.get('bids', [])],
            'asks': [[float(p), float(q)] for p, q in data.get('asks', [])]
        }
    
    def get_balance(self) -> Dict[str, float]:
        """Get account balance (requires auth)"""
        # Would require proper signature in production
        return {}
    
    def get_trades(self, symbol: str, limit: int = 50) -> List[Dict]:
        """Get recent trades"""
        data = self._get("/api/v3/trades", {'symbol': symbol, 'limit': limit})
        return [{
            'id': t['id'],
            'price': float(t['price']),
            'qty': float(t['qty']),
            'time': t['time'],
            'is_buyer_maker': t['isBuyerMaker']
        } for t in data[-limit:]]


# Global instance
binance = BinanceConnector()


def get_binance() -> BinanceConnector:
    """Get Binance connector"""
    return binance


# Convenience function to get combined data
def get_dataframe(symbol: str, source: str = 'mt5', 
                  timeframe: str = 'H1', count: int = 100) -> Optional[pd.DataFrame]:
    """Get OHLC data from any source"""
    
    if source.lower() == 'mt5':
        from src.data.mt5_connector import get_mt5
        mt5 = get_mt5()
        return mt5.get_ohlc(symbol, timeframe, count)
    
    elif source.lower() == 'binance':
        binance_conn = get_binance()
        return binance_conn.get_klines(symbol, timeframe, count)
    
    return None