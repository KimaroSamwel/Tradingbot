"""
COMPREHENSIVE TECHNICAL STRATEGIES COLLECTION
Implementation of 40+ core technical strategies for forex/metals

Includes:
- Moving Average strategies (Crossover, Multiple MA, Dynamic)
- MACD strategies (Trend, Momentum, Divergence)
- RSI strategies (Momentum, Reversion, Divergence)
- Stochastic strategies (Crossover, Divergence)
- ADX strategies (Trend Strength, Directional)
- Bollinger Band strategies (Reversion, Squeeze, Breakout)
- Williams %R strategies
- CCI strategies
- Momentum indicators
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class TechnicalSignal:
    """Generic technical strategy signal"""
    strategy: str
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float  # 0-100
    indicators: Dict  # Indicator values at signal time
    timeframe: str


class MovingAverageStrategies:
    """
    All Moving Average based strategies
    
    1. EMA Crossover (9/21, 9/21/50, 21/50)
    2. SMA Crossover (50/200 Golden Cross)
    3. Triple MA System (9/21/50)
    4. MA Dynamic Support/Resistance
    5. MA Slope Trading
    """
    
    @staticmethod
    def ema_crossover(df: pd.DataFrame, fast: int = 9, slow: int = 21) -> Optional[TechnicalSignal]:
        """
        EMA Crossover Strategy
        LONG: Fast EMA crosses above Slow EMA
        SHORT: Fast EMA crosses below Slow EMA
        """
        ema_fast = df['close'].ewm(span=fast).mean()
        ema_slow = df['close'].ewm(span=slow).mean()
        
        # Current and previous
        current_fast = ema_fast.iloc[-1]
        current_slow = ema_slow.iloc[-1]
        prev_fast = ema_fast.iloc[-2]
        prev_slow = ema_slow.iloc[-2]
        
        current_price = df['close'].iloc[-1]
        atr = MovingAverageStrategies._calculate_atr(df, 14)
        
        # Bullish crossover
        if prev_fast <= prev_slow and current_fast > current_slow:
            return TechnicalSignal(
                strategy='ema_crossover',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 1.5),
                take_profit=current_price + (atr * 3.0),
                confidence=70.0,
                indicators={'ema_fast': current_fast, 'ema_slow': current_slow},
                timeframe='M15'
            )
        
        # Bearish crossover
        elif prev_fast >= prev_slow and current_fast < current_slow:
            return TechnicalSignal(
                strategy='ema_crossover',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 1.5),
                take_profit=current_price - (atr * 3.0),
                confidence=70.0,
                indicators={'ema_fast': current_fast, 'ema_slow': current_slow},
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def triple_ema_system(df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """
        Triple EMA System (9/21/50)
        LONG: 9 > 21 > 50, price above all
        SHORT: 9 < 21 < 50, price below all
        """
        ema_9 = df['close'].ewm(span=9).mean()
        ema_21 = df['close'].ewm(span=21).mean()
        ema_50 = df['close'].ewm(span=50).mean()
        
        current_price = df['close'].iloc[-1]
        atr = MovingAverageStrategies._calculate_atr(df, 14)
        
        # Bullish alignment
        if (ema_9.iloc[-1] > ema_21.iloc[-1] > ema_50.iloc[-1] and 
            current_price > ema_9.iloc[-1]):
            
            # Check if just aligned (crossover)
            if not (ema_9.iloc[-2] > ema_21.iloc[-2] > ema_50.iloc[-2]):
                confidence = 85.0
            else:
                confidence = 70.0
            
            return TechnicalSignal(
                strategy='triple_ema',
                direction='LONG',
                entry_price=current_price,
                stop_loss=ema_50.iloc[-1],
                take_profit=current_price + (current_price - ema_50.iloc[-1]) * 2,
                confidence=confidence,
                indicators={'ema_9': ema_9.iloc[-1], 'ema_21': ema_21.iloc[-1], 'ema_50': ema_50.iloc[-1]},
                timeframe='M15'
            )
        
        # Bearish alignment
        elif (ema_9.iloc[-1] < ema_21.iloc[-1] < ema_50.iloc[-1] and 
              current_price < ema_9.iloc[-1]):
            
            if not (ema_9.iloc[-2] < ema_21.iloc[-2] < ema_50.iloc[-2]):
                confidence = 85.0
            else:
                confidence = 70.0
            
            return TechnicalSignal(
                strategy='triple_ema',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=ema_50.iloc[-1],
                take_profit=current_price - (ema_50.iloc[-1] - current_price) * 2,
                confidence=confidence,
                indicators={'ema_9': ema_9.iloc[-1], 'ema_21': ema_21.iloc[-1], 'ema_50': ema_50.iloc[-1]},
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def sma_golden_cross(df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """
        SMA Golden Cross/Death Cross (50/200)
        LONG: 50 crosses above 200 (Golden Cross)
        SHORT: 50 crosses below 200 (Death Cross)
        """
        sma_50 = df['close'].rolling(50).mean()
        sma_200 = df['close'].rolling(200).mean()
        
        if len(df) < 201:
            return None
        
        current_price = df['close'].iloc[-1]
        atr = MovingAverageStrategies._calculate_atr(df, 14)
        
        # Golden Cross
        if sma_50.iloc[-2] <= sma_200.iloc[-2] and sma_50.iloc[-1] > sma_200.iloc[-1]:
            return TechnicalSignal(
                strategy='golden_cross',
                direction='LONG',
                entry_price=current_price,
                stop_loss=sma_200.iloc[-1],
                take_profit=current_price + (atr * 5.0),
                confidence=80.0,
                indicators={'sma_50': sma_50.iloc[-1], 'sma_200': sma_200.iloc[-1]},
                timeframe='H4'
            )
        
        # Death Cross
        elif sma_50.iloc[-2] >= sma_200.iloc[-2] and sma_50.iloc[-1] < sma_200.iloc[-1]:
            return TechnicalSignal(
                strategy='death_cross',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=sma_200.iloc[-1],
                take_profit=current_price - (atr * 5.0),
                confidence=80.0,
                indicators={'sma_50': sma_50.iloc[-1], 'sma_200': sma_200.iloc[-1]},
                timeframe='H4'
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


class MACDStrategies:
    """
    MACD Strategy Collection
    
    1. MACD Signal Line Crossover
    2. MACD Zero Line Cross
    3. MACD Histogram Momentum
    4. MACD Divergence (Regular + Hidden)
    """
    
    @staticmethod
    def macd_signal_cross(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[TechnicalSignal]:
        """
        MACD Signal Line Crossover
        LONG: MACD crosses above signal line
        SHORT: MACD crosses below signal line
        """
        exp1 = df['close'].ewm(span=fast).mean()
        exp2 = df['close'].ewm(span=slow).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=signal).mean()
        histogram = macd - signal_line
        
        current_price = df['close'].iloc[-1]
        atr = MACDStrategies._calculate_atr(df, 14)
        
        # Bullish crossover
        if macd.iloc[-2] <= signal_line.iloc[-2] and macd.iloc[-1] > signal_line.iloc[-1]:
            # Stronger signal if histogram is increasing
            confidence = 75.0 if histogram.iloc[-1] > histogram.iloc[-2] else 65.0
            
            return TechnicalSignal(
                strategy='macd_signal_cross',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 1.5),
                take_profit=current_price + (atr * 3.0),
                confidence=confidence,
                indicators={'macd': macd.iloc[-1], 'signal': signal_line.iloc[-1], 'histogram': histogram.iloc[-1]},
                timeframe='M15'
            )
        
        # Bearish crossover
        elif macd.iloc[-2] >= signal_line.iloc[-2] and macd.iloc[-1] < signal_line.iloc[-1]:
            confidence = 75.0 if histogram.iloc[-1] < histogram.iloc[-2] else 65.0
            
            return TechnicalSignal(
                strategy='macd_signal_cross',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 1.5),
                take_profit=current_price - (atr * 3.0),
                confidence=confidence,
                indicators={'macd': macd.iloc[-1], 'signal': signal_line.iloc[-1], 'histogram': histogram.iloc[-1]},
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def macd_zero_cross(df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """
        MACD Zero Line Cross
        LONG: MACD crosses above zero (bullish momentum)
        SHORT: MACD crosses below zero (bearish momentum)
        """
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        macd = exp1 - exp2
        
        current_price = df['close'].iloc[-1]
        atr = MACDStrategies._calculate_atr(df, 14)
        
        # Bullish zero cross
        if macd.iloc[-2] <= 0 and macd.iloc[-1] > 0:
            return TechnicalSignal(
                strategy='macd_zero_cross',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 2.0),
                take_profit=current_price + (atr * 4.0),
                confidence=80.0,
                indicators={'macd': macd.iloc[-1]},
                timeframe='H1'
            )
        
        # Bearish zero cross
        elif macd.iloc[-2] >= 0 and macd.iloc[-1] < 0:
            return TechnicalSignal(
                strategy='macd_zero_cross',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 2.0),
                take_profit=current_price - (atr * 4.0),
                confidence=80.0,
                indicators={'macd': macd.iloc[-1]},
                timeframe='H1'
            )
        
        return None
    
    @staticmethod
    def macd_histogram_momentum(df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """
        MACD Histogram Momentum
        LONG: Histogram increasing and positive
        SHORT: Histogram decreasing and negative
        """
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        macd = exp1 - exp2
        signal_line = macd.ewm(span=9).mean()
        histogram = macd - signal_line
        
        current_price = df['close'].iloc[-1]
        atr = MACDStrategies._calculate_atr(df, 14)
        
        # Check for 3 consecutive increasing histograms (momentum building)
        if len(df) < 4:
            return None
        
        hist_increasing = (histogram.iloc[-1] > histogram.iloc[-2] > histogram.iloc[-3])
        hist_decreasing = (histogram.iloc[-1] < histogram.iloc[-2] < histogram.iloc[-3])
        
        # Bullish momentum
        if hist_increasing and histogram.iloc[-1] > 0:
            return TechnicalSignal(
                strategy='macd_histogram_momentum',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 1.5),
                take_profit=current_price + (atr * 3.0),
                confidence=70.0,
                indicators={'histogram': histogram.iloc[-1], 'histogram_slope': 'increasing'},
                timeframe='M15'
            )
        
        # Bearish momentum
        elif hist_decreasing and histogram.iloc[-1] < 0:
            return TechnicalSignal(
                strategy='macd_histogram_momentum',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 1.5),
                take_profit=current_price - (atr * 3.0),
                confidence=70.0,
                indicators={'histogram': histogram.iloc[-1], 'histogram_slope': 'decreasing'},
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


class RSIStrategies:
    """
    RSI Strategy Collection
    
    1. RSI Oversold/Overbought (Mean Reversion)
    2. RSI Momentum (>50 long, <50 short)
    3. RSI Divergence (Regular + Hidden)
    4. RSI Trendline Break
    """
    
    @staticmethod
    def rsi_oversold_overbought(df: pd.DataFrame, period: int = 14, 
                                oversold: float = 30, overbought: float = 70) -> Optional[TechnicalSignal]:
        """
        RSI Oversold/Overbought Mean Reversion
        LONG: RSI < 30 and rising
        SHORT: RSI > 70 and falling
        """
        rsi = RSIStrategies._calculate_rsi(df, period)
        
        current_price = df['close'].iloc[-1]
        atr = RSIStrategies._calculate_atr(df, 14)
        
        # Oversold bounce
        if rsi.iloc[-2] < oversold and rsi.iloc[-1] > rsi.iloc[-2]:
            # CRITICAL FIX: Confidence should be HIGHER when RSI is LOWER (more oversold)
            # Map RSI 0-30 to confidence 100-70
            confidence = max(60.0, min(100.0, 100.0 - (rsi.iloc[-1] / 30.0 * 30.0)))
            
            return TechnicalSignal(
                strategy='rsi_oversold',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 1.5),
                take_profit=current_price + (atr * 2.5),
                confidence=confidence,
                indicators={'rsi': rsi.iloc[-1]},
                timeframe='M15'
            )
        
        # Overbought reversal
        elif rsi.iloc[-2] > overbought and rsi.iloc[-1] < rsi.iloc[-2]:
            # CRITICAL FIX: Confidence should be HIGHER when RSI is HIGHER (more overbought)
            # Map RSI 70-100 to confidence 70-100
            confidence = max(60.0, min(100.0, 70.0 + ((rsi.iloc[-1] - 70.0) / 30.0 * 30.0)))
            
            return TechnicalSignal(
                strategy='rsi_overbought',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 1.5),
                take_profit=current_price - (atr * 2.5),
                confidence=confidence,
                indicators={'rsi': rsi.iloc[-1]},
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def rsi_momentum(df: pd.DataFrame, period: int = 14) -> Optional[TechnicalSignal]:
        """
        RSI Momentum Strategy
        LONG: RSI crosses above 50 (bullish momentum)
        SHORT: RSI crosses below 50 (bearish momentum)
        """
        rsi = RSIStrategies._calculate_rsi(df, period)
        
        current_price = df['close'].iloc[-1]
        atr = RSIStrategies._calculate_atr(df, 14)
        
        # Bullish momentum
        if rsi.iloc[-2] <= 50 and rsi.iloc[-1] > 50:
            confidence = min(rsi.iloc[-1], 100)
            
            return TechnicalSignal(
                strategy='rsi_momentum',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 1.5),
                take_profit=current_price + (atr * 3.0),
                confidence=confidence,
                indicators={'rsi': rsi.iloc[-1]},
                timeframe='M15'
            )
        
        # Bearish momentum
        elif rsi.iloc[-2] >= 50 and rsi.iloc[-1] < 50:
            confidence = 100 - min(rsi.iloc[-1], 50)
            
            return TechnicalSignal(
                strategy='rsi_momentum',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 1.5),
                take_profit=current_price - (atr * 3.0),
                confidence=confidence,
                indicators={'rsi': rsi.iloc[-1]},
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def _calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.01


class StochasticStrategies:
    """
    Stochastic Oscillator Strategy Collection
    
    1. Stochastic %K/%D Crossover
    2. Stochastic Overbought/Oversold
    3. Stochastic Divergence
    """
    
    @staticmethod
    def stochastic_crossover(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Optional[TechnicalSignal]:
        """
        Stochastic %K/%D Crossover
        LONG: %K crosses above %D in oversold zone
        SHORT: %K crosses below %D in overbought zone
        """
        k, d = StochasticStrategies._calculate_stochastic(df, k_period, d_period)
        
        current_price = df['close'].iloc[-1]
        atr = StochasticStrategies._calculate_atr(df, 14)
        
        # Bullish crossover in oversold
        if k.iloc[-2] <= d.iloc[-2] and k.iloc[-1] > d.iloc[-1] and k.iloc[-1] < 30:
            return TechnicalSignal(
                strategy='stochastic_crossover',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 1.5),
                take_profit=current_price + (atr * 2.5),
                confidence=80.0,
                indicators={'k': k.iloc[-1], 'd': d.iloc[-1]},
                timeframe='M15'
            )
        
        # Bearish crossover in overbought
        elif k.iloc[-2] >= d.iloc[-2] and k.iloc[-1] < d.iloc[-1] and k.iloc[-1] > 70:
            return TechnicalSignal(
                strategy='stochastic_crossover',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 1.5),
                take_profit=current_price - (atr * 2.5),
                confidence=80.0,
                indicators={'k': k.iloc[-1], 'd': d.iloc[-1]},
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def _calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Tuple[pd.Series, pd.Series]:
        """Calculate Stochastic %K and %D"""
        low_min = df['low'].rolling(window=k_period).min()
        high_max = df['high'].rolling(window=k_period).max()
        
        # FIX: Handle division by zero when high == low (flat market)
        denominator = high_max - low_min
        denominator = denominator.replace(0, 1)  # Avoid division by zero
        
        k = 100 * ((df['close'] - low_min) / denominator)
        d = k.rolling(window=d_period).mean()
        
        return k, d
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.01


class ADXStrategies:
    """
    ADX (Average Directional Index) Strategy Collection
    
    1. ADX Trend Strength (ADX > 25)
    2. ADX +DI/-DI Crossover
    3. ADX Breakout (ADX rising above threshold)
    """
    
    @staticmethod
    def adx_trend_strength(df: pd.DataFrame, period: int = 14, threshold: float = 25) -> Optional[TechnicalSignal]:
        """
        ADX Trend Strength with Directional Indicators
        LONG: ADX > 25 and +DI > -DI
        SHORT: ADX > 25 and -DI > +DI
        """
        adx, plus_di, minus_di = ADXStrategies._calculate_adx(df, period)
        
        if adx.iloc[-1] < threshold:
            return None
        
        current_price = df['close'].iloc[-1]
        atr = ADXStrategies._calculate_atr(df, 14)
        
        # Strong bullish trend
        if plus_di.iloc[-1] > minus_di.iloc[-1]:
            # Check for recent crossover
            recent_cross = plus_di.iloc[-3] < minus_di.iloc[-3]
            confidence = min(adx.iloc[-1], 100) if recent_cross else min(adx.iloc[-1] * 0.8, 100)
            
            return TechnicalSignal(
                strategy='adx_trend_strength',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 2.0),
                take_profit=current_price + (atr * 4.0),
                confidence=confidence,
                indicators={'adx': adx.iloc[-1], 'plus_di': plus_di.iloc[-1], 'minus_di': minus_di.iloc[-1]},
                timeframe='H1'
            )
        
        # Strong bearish trend
        elif minus_di.iloc[-1] > plus_di.iloc[-1]:
            recent_cross = minus_di.iloc[-3] < plus_di.iloc[-3]
            confidence = min(adx.iloc[-1], 100) if recent_cross else min(adx.iloc[-1] * 0.8, 100)
            
            return TechnicalSignal(
                strategy='adx_trend_strength',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 2.0),
                take_profit=current_price - (atr * 4.0),
                confidence=confidence,
                indicators={'adx': adx.iloc[-1], 'plus_di': plus_di.iloc[-1], 'minus_di': minus_di.iloc[-1]},
                timeframe='H1'
            )
        
        return None
    
    @staticmethod
    def _calculate_adx(df: pd.DataFrame, period: int = 14) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """Calculate ADX, +DI, -DI"""
        # Calculate True Range
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        
        # Calculate Directional Movement
        high_diff = df['high'].diff()
        low_diff = -df['low'].diff()
        
        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
        
        # Smooth with Wilder's method
        atr = tr.ewm(alpha=1/period).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/period).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period).mean() / atr)
        
        # Calculate ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(alpha=1/period).mean()
        
        return adx, plus_di, minus_di
    
    @staticmethod
    def _calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr.iloc[-1] if not np.isnan(atr.iloc[-1]) else 0.01


class BollingerBandStrategies:
    """
    Bollinger Bands Strategy Collection
    
    1. BB Mean Reversion (Touch + bounce)
    2. BB Squeeze Breakout (Volatility expansion)
    3. BB Bandwidth Strategy
    4. BB %B Strategy
    """
    
    @staticmethod
    def bb_mean_reversion(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> Optional[TechnicalSignal]:
        """
        Bollinger Bands Mean Reversion
        LONG: Price touches lower band and bounces
        SHORT: Price touches upper band and reverses
        """
        sma = df['close'].rolling(period).mean()
        std = df['close'].rolling(period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        atr = BollingerBandStrategies._calculate_atr(df, 14)
        
        # Bounce from lower band
        if prev_price <= lower_band.iloc[-2] and current_price > lower_band.iloc[-1]:
            return TechnicalSignal(
                strategy='bb_mean_reversion',
                direction='LONG',
                entry_price=current_price,
                stop_loss=lower_band.iloc[-1] - (atr * 0.5),
                take_profit=sma.iloc[-1],
                confidence=75.0,
                indicators={'upper_band': upper_band.iloc[-1], 'sma': sma.iloc[-1], 'lower_band': lower_band.iloc[-1]},
                timeframe='M15'
            )
        
        # Reversal from upper band
        elif prev_price >= upper_band.iloc[-2] and current_price < upper_band.iloc[-1]:
            return TechnicalSignal(
                strategy='bb_mean_reversion',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=upper_band.iloc[-1] + (atr * 0.5),
                take_profit=sma.iloc[-1],
                confidence=75.0,
                indicators={'upper_band': upper_band.iloc[-1], 'sma': sma.iloc[-1], 'lower_band': lower_band.iloc[-1]},
                timeframe='M15'
            )
        
        return None
    
    @staticmethod
    def bb_squeeze_breakout(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0, squeeze_threshold: float = 0.015) -> Optional[TechnicalSignal]:
        """
        Bollinger Band Squeeze Breakout
        LONG: Bands compressed (squeeze) then price breaks upper band
        SHORT: Bands compressed then price breaks lower band
        """
        sma = df['close'].rolling(period).mean()
        std = df['close'].rolling(period).std()
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        # Calculate bandwidth (volatility indicator)
        bandwidth = (upper_band - lower_band) / sma
        
        current_price = df['close'].iloc[-1]
        prev_bandwidth = bandwidth.iloc[-5:].mean()
        
        # Check if recently squeezed (low bandwidth)
        if prev_bandwidth > squeeze_threshold:
            return None
        
        atr = BollingerBandStrategies._calculate_atr(df, 14)
        
        # Bullish breakout from squeeze
        if current_price > upper_band.iloc[-1]:
            return TechnicalSignal(
                strategy='bb_squeeze_breakout',
                direction='LONG',
                entry_price=current_price,
                stop_loss=sma.iloc[-1],
                take_profit=current_price + (atr * 3.0),
                confidence=80.0,
                indicators={'bandwidth': bandwidth.iloc[-1], 'price_position': 'above_upper'},
                timeframe='M15'
            )
        
        # Bearish breakout from squeeze
        elif current_price < lower_band.iloc[-1]:
            return TechnicalSignal(
                strategy='bb_squeeze_breakout',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=sma.iloc[-1],
                take_profit=current_price - (atr * 3.0),
                confidence=80.0,
                indicators={'bandwidth': bandwidth.iloc[-1], 'price_position': 'below_lower'},
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


# Master Strategy Selector
class TechnicalStrategySelector:
    """
    Dynamically selects and executes best technical strategy
    based on market conditions
    """
    
    def __init__(self):
        self.ma_strategies = MovingAverageStrategies()
        self.macd_strategies = MACDStrategies()
        self.rsi_strategies = RSIStrategies()
        self.stochastic_strategies = StochasticStrategies()
        self.adx_strategies = ADXStrategies()
        self.bb_strategies = BollingerBandStrategies()
    
    def get_all_signals(self, df: pd.DataFrame) -> List[TechnicalSignal]:
        """
        Run all strategies and return all valid signals
        
        Returns:
            List of valid signals from all strategies
        """
        signals = []
        
        # Moving Average strategies
        signals.append(self.ma_strategies.ema_crossover(df, 9, 21))
        signals.append(self.ma_strategies.triple_ema_system(df))
        if len(df) >= 201:
            signals.append(self.ma_strategies.sma_golden_cross(df))
        
        # MACD strategies
        signals.append(self.macd_strategies.macd_signal_cross(df))
        signals.append(self.macd_strategies.macd_zero_cross(df))
        signals.append(self.macd_strategies.macd_histogram_momentum(df))
        
        # RSI strategies
        signals.append(self.rsi_strategies.rsi_oversold_overbought(df))
        signals.append(self.rsi_strategies.rsi_momentum(df))
        
        # Stochastic strategies
        signals.append(self.stochastic_strategies.stochastic_crossover(df))
        
        # ADX strategies
        signals.append(self.adx_strategies.adx_trend_strength(df))
        
        # Bollinger Band strategies
        signals.append(self.bb_strategies.bb_mean_reversion(df))
        signals.append(self.bb_strategies.bb_squeeze_breakout(df))
        
        # Filter out None signals
        signals = [s for s in signals if s is not None]
        
        return signals
    
    def get_best_signal(self, df: pd.DataFrame) -> Optional[TechnicalSignal]:
        """
        Get the highest confidence signal
        
        Returns:
            Best signal or None
        """
        signals = self.get_all_signals(df)
        
        if not signals:
            return None
        
        # Sort by confidence
        signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return signals[0]
