"""
APEX FX Trading Bot - WTI Crude Oil Feed
Section 6: Data Layer - Commodity feed for USD/CAD correlation strategy
"""

import requests
import pandas as pd
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import time


class WTIOilFeed:
    """WTI Crude oil price feed for USD/CAD correlation"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self._cached_price = None
        self._last_update = None
        self._cache_duration = 60  # 1 minute cache
    
    def get_current_price(self) -> Optional[float]:
        """Get current WTI crude oil price"""
        now = datetime.now()
        
        if self._cached_price and self._last_update:
            if (now - self._last_update).total_seconds() < self._cache_duration:
                return self._cached_price
        
        if self.api_key:
            return self._fetch_from_api()
        
        return self._get_mock_price()
    
    def _fetch_from_api(self) -> Optional[float]:
        """Fetch from Alpha Vantage API"""
        try:
            params = {
                'function': 'WTI',
                'interval': 'daily',
                'apikey': self.api_key
            }
            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()
            
            if 'data' in data and data['data']:
                price = float(data['data'][0]['value'])
                self._cached_price = price
                self._last_update = datetime.now()
                return price
        except Exception as e:
            print(f"WTI API error: {e}")
        
        return self._get_mock_price()
    
    def _get_mock_price(self) -> float:
        """Return mock price for development/testing"""
        return 78.50
    
    def get_historical(self, days: int = 30) -> pd.DataFrame:
        """Get historical WTI prices"""
        base_price = 78.50
        dates = pd.date_range(end=datetime.now(), periods=days, freq='D')
        
        import numpy as np
        np.random.seed(42)
        prices = base_price + np.cumsum(np.random.randn(days) * 0.5)
        
        df = pd.DataFrame({
            'date': dates,
            'price': prices
        })
        return df
    
    def is_trending_up(self, lookback: int = 5) -> bool:
        """Check if oil is trending up (for USD/CAD sell signal)"""
        hist = self.get_historical(lookback)
        if len(hist) < 2:
            return False
        return hist['price'].iloc[-1] > hist['price'].iloc[0]
    
    def is_trending_down(self, lookback: int = 5) -> bool:
        """Check if oil is trending down (for USD/CAD buy signal)"""
        hist = self.get_historical(lookback)
        if len(hist) < 2:
            return False
        return hist['price'].iloc[-1] < hist['price'].iloc[0]


_wti_feed = None


def get_wti_feed(api_key: str = None) -> WTIOilFeed:
    """Get global WTI feed instance"""
    global _wti_feed
    if _wti_feed is None:
        _wti_feed = WTIOilFeed(api_key)
    return _wti_feed