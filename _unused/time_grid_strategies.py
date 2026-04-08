"""
TIME-BASED & GRID STRATEGIES COLLECTION
Implementation of time-based and grid trading strategies

Time-Based Strategies:
- Day of Week Patterns
- Time of Day Patterns
- Turn of Month Effect
- London Fix Trading
- NY Close Strategy
- Weekend Gap Trading

Grid Strategies:
- Grid Trading System
- Fibonacci Grid
- Mean Reversion Grid
- Pivot Point Trading
"""

import pandas as pd
import numpy as np
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime, time as dt_time


@dataclass
class TimeBasedSignal:
    strategy: str
    time_pattern: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    time_factor: str
    timeframe: str


@dataclass
class GridSignal:
    strategy: str
    grid_type: str
    entry_levels: List[float]
    stop_loss: float
    take_profit: float
    grid_spacing: float
    confidence: float
    timeframe: str


class DayOfWeekStrategy:
    """Day of Week Pattern Trading"""
    
    PATTERNS = {
        'Monday': {'bias': 'neutral', 'volatility': 'high'},
        'Tuesday': {'bias': 'continuation', 'volatility': 'medium'},
        'Wednesday': {'bias': 'continuation', 'volatility': 'medium'},
        'Thursday': {'bias': 'reversal', 'volatility': 'medium'},
        'Friday': {'bias': 'reversal', 'volatility': 'high'}
    }
    
    @staticmethod
    def analyze(df: pd.DataFrame, current_time: datetime) -> Optional[TimeBasedSignal]:
        """Day of Week Pattern Analysis"""
        if len(df) < 20:
            return None
        
        day_name = current_time.strftime('%A')
        pattern = DayOfWeekStrategy.PATTERNS.get(day_name, {})
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Monday: Range expansion after weekend
        if day_name == 'Monday':
            weekend_gap = abs(df['open'].iloc[-1] - df['close'].iloc[-2])
            if weekend_gap > atr * 0.5:
                # Fade the gap
                if df['open'].iloc[-1] > df['close'].iloc[-2]:
                    return TimeBasedSignal(
                        strategy='day_of_week',
                        time_pattern='MONDAY_GAP_FADE',
                        direction='SHORT',
                        entry_price=current_price,
                        stop_loss=df['open'].iloc[-1] + (atr * 0.5),
                        take_profit=df['close'].iloc[-2],
                        confidence=70.0,
                        time_factor='monday_gap',
                        timeframe='H1'
                    )
        
        # Friday: Position squaring
        elif day_name == 'Friday':
            # Trend reversal likely
            ema_20 = df['close'].ewm(span=20).mean()
            if current_price > ema_20.iloc[-1] * 1.01:
                return TimeBasedSignal(
                    strategy='day_of_week',
                    time_pattern='FRIDAY_REVERSAL',
                    direction='SHORT',
                    entry_price=current_price,
                    stop_loss=current_price + (atr * 1.5),
                    take_profit=ema_20.iloc[-1],
                    confidence=65.0,
                    time_factor='friday_close',
                    timeframe='H4'
                )
        
        return None


class TimeOfDayStrategy:
    """Time of Day Pattern Trading"""
    
    @staticmethod
    def analyze(df: pd.DataFrame, current_time: datetime) -> Optional[TimeBasedSignal]:
        """Time of Day Pattern Analysis"""
        if len(df) < 20:
            return None
        
        hour = current_time.hour
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # London Fix (4 PM GMT = varies by timezone)
        # For GMT+3 Nairobi: London 4 PM = 7 PM local
        if hour == 19:  # 7 PM GMT+3
            # Gold often volatile around London fix
            return TimeBasedSignal(
                strategy='time_of_day',
                time_pattern='LONDON_FIX',
                direction='LONG',  # Direction based on price action
                entry_price=current_price,
                stop_loss=current_price - (atr * 1.0),
                take_profit=current_price + (atr * 2.0),
                confidence=70.0,
                time_factor='london_4pm_fix',
                timeframe='M15'
            )
        
        # NY Close (5 PM EST = 1 AM GMT+3)
        elif hour == 1:
            return TimeBasedSignal(
                strategy='time_of_day',
                time_pattern='NY_CLOSE',
                direction='SHORT',  # Often reversal
                entry_price=current_price,
                stop_loss=current_price + (atr * 1.0),
                take_profit=current_price - (atr * 2.0),
                confidence=65.0,
                time_factor='ny_close_reversal',
                timeframe='M15'
            )
        
        return None


class TurnOfMonthStrategy:
    """Turn of Month Effect Trading"""
    
    @staticmethod
    def analyze(df: pd.DataFrame, current_time: datetime) -> Optional[TimeBasedSignal]:
        """Turn of Month Pattern"""
        if len(df) < 20:
            return None
        
        day_of_month = current_time.day
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Last 3 days of month and first 3 days of new month
        if day_of_month >= 28 or day_of_month <= 3:
            # Historically bullish period
            ema_50 = df['close'].ewm(span=50).mean()
            
            if current_price > ema_50.iloc[-1]:
                return TimeBasedSignal(
                    strategy='turn_of_month',
                    time_pattern='MONTH_END_BULLISH',
                    direction='LONG',
                    entry_price=current_price,
                    stop_loss=ema_50.iloc[-1],
                    take_profit=current_price + (atr * 3.0),
                    confidence=70.0,
                    time_factor='turn_of_month',
                    timeframe='D1'
                )
        
        return None


class GridTradingStrategy:
    """Grid Trading System"""
    
    @staticmethod
    def create_grid(df: pd.DataFrame, num_levels: int = 5, 
                    spacing_atr: float = 1.0) -> Optional[GridSignal]:
        """
        Create Grid Trading Levels
        Places buy/sell orders at regular intervals
        """
        if len(df) < 20:
            return None
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        grid_spacing = atr * spacing_atr
        
        # Create grid levels above and below current price
        entry_levels = []
        for i in range(-num_levels//2, num_levels//2 + 1):
            level = current_price + (i * grid_spacing)
            entry_levels.append(level)
        
        return GridSignal(
            strategy='grid_trading',
            grid_type='STANDARD_GRID',
            entry_levels=entry_levels,
            stop_loss=entry_levels[0] - (grid_spacing * 0.5),
            take_profit=entry_levels[-1] + (grid_spacing * 0.5),
            grid_spacing=grid_spacing,
            confidence=75.0,
            timeframe='H1'
        )


class FibonacciGridStrategy:
    """Fibonacci-Based Grid Trading"""
    
    @staticmethod
    def create_fib_grid(df: pd.DataFrame, lookback: int = 50) -> Optional[GridSignal]:
        """
        Fibonacci Grid based on recent range
        """
        if len(df) < lookback:
            return None
        
        range_high = df['high'].iloc[-lookback:].max()
        range_low = df['low'].iloc[-lookback:].min()
        fib_range = range_high - range_low
        
        # Fibonacci levels
        fib_levels = [
            range_low,
            range_low + (fib_range * 0.236),
            range_low + (fib_range * 0.382),
            range_low + (fib_range * 0.500),
            range_low + (fib_range * 0.618),
            range_low + (fib_range * 0.786),
            range_high
        ]
        
        return GridSignal(
            strategy='fibonacci_grid',
            grid_type='FIB_GRID',
            entry_levels=fib_levels,
            stop_loss=range_low - (fib_range * 0.1),
            take_profit=range_high + (fib_range * 0.1),
            grid_spacing=fib_range * 0.236,
            confidence=80.0,
            timeframe='H4'
        )


class PivotPointStrategy:
    """Pivot Point Trading"""
    
    @staticmethod
    def calculate_pivots(df: pd.DataFrame) -> Optional[GridSignal]:
        """
        Calculate Pivot Points (Standard, Fibonacci, Camarilla)
        """
        if len(df) < 2:
            return None
        
        # Use previous day's data
        prev = df.iloc[-2]
        
        # Standard Pivot
        pivot = (prev['high'] + prev['low'] + prev['close']) / 3
        
        # Support and Resistance levels
        r1 = (2 * pivot) - prev['low']
        s1 = (2 * pivot) - prev['high']
        r2 = pivot + (prev['high'] - prev['low'])
        s2 = pivot - (prev['high'] - prev['low'])
        r3 = prev['high'] + 2 * (pivot - prev['low'])
        s3 = prev['low'] - 2 * (prev['high'] - pivot)
        
        levels = [s3, s2, s1, pivot, r1, r2, r3]
        
        return GridSignal(
            strategy='pivot_points',
            grid_type='PIVOT_LEVELS',
            entry_levels=levels,
            stop_loss=s3,
            take_profit=r3,
            grid_spacing=(r1 - pivot),
            confidence=75.0,
            timeframe='D1'
        )


class MeanReversionGridStrategy:
    """Mean Reversion Grid"""
    
    @staticmethod
    def create_mean_grid(df: pd.DataFrame) -> Optional[GridSignal]:
        """
        Grid around mean (SMA) for mean reversion
        """
        if len(df) < 50:
            return None
        
        sma_50 = df['close'].rolling(50).mean().iloc[-1]
        std_dev = df['close'].rolling(50).std().iloc[-1]
        
        # Create grid at standard deviation intervals
        levels = [
            sma_50 - (3 * std_dev),
            sma_50 - (2 * std_dev),
            sma_50 - (1 * std_dev),
            sma_50,
            sma_50 + (1 * std_dev),
            sma_50 + (2 * std_dev),
            sma_50 + (3 * std_dev)
        ]
        
        return GridSignal(
            strategy='mean_reversion_grid',
            grid_type='STATISTICAL_GRID',
            entry_levels=levels,
            stop_loss=levels[0],
            take_profit=levels[-1],
            grid_spacing=std_dev,
            confidence=80.0,
            timeframe='H4'
        )


# Master Time & Grid Strategy Selector
class TimeGridStrategySelector:
    """Master selector for time-based and grid strategies"""
    
    def __init__(self):
        self.day_of_week = DayOfWeekStrategy()
        self.time_of_day = TimeOfDayStrategy()
        self.turn_of_month = TurnOfMonthStrategy()
        self.grid = GridTradingStrategy()
        self.fib_grid = FibonacciGridStrategy()
        self.pivot = PivotPointStrategy()
        self.mean_grid = MeanReversionGridStrategy()
    
    def get_time_signals(self, df: pd.DataFrame, 
                        current_time: datetime = None) -> List[TimeBasedSignal]:
        """Get all time-based signals"""
        if current_time is None:
            current_time = datetime.now()
        
        signals = []
        
        signals.append(self.day_of_week.analyze(df, current_time))
        signals.append(self.time_of_day.analyze(df, current_time))
        signals.append(self.turn_of_month.analyze(df, current_time))
        
        return [s for s in signals if s is not None]
    
    def get_grid_signals(self, df: pd.DataFrame) -> List[GridSignal]:
        """Get all grid trading signals"""
        signals = []
        
        signals.append(self.grid.create_grid(df))
        signals.append(self.fib_grid.create_fib_grid(df))
        signals.append(self.pivot.calculate_pivots(df))
        signals.append(self.mean_grid.create_mean_grid(df))
        
        return [s for s in signals if s is not None]
    
    def get_best_time_signal(self, df: pd.DataFrame, 
                            current_time: datetime = None) -> Optional[TimeBasedSignal]:
        """Get highest confidence time-based signal"""
        signals = self.get_time_signals(df, current_time)
        return max(signals, key=lambda x: x.confidence) if signals else None
    
    def get_best_grid(self, df: pd.DataFrame) -> Optional[GridSignal]:
        """Get highest confidence grid signal"""
        signals = self.get_grid_signals(df)
        return max(signals, key=lambda x: x.confidence) if signals else None
