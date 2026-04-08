"""
SCALPING & SWING TRADING STRATEGIES - COMPLETE
All scalping and swing strategies for forex/metals
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List
from dataclasses import dataclass


@dataclass
class ScalpSignal:
    strategy: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    pips_target: float
    timeframe: str = 'M1'


@dataclass
class SwingSignal:
    strategy: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    confidence: float
    holding_days: int
    timeframe: str = 'H4'


class ScalpingStrategies:
    """All scalping strategies"""
    
    @staticmethod
    def ema_scalp(df: pd.DataFrame) -> Optional[ScalpSignal]:
        """EMA 5/13/26 scalping system"""
        ema5 = df['close'].ewm(span=5).mean()
        ema13 = df['close'].ewm(span=13).mean()
        ema26 = df['close'].ewm(span=26).mean()
        
        current_price = df['close'].iloc[-1]
        atr = df['high'].rolling(14).mean() - df['low'].rolling(14).mean()
        atr_val = atr.iloc[-1] if len(atr) > 0 else 0.0001
        
        if (ema5.iloc[-2] <= ema13.iloc[-2] and ema5.iloc[-1] > ema13.iloc[-1] and
            current_price > ema26.iloc[-1]):
            return ScalpSignal('ema_scalp', 'LONG', current_price,
                             ema26.iloc[-1], current_price + atr_val * 0.5,
                             75.0, atr_val * 0.5, 'M1')
        
        elif (ema5.iloc[-2] >= ema13.iloc[-2] and ema5.iloc[-1] < ema13.iloc[-1] and
              current_price < ema26.iloc[-1]):
            return ScalpSignal('ema_scalp', 'SHORT', current_price,
                             ema26.iloc[-1], current_price - atr_val * 0.5,
                             75.0, atr_val * 0.5, 'M1')
        return None
    
    @staticmethod
    def bb_scalp(df: pd.DataFrame) -> Optional[ScalpSignal]:
        """Bollinger Band scalping"""
        sma = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        if current_price <= lower.iloc[-1]:
            return ScalpSignal('bb_scalp', 'LONG', current_price,
                             current_price - atr * 0.3, sma.iloc[-1],
                             80.0, atr * 0.5, 'M5')
        elif current_price >= upper.iloc[-1]:
            return ScalpSignal('bb_scalp', 'SHORT', current_price,
                             current_price + atr * 0.3, sma.iloc[-1],
                             80.0, atr * 0.5, 'M5')
        return None


class SwingStrategies:
    """All swing trading strategies"""
    
    @staticmethod
    def fib_swing(df: pd.DataFrame) -> Optional[SwingSignal]:
        """Fibonacci swing trading"""
        if len(df) < 50:
            return None
        
        high = df['high'].iloc[-50:].max()
        low = df['low'].iloc[-50:].min()
        fib_range = high - low
        
        fib_618 = high - (fib_range * 0.618)
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        if abs(current_price - fib_618) < atr * 0.5:
            ema50 = df['close'].ewm(span=50).mean()
            if ema50.iloc[-1] > ema50.iloc[-10]:
                return SwingSignal('fib_swing', 'LONG', current_price, low - atr * 0.5,
                                 high, high + fib_range * 0.27, high + fib_range * 0.618,
                                 80.0, 5, 'H4')
        return None
    
    @staticmethod
    def macd_divergence_swing(df: pd.DataFrame) -> Optional[SwingSignal]:
        """MACD divergence swing"""
        exp1 = df['close'].ewm(span=12).mean()
        exp2 = df['close'].ewm(span=26).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9).mean()
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        if macd.iloc[-2] <= signal.iloc[-2] and macd.iloc[-1] > signal.iloc[-1]:
            return SwingSignal('macd_div_swing', 'LONG', current_price,
                             current_price - atr * 2, current_price + atr * 3,
                             current_price + atr * 5, current_price + atr * 8,
                             75.0, 7, 'H4')
        return None


class ScalpSwingSelector:
    """Master selector for scalping and swing strategies"""
    
    def __init__(self):
        self.scalp = ScalpingStrategies()
        self.swing = SwingStrategies()
    
    def get_scalp_signals(self, df: pd.DataFrame) -> List[ScalpSignal]:
        signals = []
        signals.append(self.scalp.ema_scalp(df))
        signals.append(self.scalp.bb_scalp(df))
        return [s for s in signals if s is not None]
    
    def get_swing_signals(self, df: pd.DataFrame) -> List[SwingSignal]:
        signals = []
        signals.append(self.swing.fib_swing(df))
        signals.append(self.swing.macd_divergence_swing(df))
        return [s for s in signals if s is not None]
    
    def get_best_scalp(self, df: pd.DataFrame) -> Optional[ScalpSignal]:
        signals = self.get_scalp_signals(df)
        return max(signals, key=lambda x: x.confidence) if signals else None
    
    def get_best_swing(self, df: pd.DataFrame) -> Optional[SwingSignal]:
        signals = self.get_swing_signals(df)
        return max(signals, key=lambda x: x.confidence) if signals else None
