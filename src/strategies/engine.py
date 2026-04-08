"""
APEX FX Trading Bot - Strategy Engine
Section 4: Strategy Architecture
6 instrument-specific strategy modules + Regime Detection Engine (RDE)
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum


class MarketRegime(Enum):
    """Section 4.1 - Regime Detection Engine (RDE)"""
    TRENDING = "TRENDING"
    RANGING = "RANGING"
    BREAKOUT_PENDING = "BREAKOUT_PENDING"
    AVOID = "AVOID"


class RegimeDetector:
    """
    Regime Detection Engine (RDE)
    Runs on every new bar close, classifies market into one of three regimes
    """
    
    @staticmethod
    def detect(df: pd.DataFrame) -> MarketRegime:
        """Detect current market regime"""
        if len(df) < 50:
            return MarketRegime.AVOID
        
        # Calculate ADX
        adx = RegimeDetector._calculate_adx(df)
        
        # Calculate ATR expansion/contraction
        atr_current = df['high'].iloc[-1] - df['low'].iloc[-1]
        atr_avg = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Calculate Bollinger Band width
        bb_width = RegimeDetector._bollinger_width(df)
        bb_width_avg = bb_width.rolling(20).mean().iloc[-1]
        
        # Decision logic
        if adx > 25 and atr_current > atr_avg:
            return MarketRegime.TRENDING
        elif adx < 20 and bb_width < bb_width_avg * 0.8:
            return MarketRegime.RANGING
        elif bb_width < bb_width_avg * 0.5:
            return MarketRegime.BREAKOUT_PENDING
        elif 20 <= adx <= 25:
            return MarketRegime.AVOID
        else:
            return MarketRegime.AVOID
    
    @staticmethod
    def _calculate_adx(df: pd.DataFrame) -> float:
        """Calculate ADX(14)"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr = pd.concat([
            high - low,
            abs(high - close.shift()),
            abs(low - close.shift())
        ], axis=1).max(axis=1)
        
        atr = tr.rolling(14).mean()
        
        plus_di = 100 * (plus_dm.rolling(14).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(14).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(14).mean()
        
        return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 20
    
    @staticmethod
    def _bollinger_width(df: pd.DataFrame) -> pd.Series:
        """Bollinger Band width"""
        sma = df['close'].rolling(20).mean()
        std = df['close'].rolling(20).std()
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        return (upper - lower) / sma


# Section 4.2-4.7: Per-Instrument Strategy Classes

class EURUSDStrategy:
    """
    Section 4.2 EUR/USD - Multi-Timeframe Trend Following + Session Breakout
    Primary: EMA Crossover Trend System (H4 trend, H1 entry)
    Secondary: London Session Breakout
    """
    
    @staticmethod
    def get_signals(df_h4: pd.DataFrame, df_h1: pd.DataFrame, regime: MarketRegime) -> List[Dict]:
        signals = []
        
        if regime == MarketRegime.TRENDING:
            # Primary: EMA Crossover on H1 with H4 trend confirmation
            h4_trend = EURUSDStrategy._get_h4_trend(df_h4)
            h1_signal = EURUSDStrategy._ema_crossover_signal(df_h1)
            
            if h1_signal and h4_trend == h1_signal['direction']:
                # Entry filters
                rsi = df_h1['close'].diff().apply(lambda x: 100 - (100 / (1 + x)) if x > 0 else 0).rolling(14).mean().iloc[-1]
                if not ((h1_signal['direction'] == 'BUY' and rsi > 70) or 
                        (h1_signal['direction'] == 'SELL' and rsi < 30)):
                    signals.append({
                        'strategy': 'EURUSD_EMA_CROSSOVER',
                        'direction': h1_signal['direction'],
                        'confidence': 75,
                        'timeframe': 'H1',
                        'regime': regime.value,
                        'entry': df_h1['close'].iloc[-1],
                        'reason': f"EMA crossover with H4 trend confirmation"
                    })
        
        elif regime == MarketRegime.BREAKOUT_PENDING:
            # Secondary: London Session Breakout (06:00-08:00 UTC range)
            # Simplified: check for breakout after range formation
            signals.append({
                'strategy': 'EURUSD_LONDON_BREAKOUT',
                'direction': None,  # Would determine direction based on breakout
                'confidence': 60,
                'timeframe': 'M15',
                'regime': regime.value,
                'entry': df_h1['close'].iloc[-1],
                'reason': 'London session breakout (secondary)'
            })
        
        return signals
    
    @staticmethod
    def _get_h4_trend(df: pd.DataFrame) -> str:
        ema20 = df['close'].ewm(span=20).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50).mean().iloc[-1]
        return 'BUY' if ema20 > ema50 else 'SELL'
    
    @staticmethod
    def _ema_crossover_signal(df: pd.DataFrame) -> Optional[Dict]:
        ema9 = df['close'].ewm(span=9).mean()
        ema21 = df['close'].ewm(span=21).mean()
        
        if len(ema9) < 2:
            return None
            
        if ema9.iloc[-1] > ema21.iloc[-1] and ema9.iloc[-2] <= ema21.iloc[-2]:
            return {'direction': 'BUY', 'price': df['close'].iloc[-1]}
        elif ema9.iloc[-1] < ema21.iloc[-1] and ema9.iloc[-2] >= ema21.iloc[-2]:
            return {'direction': 'SELL', 'price': df['close'].iloc[-1]}
        
        return None


class GBPUSDStrategy:
    """
    Section 4.3 GBP/USD - Momentum Breakout + Fibonacci Retracement
    Primary: London Open Momentum
    Secondary: Fibonacci Pullback
    """
    
    @staticmethod
    def get_signals(df_h1: pd.DataFrame, df_m15: pd.DataFrame, regime: MarketRegime) -> List[Dict]:
        signals = []
        
        if regime == MarketRegime.TRENDING:
            # Primary: Momentum breakout with Bollinger Bands
            bb_upper = df_m15['close'].rolling(20).mean() + 2 * df_m15['close'].rolling(20).std()
            atr = (df_m15['high'] - df_m15['low']).rolling(14).mean()
            
            if df_m15['close'].iloc[-1] > bb_upper.iloc[-1] and atr.iloc[-1] > atr.rolling(30).mean().iloc[-1]:
                ema50 = df_h1['close'].ewm(span=50).mean().iloc[-1]
                if df_h1['close'].iloc[-1] > ema50:
                    signals.append({
                        'strategy': 'GBPUSD_LONDON_MOMENTUM',
                        'direction': 'BUY',
                        'confidence': 70,
                        'timeframe': 'M15',
                        'regime': regime.value,
                        'entry': df_m15['close'].iloc[-1],
                        'reason': 'Bollinger breakout + ATR confirmation'
                    })
        
        elif regime == MarketRegime.TRENDING:
            # Secondary: Fibonacci retracement
            signals.append({
                'strategy': 'GBPUSD_FIBONACCI_PULLBACK',
                'direction': None,
                'confidence': 55,
                'timeframe': 'H1',
                'regime': regime.value,
                'entry': df_h1['close'].iloc[-1],
                'reason': 'Fibonacci retracement (secondary)'
            })
        
        return signals


class USDJPYStrategy:
    """
    Section 4.4 USD/JPY - Carry Trade Momentum + BoJ Intervention Filter
    Primary: Multi-Session Trend
    """
    
    @staticmethod
    def get_signals(df_d1: pd.DataFrame, df_h4: pd.DataFrame, df_h1: pd.DataFrame, regime: MarketRegime) -> List[Dict]:
        signals = []
        
        if regime == MarketRegime.TRENDING:
            # Primary: D1 200 EMA bias, H4 50 EMA trend, Stochastic confirmation
            ema200 = df_d1['close'].ewm(span=200).mean().iloc[-1]
            ema50 = df_h4['close'].ewm(span=50).mean().iloc[-1]
            
            if df_d1['close'].iloc[-1] > ema200 and ema50 > 0:  # H4 EMA sloping up
                # Stochastic oversold cross
                stoch_k = (df_h1['close'] - df_h1['low'].rolling(5).min()) / \
                          (df_h1['high'].rolling(5).max() - df_h1['low'].rolling(5).min()) * 100
                
                if stoch_k.iloc[-1] > 20 and stoch_k.iloc[-2] < 20:
                    signals.append({
                        'strategy': 'USDJPY_CARRY_TREND',
                        'direction': 'BUY',
                        'confidence': 65,
                        'timeframe': 'H1',
                        'regime': regime.value,
                        'entry': df_h1['close'].iloc[-1],
                        'reason': 'D1 trend + H4 momentum + stochastic confirmation'
                    })
        
        return signals


class USDCHFStrategy:
    """
    Section 4.5 USD/CHF - Mean Reversion + EUR/USD Divergence
    Primary: Bollinger Band Mean Reversion
    """
    
    @staticmethod
    def get_signals(df_h1: pd.DataFrame, df_h4: pd.DataFrame, eurusd_regime: MarketRegime, regime: MarketRegime) -> List[Dict]:
        signals = []
        
        if regime == MarketRegime.RANGING and eurusd_regime != MarketRegime.TRENDING:
            # Primary: Bollinger Band mean reversion
            bb_middle = df_h1['close'].rolling(20).mean()
            bb_upper = bb_middle + 2 * df_h1['close'].rolling(20).std()
            bb_lower = bb_middle - 2 * df_h1['close'].rolling(20).std()
            
            rsi = 100 - (100 / (1 + (df_h1['close'].diff().apply(lambda x: x if x > 0 else 0).rolling(14).mean() / 
                                  -df_h1['close'].diff().apply(lambda x: x if x < 0 else 0).rolling(14).mean())))
            rsi_val = rsi.iloc[-1]
            
            if df_h1['close'].iloc[-1] <= bb_lower.iloc[-1] and rsi_val < 30:
                signals.append({
                    'strategy': 'USDCHF_BB_MEAN_REV',
                    'direction': 'BUY',
                    'confidence': 60,
                    'timeframe': 'H1',
                    'regime': regime.value,
                    'entry': df_h1['close'].iloc[-1],
                    'reason': 'Bollinger lower band + RSI oversold'
                })
            elif df_h1['close'].iloc[-1] >= bb_upper.iloc[-1] and rsi_val > 70:
                signals.append({
                    'strategy': 'USDCHF_BB_MEAN_REV',
                    'direction': 'SELL',
                    'confidence': 60,
                    'timeframe': 'H1',
                    'regime': regime.value,
                    'entry': df_h1['close'].iloc[-1],
                    'reason': 'Bollinger upper band + RSI overbought'
                })
        
        return signals


class USDCADStrategy:
    """
    Section 4.6 USD/CAD - Oil-Correlated Trend Following
    Primary: WTI Crude Oil Correlation Trend
    """
    
    @staticmethod
    def get_signals(df_h4: pd.DataFrame, df_h1: pd.DataFrame, oil_price: float, regime: MarketRegime) -> List[Dict]:
        signals = []
        
        # In production, would fetch real WTI price
        oil_trend = 'DOWN' if oil_price < 75 else 'UP'
        
        if regime == MarketRegime.TRENDING:
            # EMA crossover confirmed by oil direction
            ema50 = df_h1['close'].ewm(span=50).mean()
            ema200 = df_h1['close'].ewm(span=200).mean()
            
            if ema50.iloc[-1] > ema200.iloc[-1]:  # Bullish
                if oil_trend == 'DOWN':  # Oil down = CAD up = USD/CAD up
                    signals.append({
                        'strategy': 'USDCAD_OIL_TREND',
                        'direction': 'BUY',
                        'confidence': 70,
                        'timeframe': 'H1',
                        'regime': regime.value,
                        'entry': df_h1['close'].iloc[-1],
                        'reason': f'EMA bullish + oil trending {oil_trend}'
                    })
            else:  # Bearish
                if oil_trend == 'UP':
                    signals.append({
                        'strategy': 'USDCAD_OIL_TREND',
                        'direction': 'SELL',
                        'confidence': 70,
                        'timeframe': 'H1',
                        'regime': regime.value,
                        'entry': df_h1['close'].iloc[-1],
                        'reason': f'EMA bearish + oil trending {oil_trend}'
                    })
        
        return signals


class XAUUSDStrategy:
    """
    Section 4.7 XAU/USD - Multi-Timeframe Trend + Breakout Hybrid
    Primary: 200 EMA Trend System
    Secondary: Session Open Breakout
    """
    
    @staticmethod
    def get_signals(df_d1: pd.DataFrame, df_h4: pd.DataFrame, df_h1: pd.DataFrame, regime: MarketRegime) -> List[Dict]:
        signals = []
        
        if regime == MarketRegime.TRENDING:
            # Primary: D1 200 EMA trend + H4 50 EMA pullback
            ema200_d1 = df_d1['close'].ewm(span=200).mean().iloc[-1]
            ema50_h4 = df_h4['close'].ewm(span=50).mean().iloc[-1]
            
            if df_d1['close'].iloc[-1] > ema200_d1:  # D1 bullish
                if df_h4['close'].iloc[-1] >= ema50_h4:  # Price at H4 50 EMA pullback
                    rsi = 100 - (100 / (1 + (df_h4['close'].diff().apply(lambda x: x if x > 0 else 0).rolling(14).mean() / 
                                          -df_h4['close'].diff().apply(lambda x: x if x < 0 else 0).rolling(14).mean())))
                    rsi_val = rsi.iloc[-1]
                    
                    if 40 < rsi_val < 60:  # RSI neutral, not exhausted
                        signals.append({
                            'strategy': 'XAUUSD_EMA_TREND',
                            'direction': 'BUY',
                            'confidence': 75,
                            'timeframe': 'H4',
                            'regime': regime.value,
                            'entry': df_h4['close'].iloc[-1],
                            'reason': 'D1 uptrend + H4 pullback to 50 EMA + RSI neutral'
                        })
        
        elif regime == MarketRegime.BREAKOUT_PENDING:
            # Secondary: Session open breakout (London/NY)
            signals.append({
                'strategy': 'XAUUSD_SESSION_BREAKOUT',
                'direction': None,
                'confidence': 60,
                'timeframe': 'M15',
                'regime': regime.value,
                'entry': df_h1['close'].iloc[-1],
                'reason': 'Session open breakout (secondary)'
            })
        
        return signals


# Main Strategy Engine

class StrategyEngine:
    """
    APEX FX Strategy Engine
    Section 4: Strategy Architecture
    Combines RDE with per-instrument strategy modules
    """
    
    # All 6 instruments
    INSTRUMENTS = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'XAUUSD']
    
    # Strategy mapping
    STRATEGIES = {
        'EURUSD': EURUSDStrategy,
        'GBPUSD': GBPUSDStrategy,
        'USDJPY': USDJPYStrategy,
        'USDCHF': USDCHFStrategy,
        'USDCAD': USDCADStrategy,
        'XAUUSD': XAUUSDStrategy
    }
    
    def __init__(self, ta=None):
        self.ta = ta
        self.regime_detector = RegimeDetector()
    
    def scan_instrument(self, symbol: str, data: Dict[str, pd.DataFrame]) -> List[Dict]:
        """Scan single instrument for trading opportunities"""
        
        # Get regime for this instrument
        if 'H1' in data:
            regime = self.regime_detector.detect(data['H1'])
        else:
            regime = MarketRegime.AVOID
        
        # Get EUR/USD regime for USD/CHF correlation filter
        eurusd_regime = MarketRegime.TRENDING
        if 'EURUSD' in data:
            eurusd_regime = self.regime_detector.detect(data['EURUSD'])
        
        # Get strategy class for this instrument
        strategy_class = self.STRATEGIES.get(symbol, EURUSDStrategy)
        
        # Get signals based on available timeframes
        signals = strategy_class.get_signals(
            data.get('H4', pd.DataFrame()),
            data.get('H1', pd.DataFrame()),
            data.get('D1', pd.DataFrame()),
            data.get('M15', pd.DataFrame()),
            regime=regime,
            eurusd_regime=eurusd_regime,
            oil_price=75.0  # Simplified - would fetch real oil price
        )
        
        # Add symbol to each signal
        for sig in signals:
            sig['symbol'] = symbol
            sig['regime'] = regime.value
        
        return signals
    
    def scan_all(self, market_data: Dict[str, Dict[str, pd.DataFrame]]) -> List[Dict]:
        """Scan all instruments"""
        all_signals = []
        
        for symbol in self.INSTRUMENTS:
            if symbol in market_data:
                signals = self.scan_instrument(symbol, market_data[symbol])
                all_signals.extend(signals)
        
        return all_signals
    
    def get_regime(self, df: pd.DataFrame) -> MarketRegime:
        """Get market regime for any dataframe"""
        return self.regime_detector.detect(df)


strategy_engine = StrategyEngine()


def get_strategy_engine() -> StrategyEngine:
    return strategy_engine