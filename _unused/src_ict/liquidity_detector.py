"""
ICT LIQUIDITY DETECTOR
Detects institutional liquidity sweeps (SSL/BSL) - the foundation of ICT trading

Liquidity = Areas where stop-losses cluster (equal highs/lows, round numbers, trendlines)
Sweep = Price briefly breaks these levels to trigger stops, then reverses

This is the MANIPULATION phase that institutions use before the true move
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LiquidityPool:
    """Represents a liquidity zone"""
    pool_type: str  # 'BSL' (Buy-Side) or 'SSL' (Sell-Side)
    price: float
    time: datetime
    strength: int  # Number of touches (2+ = equal highs/lows)
    swept: bool = False
    sweep_time: Optional[datetime] = None


@dataclass
class LiquiditySweep:
    """Represents a confirmed liquidity sweep"""
    sweep_type: str  # 'SSL' or 'BSL'
    liquidity_level: float
    sweep_high: float  # Actual high of sweep candle
    sweep_low: float   # Actual low of sweep candle
    sweep_time: datetime
    rejection_confirmed: bool  # Did price reverse after sweep?
    rejection_strength: float  # Wick size / body size ratio
    volume_spike: bool  # Was there increased volume?


class ICTLiquidityDetector:
    """
    Detect institutional liquidity pools and sweeps
    
    Key Concept:
    - Smart money needs liquidity (stop-losses) to fill large orders
    - They drive price to sweep these stops, then reverse
    - We trade the REVERSAL after the sweep
    """
    
    def __init__(self, 
                 lookback_bars: int = 20,
                 equal_level_tolerance_pips: float = 2.0,
                 min_sweep_pips: float = 1.0,
                 min_rejection_ratio: float = 2.0):
        """
        Args:
            lookback_bars: How far to look for equal highs/lows
            equal_level_tolerance_pips: Max difference for "equal" levels
            min_sweep_pips: Minimum pips beyond level to confirm sweep
            min_rejection_ratio: Wick must be X times larger than body
        """
        self.lookback_bars = lookback_bars
        self.equal_tolerance = equal_level_tolerance_pips
        self.min_sweep = min_sweep_pips
        self.min_rejection_ratio = min_rejection_ratio
        
        self.liquidity_pools: List[LiquidityPool] = []
        self.sweeps: List[LiquiditySweep] = []
    
    def identify_liquidity_pools(self, df: pd.DataFrame) -> List[LiquidityPool]:
        """
        Identify liquidity pools (equal highs/lows, swing points)
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            List of LiquidityPool objects
        """
        pools = []
        
        # Find swing highs and lows
        for i in range(self.lookback_bars, len(df) - self.lookback_bars):
            # Buy-Side Liquidity (BSL) - Equal highs
            if self._is_swing_high(df, i):
                high_price = df.iloc[i]['high']
                
                # Check for equal highs within lookback
                equal_count = 1
                for j in range(max(0, i - self.lookback_bars), i):
                    if self._is_equal_level(df.iloc[j]['high'], high_price):
                        equal_count += 1
                
                # Equal highs = strong liquidity pool
                if equal_count >= 2:
                    pools.append(LiquidityPool(
                        pool_type='BSL',
                        price=high_price,
                        time=df.iloc[i]['time'],
                        strength=equal_count
                    ))
            
            # Sell-Side Liquidity (SSL) - Equal lows
            if self._is_swing_low(df, i):
                low_price = df.iloc[i]['low']
                
                equal_count = 1
                for j in range(max(0, i - self.lookback_bars), i):
                    if self._is_equal_level(df.iloc[j]['low'], low_price):
                        equal_count += 1
                
                if equal_count >= 2:
                    pools.append(LiquidityPool(
                        pool_type='SSL',
                        price=low_price,
                        time=df.iloc[i]['time'],
                        strength=equal_count
                    ))
        
        self.liquidity_pools = pools
        return pools
    
    def detect_sweeps(self, df: pd.DataFrame, 
                      liquidity_pools: List[LiquidityPool]) -> List[LiquiditySweep]:
        """
        Detect when price sweeps liquidity pools
        
        A sweep occurs when:
        1. Price breaks above BSL or below SSL
        2. Creates a long wick (rejection)
        3. Closes back inside the level
        4. Often has increased volume
        
        Args:
            df: OHLCV DataFrame
            liquidity_pools: Previously identified pools
            
        Returns:
            List of LiquiditySweep objects
        """
        sweeps = []
        
        for i in range(1, len(df)):
            candle = df.iloc[i]
            
            for pool in liquidity_pools:
                # Skip if already swept
                if pool.swept:
                    continue
                
                # Check for BSL sweep (upside)
                if pool.pool_type == 'BSL':
                    if candle['high'] > pool.price + self.min_sweep:
                        # Confirmed sweep if it breaks above then rejects
                        rejection = self._check_bullish_rejection(candle, pool.price)
                        
                        if rejection > 0:
                            sweep = LiquiditySweep(
                                sweep_type='BSL',
                                liquidity_level=pool.price,
                                sweep_high=candle['high'],
                                sweep_low=candle['low'],
                                sweep_time=candle['time'],
                                rejection_confirmed=rejection >= self.min_rejection_ratio,
                                rejection_strength=rejection,
                                volume_spike=self._check_volume_spike(df, i)
                            )
                            sweeps.append(sweep)
                            pool.swept = True
                            pool.sweep_time = candle['time']
                
                # Check for SSL sweep (downside)
                elif pool.pool_type == 'SSL':
                    if candle['low'] < pool.price - self.min_sweep:
                        # Confirmed sweep if it breaks below then rejects
                        rejection = self._check_bearish_rejection(candle, pool.price)
                        
                        if rejection > 0:
                            sweep = LiquiditySweep(
                                sweep_type='SSL',
                                liquidity_level=pool.price,
                                sweep_high=candle['high'],
                                sweep_low=candle['low'],
                                sweep_time=candle['time'],
                                rejection_confirmed=rejection >= self.min_rejection_ratio,
                                rejection_strength=rejection,
                                volume_spike=self._check_volume_spike(df, i)
                            )
                            sweeps.append(sweep)
                            pool.swept = True
                            pool.sweep_time = candle['time']
        
        self.sweeps = sweeps
        return sweeps
    
    def get_latest_sweep(self) -> Optional[LiquiditySweep]:
        """Get the most recent liquidity sweep"""
        if not self.sweeps:
            return None
        return self.sweeps[-1]
    
    def is_sweep_valid_for_trading(self, sweep: LiquiditySweep,
                                   max_bars_ago: int = 5) -> bool:
        """
        Check if a sweep is valid for trading
        
        Args:
            sweep: LiquiditySweep to validate
            max_bars_ago: Maximum bars since sweep
            
        Returns:
            True if sweep is tradeable
        """
        # Must have strong rejection
        if not sweep.rejection_confirmed:
            return False
        
        # Must be recent
        if max_bars_ago is not None:
            # This would require tracking bar count since sweep
            pass
        
        # Prefer volume confirmation
        if sweep.volume_spike:
            return True
        
        # Strong rejection alone can be valid
        return sweep.rejection_strength >= self.min_rejection_ratio * 1.5
    
    def _is_swing_high(self, df: pd.DataFrame, idx: int, lookback: int = 5) -> bool:
        """Check if candle is a swing high"""
        if idx < lookback or idx >= len(df) - lookback:
            return False
        
        current_high = df.iloc[idx]['high']
        
        # Check if higher than bars before and after
        for i in range(idx - lookback, idx):
            if df.iloc[i]['high'] >= current_high:
                return False
        
        for i in range(idx + 1, min(idx + lookback + 1, len(df))):
            if df.iloc[i]['high'] >= current_high:
                return False
        
        return True
    
    def _is_swing_low(self, df: pd.DataFrame, idx: int, lookback: int = 5) -> bool:
        """Check if candle is a swing low"""
        if idx < lookback or idx >= len(df) - lookback:
            return False
        
        current_low = df.iloc[idx]['low']
        
        for i in range(idx - lookback, idx):
            if df.iloc[i]['low'] <= current_low:
                return False
        
        for i in range(idx + 1, min(idx + lookback + 1, len(df))):
            if df.iloc[i]['low'] <= current_low:
                return False
        
        return True
    
    def _is_equal_level(self, price1: float, price2: float) -> bool:
        """Check if two prices are approximately equal"""
        return abs(price1 - price2) <= self.equal_tolerance
    
    def _check_bullish_rejection(self, candle: pd.Series, level: float) -> float:
        """
        Check for bearish rejection after BSL sweep
        
        Returns rejection strength (wick/body ratio)
        """
        high = candle['high']
        low = candle['low']
        open_price = candle['open']
        close = candle['close']
        
        # Calculate wick and body
        upper_wick = high - max(open_price, close)
        body = abs(close - open_price)
        
        # Avoid division by zero
        if body < 0.0001:
            body = 0.0001
        
        # Rejection strength = upper wick / body
        # Also check if it closed below the level
        if close < level and upper_wick > 0:
            return upper_wick / body
        
        return 0.0
    
    def _check_bearish_rejection(self, candle: pd.Series, level: float) -> float:
        """
        Check for bullish rejection after SSL sweep
        
        Returns rejection strength (wick/body ratio)
        """
        high = candle['high']
        low = candle['low']
        open_price = candle['open']
        close = candle['close']
        
        # Calculate wick and body
        lower_wick = min(open_price, close) - low
        body = abs(close - open_price)
        
        if body < 0.0001:
            body = 0.0001
        
        # Rejection strength = lower wick / body
        # Also check if it closed above the level
        if close > level and lower_wick > 0:
            return lower_wick / body
        
        return 0.0
    
    def _check_volume_spike(self, df: pd.DataFrame, idx: int, 
                           threshold: float = 1.5) -> bool:
        """
        Check if current candle has volume spike
        
        Args:
            df: DataFrame
            idx: Current candle index
            threshold: Volume must be X times average
            
        Returns:
            True if volume spike detected
        """
        if 'volume' not in df.columns and 'tick_volume' not in df.columns:
            return False
        
        vol_col = 'volume' if 'volume' in df.columns else 'tick_volume'
        
        # Compare to average of last 10 bars
        if idx < 10:
            return False
        
        current_vol = df.iloc[idx][vol_col]
        avg_vol = df.iloc[idx-10:idx][vol_col].mean()
        
        return current_vol >= avg_vol * threshold
    
    def get_sweep_summary(self) -> Dict:
        """Get summary of detected sweeps"""
        if not self.sweeps:
            return {
                'total_sweeps': 0,
                'ssl_sweeps': 0,
                'bsl_sweeps': 0,
                'confirmed_rejections': 0
            }
        
        ssl_count = sum(1 for s in self.sweeps if s.sweep_type == 'SSL')
        bsl_count = sum(1 for s in self.sweeps if s.sweep_type == 'BSL')
        confirmed = sum(1 for s in self.sweeps if s.rejection_confirmed)
        
        return {
            'total_sweeps': len(self.sweeps),
            'ssl_sweeps': ssl_count,
            'bsl_sweeps': bsl_count,
            'confirmed_rejections': confirmed,
            'latest_sweep': self.get_latest_sweep()
        }
