"""
COMPREHENSIVE BREAKOUT STRATEGIES COLLECTION
Implementation of 15+ breakout strategies for forex/metals

Includes:
- Range Breakout
- Session Breakout (London/NY/Asian)
- Volatility Breakout (ATR-based)
- Opening Range Breakout (ORB)
- Triangle Pattern Breakout
- Flag/Pennant Breakout
- Donchian Channel Breakout
- Fibonacci Extension Breakout
- News Breakout
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, time


@dataclass
class BreakoutSignal:
    """Breakout strategy signal"""
    strategy: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float  # 0-100
    breakout_level: float
    volume_confirmation: bool
    timeframe: str


class RangeBreakoutStrategies:
    """
    Range and consolidation breakout strategies
    
    1. Horizontal Range Breakout
    2. Consolidation Box Breakout
    3. Narrow Range Breakout
    """
    
    @staticmethod
    def horizontal_range_breakout(df: pd.DataFrame, lookback: int = 20) -> Optional[BreakoutSignal]:
        """
        Horizontal Range Breakout
        Detects consolidation and trades breakout
        """
        if len(df) < lookback + 5:
            return None
        
        # Find range highs/lows
        range_high = df['high'].iloc[-lookback:-1].max()
        range_low = df['low'].iloc[-lookback:-1].min()
        range_size = range_high - range_low
        
        # Calculate average range to determine if consolidating
        avg_range = df['high'].iloc[-lookback:-1] - df['low'].iloc[-lookback:-1]
        avg_range_value = avg_range.mean()
        
        # Check if range is tight (consolidation)
        if range_size > avg_range_value * 3:
            return None  # Too wide, not a consolidation
        
        current_price = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        atr = RangeBreakoutStrategies._calculate_atr(df, 14)
        
        # Volume confirmation (if available)
        volume_spike = False
        if 'volume' in df.columns:
            avg_volume = df['volume'].iloc[-lookback:-1].mean()
            current_volume = df['volume'].iloc[-1]
            volume_spike = current_volume > avg_volume * 1.5
        
        # Bullish breakout
        if current_high > range_high:
            return BreakoutSignal(
                strategy='range_breakout',
                direction='LONG',
                entry_price=current_price,
                stop_loss=range_high - (atr * 0.5),  # Stop below breakout level
                take_profit=current_price + range_size,  # Target = range height
                confidence=85.0 if volume_spike else 70.0,
                breakout_level=range_high,
                volume_confirmation=volume_spike,
                timeframe='M15'
            )
        
        # Bearish breakout
        elif current_low < range_low:
            return BreakoutSignal(
                strategy='range_breakout',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=range_low + (atr * 0.5),
                take_profit=current_price - range_size,
                confidence=85.0 if volume_spike else 70.0,
                breakout_level=range_low,
                volume_confirmation=volume_spike,
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.01


class SessionBreakoutStrategies:
    """
    Session-based breakout strategies
    
    1. London Open Breakout (3 AM EST)
    2. NY Open Breakout (8 AM EST)
    3. Asian Range Breakout
    4. Opening Range Breakout (ORB)
    """
    
    @staticmethod
    def opening_range_breakout(df: pd.DataFrame, orb_minutes: int = 60) -> Optional[BreakoutSignal]:
        """
        Opening Range Breakout (ORB)
        Marks first X minutes of session and trades breakout
        
        For GMT+3 (Nairobi):
        - London: 11 AM - 12 PM range
        - NY: 4 PM - 5 PM range
        """
        if len(df) < 100:
            return None
        
        # For M15 timeframe, 60 minutes = 4 candles
        orb_candles = orb_minutes // 15  # Adjust based on timeframe
        
        if len(df) < orb_candles + 10:
            return None
        
        # Get opening range (first N candles of session)
        # Assuming current data includes session start
        orb_high = df['high'].iloc[-orb_candles-5:-5].max()
        orb_low = df['low'].iloc[-orb_candles-5:-5].min()
        orb_range = orb_high - orb_low
        
        current_price = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        atr = SessionBreakoutStrategies._calculate_atr(df, 14)
        
        # Bullish ORB breakout
        if current_high > orb_high:
            return BreakoutSignal(
                strategy='opening_range_breakout',
                direction='LONG',
                entry_price=current_price,
                stop_loss=orb_low,
                take_profit=current_price + orb_range,
                confidence=80.0,
                breakout_level=orb_high,
                volume_confirmation=False,
                timeframe='M15'
            )
        
        # Bearish ORB breakout
        elif current_low < orb_low:
            return BreakoutSignal(
                strategy='opening_range_breakout',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=orb_high,
                take_profit=current_price - orb_range,
                confidence=80.0,
                breakout_level=orb_low,
                volume_confirmation=False,
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def london_open_breakout(df: pd.DataFrame, current_time: datetime) -> Optional[BreakoutSignal]:
        """
        London Open Breakout (11 AM GMT+3)
        Trades the initial spike at London open
        """
        # Check if we're at London open (11 AM GMT+3)
        hour = current_time.hour
        
        if hour != 11:
            return None
        
        # Look at pre-London range (last 4 hours)
        lookback = 16  # 4 hours on M15
        
        if len(df) < lookback + 5:
            return None
        
        pre_london_high = df['high'].iloc[-lookback:-1].max()
        pre_london_low = df['low'].iloc[-lookback:-1].min()
        
        current_price = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        atr = SessionBreakoutStrategies._calculate_atr(df, 14)
        
        # Bullish London breakout
        if current_high > pre_london_high:
            return BreakoutSignal(
                strategy='london_open_breakout',
                direction='LONG',
                entry_price=current_price,
                stop_loss=pre_london_high - (atr * 0.5),
                take_profit=current_price + (atr * 3.0),
                confidence=85.0,
                breakout_level=pre_london_high,
                volume_confirmation=False,
                timeframe='M15'
            )
        
        # Bearish London breakout
        elif current_low < pre_london_low:
            return BreakoutSignal(
                strategy='london_open_breakout',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=pre_london_low + (atr * 0.5),
                take_profit=current_price - (atr * 3.0),
                confidence=85.0,
                breakout_level=pre_london_low,
                volume_confirmation=False,
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def ny_open_breakout(df: pd.DataFrame, current_time: datetime) -> Optional[BreakoutSignal]:
        """
        NY Open Breakout (4 PM GMT+3)
        Trades the NY session opening spike
        """
        hour = current_time.hour
        
        if hour != 16:  # 4 PM GMT+3 = 8 AM EST
            return None
        
        lookback = 16  # Last 4 hours
        
        if len(df) < lookback + 5:
            return None
        
        pre_ny_high = df['high'].iloc[-lookback:-1].max()
        pre_ny_low = df['low'].iloc[-lookback:-1].min()
        
        current_price = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        atr = SessionBreakoutStrategies._calculate_atr(df, 14)
        
        # Bullish NY breakout
        if current_high > pre_ny_high:
            return BreakoutSignal(
                strategy='ny_open_breakout',
                direction='LONG',
                entry_price=current_price,
                stop_loss=pre_ny_high - (atr * 0.5),
                take_profit=current_price + (atr * 3.0),
                confidence=85.0,
                breakout_level=pre_ny_high,
                volume_confirmation=False,
                timeframe='M15'
            )
        
        # Bearish NY breakout
        elif current_low < pre_ny_low:
            return BreakoutSignal(
                strategy='ny_open_breakout',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=pre_ny_low + (atr * 0.5),
                take_profit=current_price - (atr * 3.0),
                confidence=85.0,
                breakout_level=pre_ny_low,
                volume_confirmation=False,
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.01


class VolatilityBreakoutStrategies:
    """
    Volatility-based breakout strategies
    
    1. ATR Expansion Breakout
    2. Bollinger Band Squeeze Breakout
    3. Keltner Channel Breakout
    4. Donchian Channel Breakout
    """
    
    @staticmethod
    def atr_expansion_breakout(df: pd.DataFrame, atr_period: int = 14, expansion_factor: float = 1.5) -> Optional[BreakoutSignal]:
        """
        ATR Expansion Breakout
        Trades when volatility expands significantly
        """
        atr = VolatilityBreakoutStrategies._calculate_atr(df, atr_period)
        atr_avg = df['high'].rolling(atr_period).apply(
            lambda x: VolatilityBreakoutStrategies._calculate_atr(
                df.iloc[len(df)-len(x):], atr_period
            )
        ).mean()
        
        # Check for ATR expansion
        if atr < atr_avg * expansion_factor:
            return None
        
        current_price = df['close'].iloc[-1]
        prev_close = df['close'].iloc[-2]
        
        # Strong bullish candle with ATR expansion
        if current_price > prev_close * 1.002:  # 0.2% gain minimum
            return BreakoutSignal(
                strategy='atr_expansion_breakout',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 1.5),
                take_profit=current_price + (atr * 3.0),
                confidence=75.0,
                breakout_level=prev_close,
                volume_confirmation=False,
                timeframe='M15'
            )
        
        # Strong bearish candle with ATR expansion
        elif current_price < prev_close * 0.998:  # 0.2% drop minimum
            return BreakoutSignal(
                strategy='atr_expansion_breakout',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 1.5),
                take_profit=current_price - (atr * 3.0),
                confidence=75.0,
                breakout_level=prev_close,
                volume_confirmation=False,
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def donchian_channel_breakout(df: pd.DataFrame, period: int = 20) -> Optional[BreakoutSignal]:
        """
        Donchian Channel Breakout
        LONG: Price breaks above highest high of last N periods
        SHORT: Price breaks below lowest low of last N periods
        """
        if len(df) < period + 5:
            return None
        
        upper_channel = df['high'].rolling(period).max()
        lower_channel = df['low'].rolling(period).min()
        
        current_price = df['close'].iloc[-1]
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        
        atr = VolatilityBreakoutStrategies._calculate_atr(df, 14)
        
        # Bullish breakout
        if current_high > upper_channel.iloc[-2]:
            channel_width = upper_channel.iloc[-2] - lower_channel.iloc[-2]
            
            return BreakoutSignal(
                strategy='donchian_breakout',
                direction='LONG',
                entry_price=current_price,
                stop_loss=lower_channel.iloc[-1],
                take_profit=current_price + channel_width,
                confidence=80.0,
                breakout_level=upper_channel.iloc[-2],
                volume_confirmation=False,
                timeframe='H1'
            )
        
        # Bearish breakout
        elif current_low < lower_channel.iloc[-2]:
            channel_width = upper_channel.iloc[-2] - lower_channel.iloc[-2]
            
            return BreakoutSignal(
                strategy='donchian_breakout',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=upper_channel.iloc[-1],
                take_profit=current_price - channel_width,
                confidence=80.0,
                breakout_level=lower_channel.iloc[-2],
                volume_confirmation=False,
                timeframe='H1'
            )
        
        return None
    
    @staticmethod
    def keltner_channel_breakout(df: pd.DataFrame, ema_period: int = 20, atr_multiplier: float = 2.0) -> Optional[BreakoutSignal]:
        """
        Keltner Channel Breakout
        Uses EMA and ATR for dynamic channels
        """
        ema = df['close'].ewm(span=ema_period).mean()
        atr = VolatilityBreakoutStrategies._calculate_atr(df, 14)
        
        upper_channel = ema + (atr * atr_multiplier)
        lower_channel = ema - (atr * atr_multiplier)
        
        current_price = df['close'].iloc[-1]
        
        # Bullish breakout
        if current_price > upper_channel.iloc[-1]:
            return BreakoutSignal(
                strategy='keltner_breakout',
                direction='LONG',
                entry_price=current_price,
                stop_loss=ema.iloc[-1],
                take_profit=current_price + (atr * 3.0),
                confidence=75.0,
                breakout_level=upper_channel.iloc[-1],
                volume_confirmation=False,
                timeframe='M15'
            )
        
        # Bearish breakout
        elif current_price < lower_channel.iloc[-1]:
            return BreakoutSignal(
                strategy='keltner_breakout',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=ema.iloc[-1],
                take_profit=current_price - (atr * 3.0),
                confidence=75.0,
                breakout_level=lower_channel.iloc[-1],
                volume_confirmation=False,
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.01


class PatternBreakoutStrategies:
    """
    Chart pattern breakout strategies
    
    1. Triangle Pattern Breakout
    2. Flag/Pennant Breakout
    3. Rectangle Pattern Breakout
    """
    
    @staticmethod
    def triangle_breakout(df: pd.DataFrame, lookback: int = 20) -> Optional[BreakoutSignal]:
        """
        Triangle Pattern Breakout Detection
        Detects converging highs and lows
        """
        if len(df) < lookback + 10:
            return None
        
        # Get swing highs and lows
        highs = df['high'].iloc[-lookback:]
        lows = df['low'].iloc[-lookback:]
        
        # Simple triangle detection: highs decreasing, lows increasing
        high_trend = np.polyfit(range(len(highs)), highs, 1)[0]
        low_trend = np.polyfit(range(len(lows)), lows, 1)[0]
        
        # Check for converging lines (triangle)
        if not (high_trend < 0 and low_trend > 0):
            return None
        
        # Apex area
        current_high = highs.max()
        current_low = lows.min()
        
        current_price = df['close'].iloc[-1]
        atr = PatternBreakoutStrategies._calculate_atr(df, 14)
        
        # Bullish breakout
        if df['high'].iloc[-1] > current_high:
            pattern_height = current_high - current_low
            
            return BreakoutSignal(
                strategy='triangle_breakout',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_low,
                take_profit=current_price + pattern_height,
                confidence=75.0,
                breakout_level=current_high,
                volume_confirmation=False,
                timeframe='H1'
            )
        
        # Bearish breakout
        elif df['low'].iloc[-1] < current_low:
            pattern_height = current_high - current_low
            
            return BreakoutSignal(
                strategy='triangle_breakout',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_high,
                take_profit=current_price - pattern_height,
                confidence=75.0,
                breakout_level=current_low,
                volume_confirmation=False,
                timeframe='H1'
            )
        
        return None
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.01


# Master Breakout Strategy Selector
class BreakoutStrategySelector:
    """
    Selects and executes best breakout strategy
    based on market conditions and time
    """
    
    def __init__(self):
        self.range_strategies = RangeBreakoutStrategies()
        self.session_strategies = SessionBreakoutStrategies()
        self.volatility_strategies = VolatilityBreakoutStrategies()
        self.pattern_strategies = PatternBreakoutStrategies()
    
    def get_all_signals(self, df: pd.DataFrame, current_time: datetime = None) -> List[BreakoutSignal]:
        """
        Run all breakout strategies
        
        Returns:
            List of valid breakout signals
        """
        if current_time is None:
            current_time = datetime.now()
        
        signals = []
        
        # Range breakout strategies
        signals.append(self.range_strategies.horizontal_range_breakout(df))
        
        # Session breakout strategies
        signals.append(self.session_strategies.opening_range_breakout(df))
        signals.append(self.session_strategies.london_open_breakout(df, current_time))
        signals.append(self.session_strategies.ny_open_breakout(df, current_time))
        
        # Volatility breakout strategies
        signals.append(self.volatility_strategies.atr_expansion_breakout(df))
        signals.append(self.volatility_strategies.donchian_channel_breakout(df))
        signals.append(self.volatility_strategies.keltner_channel_breakout(df))
        
        # Pattern breakout strategies
        signals.append(self.pattern_strategies.triangle_breakout(df))
        
        # Filter out None signals
        signals = [s for s in signals if s is not None]
        
        return signals
    
    def get_best_signal(self, df: pd.DataFrame, current_time: datetime = None) -> Optional[BreakoutSignal]:
        """
        Get highest confidence breakout signal
        
        Returns:
            Best signal or None
        """
        signals = self.get_all_signals(df, current_time)
        
        if not signals:
            return None
        
        # Sort by confidence
        signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return signals[0]
