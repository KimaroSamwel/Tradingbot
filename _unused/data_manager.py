"""
Data Manager
Centralized data fetching, caching, and management
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pickle
import os


class DataManager:
    """
    Manages data fetching and caching for the trading system
    """
    
    def __init__(self, cache_dir: str = 'data/cache'):
        """
        Initialize data manager
        
        Args:
            cache_dir: Directory for data cache
        """
        self.cache_dir = cache_dir
        os.makedirs(cache_dir, exist_ok=True)
        
        self.cache_duration = {
            mt5.TIMEFRAME_M5: timedelta(hours=1),
            mt5.TIMEFRAME_M15: timedelta(hours=2),
            mt5.TIMEFRAME_H1: timedelta(hours=6),
            mt5.TIMEFRAME_H4: timedelta(hours=12),
            mt5.TIMEFRAME_D1: timedelta(days=1)
        }
    
    def get_data(self, symbol: str, timeframe: int, bars: int = 500,
                use_cache: bool = True) -> Optional[pd.DataFrame]:
        """
        Get market data with caching
        
        Args:
            symbol: Trading symbol
            timeframe: MT5 timeframe
            bars: Number of bars
            use_cache: Whether to use cached data
        
        Returns:
            DataFrame with OHLCV data
        """
        cache_file = self._get_cache_filename(symbol, timeframe)
        
        if use_cache and os.path.exists(cache_file):
            cached_data = self._load_from_cache(cache_file, timeframe)
            if cached_data is not None:
                return cached_data
        
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        df.set_index('time', inplace=True)
        
        if use_cache:
            self._save_to_cache(df, cache_file)
        
        return df
    
    def get_multi_timeframe_data(self, symbol: str, 
                                timeframes: List[int],
                                bars: int = 500) -> Dict[int, pd.DataFrame]:
        """
        Get data for multiple timeframes
        
        Args:
            symbol: Trading symbol
            timeframes: List of MT5 timeframes
            bars: Number of bars
        
        Returns:
            Dict of {timeframe: DataFrame}
        """
        data = {}
        
        for tf in timeframes:
            df = self.get_data(symbol, tf, bars)
            if df is not None:
                data[tf] = df
        
        return data
    
    def _get_cache_filename(self, symbol: str, timeframe: int) -> str:
        """Generate cache filename"""
        tf_name = self._timeframe_to_string(timeframe)
        return os.path.join(self.cache_dir, f'{symbol}_{tf_name}.pkl')
    
    def _timeframe_to_string(self, timeframe: int) -> str:
        """Convert timeframe constant to string"""
        tf_map = {
            mt5.TIMEFRAME_M5: 'M5',
            mt5.TIMEFRAME_M15: 'M15',
            mt5.TIMEFRAME_H1: 'H1',
            mt5.TIMEFRAME_H4: 'H4',
            mt5.TIMEFRAME_D1: 'D1'
        }
        return tf_map.get(timeframe, 'UNKNOWN')
    
    def _load_from_cache(self, cache_file: str, timeframe: int) -> Optional[pd.DataFrame]:
        """Load data from cache if fresh"""
        try:
            cache_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
            max_age = self.cache_duration.get(timeframe, timedelta(hours=1))
            
            if datetime.now() - cache_time > max_age:
                return None
            
            with open(cache_file, 'rb') as f:
                df = pickle.load(f)
            
            return df
        
        except Exception:
            return None
    
    def _save_to_cache(self, df: pd.DataFrame, cache_file: str):
        """Save data to cache"""
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(df, f)
        except Exception as e:
            print(f"Failed to cache data: {e}")
    
    def clear_cache(self, symbol: Optional[str] = None):
        """
        Clear data cache
        
        Args:
            symbol: Symbol to clear (None = clear all)
        """
        if symbol is None:
            for file in os.listdir(self.cache_dir):
                if file.endswith('.pkl'):
                    os.remove(os.path.join(self.cache_dir, file))
        else:
            for file in os.listdir(self.cache_dir):
                if file.startswith(symbol) and file.endswith('.pkl'):
                    os.remove(os.path.join(self.cache_dir, file))
