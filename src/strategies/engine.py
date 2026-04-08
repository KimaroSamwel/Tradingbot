"""
APEX FX Trading Bot - Strategy Engine
6 Strategy Categories with 30+ Strategies
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from datetime import datetime
import json


class StrategyEngine:
    """Multi-strategy trading engine"""
    
    CATEGORIES = {
        'TREND': 'Trend Following',
        'MEAN_REVERSION': 'Mean Reversion',
        'BREAKOUT': 'Breakout',
        'GRID': 'Grid Trading',
        'SCALPING': 'Scalping',
        'CUSTOM': 'Custom/AI'
    }
    
    def __init__(self, ta=None):
        self.ta = ta
        self.active_strategies = []
        self.strategy_params = {}
        
    def scan_symbol(self, symbol: str, df: pd.DataFrame, category: str = None) -> List[Dict[str, Any]]:
        """Scan symbol for trading opportunities"""
        signals = []
        
        # Calculate indicators
        if self.ta:
            indicators = self.ta.calculate_all(df)
        else:
            from src.analysis.technical import TechnicalAnalysis
            self.ta = TechnicalAnalysis()
            indicators = self.ta.calculate_all(df)
        
        # Scan by category
        if category:
            signals.extend(self._scan_category(category, symbol, df, indicators))
        else:
            for cat in self.CATEGORIES.keys():
                signals.extend(self._scan_category(cat, symbol, df, indicators))
        
        return signals
    
    def _scan_category(self, category: str, symbol: str, df: pd.DataFrame, indicators: Dict) -> List[Dict]:
        """Scan specific category"""
        strategies = {
            'TREND': self._scan_trend_strategies,
            'MEAN_REVERSION': self._scan_mean_reversion_strategies,
            'BREAKOUT': self._scan_breakout_strategies,
            'GRID': self._scan_grid_strategies,
            'SCALPING': self._scan_scalping_strategies,
            'CUSTOM': self._scan_custom_strategies
        }
        
        return strategies.get(category, lambda s, d, i: [])(symbol, df, indicators)
    
    # ==================== TREND STRATEGIES ====================
    
    def _scan_trend_strategies(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> List[Dict]:
        """Scan trend-based strategies"""
        signals = []
        trend = indicators.get('trend', {})
        momentum = indicators.get('momentum', {})
        
        # EMA Crossover Strategy
        if trend.get('ema_9_above_21') == 1 and trend.get('price_above_sma200') == 1:
            signals.append({
                'id': f'{symbol}_EMA_CROSSUP_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'EMA_CROSSUP',
                'category': 'TREND',
                'direction': 'BUY',
                'entry_price': df['close'].iloc[-1],
                'sl_price': trend.get('sma_50', df['close'].iloc[-1] * 0.99),
                'tp_price': df['close'].iloc[-1] * 1.02,
                'confidence': 75,
                'indicators': trend,
                'reason': 'EMA 9/21 crossover with price above SMA200'
            })
        
        # EMA Crossover Down
        if trend.get('ema_9_above_21') == 0 and trend.get('price_above_sma200') == 0:
            signals.append({
                'id': f'{symbol}_EMA_CROSSDOWN_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'EMA_CROSSDOWN',
                'category': 'TREND',
                'direction': 'SELL',
                'entry_price': df['close'].iloc[-1],
                'sl_price': trend.get('sma_50', df['close'].iloc[-1] * 1.01),
                'tp_price': df['close'].iloc[-1] * 0.98,
                'confidence': 75,
                'indicators': trend,
                'reason': 'EMA 9/21 crossover down with price below SMA200'
            })
        
        # Supertrend Strategy
        if trend.get('supertrend'):
            price = df['close'].iloc[-1]
            psar = trend.get('supertrend', price)
            if price > psar:
                signals.append({
                    'id': f'{symbol}_SUPERTREND_BUY_{datetime.now().timestamp()}',
                    'symbol': symbol,
                    'strategy': 'SUPERTREND_BUY',
                    'category': 'TREND',
                    'direction': 'BUY',
                    'entry_price': price,
                    'sl_price': price * 0.98,
                    'tp_price': price * 1.03,
                    'confidence': 70,
                    'indicators': trend,
                    'reason': 'Supertrend bullish signal'
                })
        
        # Ichimoku Strategy
        if trend.get('tenkan_sen') and trend.get('kijun_sen'):
            if trend['tenkan_sen'] > trend['kijun_sen'] and trend['chikou_span'] < df['close'].iloc[-1]:
                signals.append({
                    'id': f'{symbol}_ICHIMOKU_BUY_{datetime.now().timestamp()}',
                    'symbol': symbol,
                    'strategy': 'ICHIMOKU_BUY',
                    'category': 'TREND',
                    'direction': 'BUY',
                    'entry_price': df['close'].iloc[-1],
                    'sl_price': trend.get('senkou_b', df['close'].iloc[-1] * 0.98),
                    'tp_price': trend.get('senkou_a', df['close'].iloc[-1] * 1.03),
                    'confidence': 65,
                    'indicators': trend,
                    'reason': 'Ichimoku cloud bullish'
                })
        
        return signals
    
    # ==================== MEAN REVERSION STRATEGIES ====================
    
    def _scan_mean_reversion_strategies(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> List[Dict]:
        """Scan mean reversion strategies"""
        signals = []
        momentum = indicators.get('momentum', {})
        volatility = indicators.get('volatility', {})
        
        # RSI Oversold
        rsi = momentum.get('rsi_14', 50)
        if rsi < 30:
            signals.append({
                'id': f'{symbol}_RSI_OVERSOLD_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'RSI_OVERSOLD',
                'category': 'MEAN_REVERSION',
                'direction': 'BUY',
                'entry_price': df['close'].iloc[-1],
                'sl_price': df['close'].iloc[-1] * 0.98,
                'tp_price': df['close'].iloc[-1] * 1.02,
                'confidence': 70,
                'indicators': momentum,
                'reason': f'RSI oversold at {rsi}'
            })
        
        # RSI Overbought
        if rsi > 70:
            signals.append({
                'id': f'{symbol}_RSI_OVERBOUGHT_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'RSI_OVERBOUGHT',
                'category': 'MEAN_REVERSION',
                'direction': 'SELL',
                'entry_price': df['close'].iloc[-1],
                'sl_price': df['close'].iloc[-1] * 1.02,
                'tp_price': df['close'].iloc[-1] * 0.98,
                'confidence': 70,
                'indicators': momentum,
                'reason': f'RSI overbought at {rsi}'
            })
        
        # Bollinger Bands Bounce
        bb = volatility.get('bb_position', 0.5)
        if bb < 0.1:
            signals.append({
                'id': f'{symbol}_BB_BOUNCE_BUY_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'BB_BOUNCE_BUY',
                'category': 'MEAN_REVERSION',
                'direction': 'BUY',
                'entry_price': df['close'].iloc[-1],
                'sl_price': volatility.get('bb_lower'),
                'tp_price': volatility.get('bb_middle'),
                'confidence': 65,
                'indicators': volatility,
                'reason': 'Price at lower Bollinger Band'
            })
        
        # Stochastic Oversold
        stoch_k = momentum.get('stoch_k', 50)
        stoch_d = momentum.get('stoch_d', 50)
        if stoch_k < 20 and stoch_d < 20:
            signals.append({
                'id': f'{symbol}_STOCH_OVERSOLD_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'STOCH_OVERSOLD',
                'category': 'MEAN_REVERSION',
                'direction': 'BUY',
                'entry_price': df['close'].iloc[-1],
                'sl_price': df['close'].iloc[-1] * 0.99,
                'tp_price': df['close'].iloc[-1] * 1.015,
                'confidence': 60,
                'indicators': momentum,
                'reason': f'Stochastic oversold ({stoch_k:.0f})'
            })
        
        return signals
    
    # ==================== BREAKOUT STRATEGIES ====================
    
    def _scan_breakout_strategies(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> List[Dict]:
        """Scan breakout strategies"""
        signals = []
        volatility = indicators.get('volatility', {})
        pattern = indicators.get('pattern', {})
        
        # Donchian Breakout Up
        if volatility.get('dc_upper') and df['close'].iloc[-1] > volatility['dc_upper']:
            signals.append({
                'id': f'{symbol}_DC_BREAKOUT_UP_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'DC_BREAKOUT_UP',
                'category': 'BREAKOUT',
                'direction': 'BUY',
                'entry_price': df['close'].iloc[-1],
                'sl_price': volatility.get('dc_middle'),
                'tp_price': volatility.get('dc_upper') * 1.02,
                'confidence': 75,
                'indicators': volatility,
                'reason': 'Donchian channel breakout up'
            })
        
        # Donchian Breakout Down
        if volatility.get('dc_lower') and df['close'].iloc[-1] < volatility['dc_lower']:
            signals.append({
                'id': f'{symbol}_DC_BREAKOUT_DOWN_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'DC_BREAKOUT_DOWN',
                'category': 'BREAKOUT',
                'direction': 'SELL',
                'entry_price': df['close'].iloc[-1],
                'sl_price': volatility.get('dc_middle'),
                'tp_price': volatility.get('dc_lower') * 0.98,
                'confidence': 75,
                'indicators': volatility,
                'reason': 'Donchian channel breakout down'
            })
        
        # Higher Highs Breakout
        if pattern.get('higher_highs'):
            signals.append({
                'id': f'{symbol}_HH_BREAKOUT_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'HH_BREAKOUT',
                'category': 'BREAKOUT',
                'direction': 'BUY',
                'entry_price': df['close'].iloc[-1],
                'sl_price': df['close'].iloc[-1] * 0.98,
                'tp_price': df['close'].iloc[-1] * 1.025,
                'confidence': 70,
                'indicators': pattern,
                'reason': 'Higher highs pattern'
            })
        
        return signals
    
    # ==================== GRID STRATEGIES ====================
    
    def _scan_grid_strategies(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> List[Dict]:
        """Scan grid strategies - returns neutral signals for grid placement"""
        signals = []
        
        # Range-bound market for grid
        volatility = indicators.get('volatility', {})
        bb_width = volatility.get('bb_width', 0)
        
        if bb_width < 0.05:  # Low volatility = good for grid
            mid = volatility.get('bb_middle', df['close'].iloc[-1])
            lower = volatility.get('bb_lower', mid * 0.99)
            upper = volatility.get('bb_upper', mid * 1.01)
            
            signals.append({
                'id': f'{symbol}_GRID_RANGE_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'GRID_RANGE',
                'category': 'GRID',
                'direction': 'NEUTRAL',
                'entry_price': mid,
                'sl_price': lower,
                'tp_price': upper,
                'confidence': 60,
                'indicators': volatility,
                'reason': f'Grid setup: Lower={lower:.5f}, Upper={upper:.5f}'
            })
        
        return signals
    
    # ==================== SCALPING STRATEGIES ====================
    
    def _scan_scalping_strategies(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> List[Dict]:
        """Scan scalping strategies"""
        signals = []
        momentum = indicators.get('momentum', {})
        volume = indicators.get('volume', {})
        
        # AO Zero Line Cross
        ao = momentum.get('awesome_oscillator', 0)
        if ao > 0 and ao < momentum.get('awesome_oscillator', 0):
            signals.append({
                'id': f'{symbol}_AO_SCALE_BUY_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'AO_SCALE_BUY',
                'category': 'SCALPING',
                'direction': 'BUY',
                'entry_price': df['close'].iloc[-1],
                'sl_price': df['close'].iloc[-1] * 0.998,
                'tp_price': df['close'].iloc[-1] * 1.003,
                'confidence': 55,
                'indicators': momentum,
                'reason': 'AO bullish cross for scalping'
            })
        
        # Volume Spike
        vol_ratio = volume.get('volume_ratio', 1)
        if vol_ratio > 2:
            signals.append({
                'id': f'{symbol}_VOLUME_SPIKE_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'VOLUME_SPIKE',
                'category': 'SCALPING',
                'direction': 'BUY' if df['close'].iloc[-1] > df['close'].iloc[-2] else 'SELL',
                'entry_price': df['close'].iloc[-1],
                'sl_price': df['close'].iloc[-1] * 0.999,
                'tp_price': df['close'].iloc[-1] * 1.002,
                'confidence': 50,
                'indicators': volume,
                'reason': f'Volume spike ({vol_ratio:.1f}x average)'
            })
        
        return signals
    
    # ==================== CUSTOM/AI STRATEGIES ====================
    
    def _scan_custom_strategies(self, symbol: str, df: pd.DataFrame, indicators: Dict) -> List[Dict]:
        """Scan custom/AI strategies"""
        signals = []
        
        # Multi-factor confluence
        trend = indicators.get('trend', {})
        momentum = indicators.get('momentum', {})
        volatility = indicators.get('volatility', {})
        
        # Confluence BUY: EMA aligned + RSI not overbought + not at resistance
        rsi = momentum.get('rsi_14', 50)
        near_resistance = pattern = indicators.get('pattern', {})
        near_r = near_resistance.get('near_resistance', False)
        
        if (trend.get('ema_9_above_21') == 1 and 
            30 < rsi < 70 and 
            not near_r):
            signals.append({
                'id': f'{symbol}_CONFLUENCE_BUY_{datetime.now().timestamp()}',
                'symbol': symbol,
                'strategy': 'CONFLUENCE_BUY',
                'category': 'CUSTOM',
                'direction': 'BUY',
                'entry_price': df['close'].iloc[-1],
                'sl_price': trend.get('sma_50', df['close'].iloc[-1] * 0.99),
                'tp_price': df['close'].iloc[-1] * 1.02,
                'confidence': 80,
                'indicators': indicators,
                'reason': 'Multi-factor confluence BUY'
            })
        
        return signals
    
    def get_available_strategies(self) -> List[Dict[str, Any]]:
        """Get list of all available strategies"""
        return [
            # Trend
            {'id': 'EMA_CROSSUP', 'name': 'EMA Crossover Up', 'category': 'TREND', 'description': 'EMA 9/21 bullish crossover'},
            {'id': 'EMA_CROSSDOWN', 'name': 'EMA Crossover Down', 'category': 'TREND', 'description': 'EMA 9/21 bearish crossover'},
            {'id': 'SUPERTREND_BUY', 'name': 'Supertrend Buy', 'category': 'TREND', 'description': 'Supertrend bullish signal'},
            {'id': 'ICHIMOKU_BUY', 'name': 'Ichimoku Buy', 'category': 'TREND', 'description': 'Ichimoku cloud bullish'},
            
            # Mean Reversion
            {'id': 'RSI_OVERSOLD', 'name': 'RSI Oversold', 'category': 'MEAN_REVERSION', 'description': 'RSI below 30'},
            {'id': 'RSI_OVERBOUGHT', 'name': 'RSI Overbought', 'category': 'MEAN_REVERSION', 'description': 'RSI above 70'},
            {'id': 'BB_BOUNCE_BUY', 'name': 'BB Bounce Buy', 'category': 'MEAN_REVERSION', 'description': 'Price at lower BB'},
            {'id': 'STOCH_OVERSOLD', 'name': 'Stochastic Oversold', 'category': 'MEAN_REVERSION', 'description': 'Stochastic below 20'},
            
            # Breakout
            {'id': 'DC_BREAKOUT_UP', 'name': 'Donchian Breakout Up', 'category': 'BREAKOUT', 'description': 'Break above DC upper'},
            {'id': 'DC_BREAKOUT_DOWN', 'name': 'Donchian Breakout Down', 'category': 'BREAKOUT', 'description': 'Break below DC lower'},
            {'id': 'HH_BREAKOUT', 'name': 'Higher Highs', 'category': 'BREAKOUT', 'description': 'Higher highs pattern'},
            
            # Grid
            {'id': 'GRID_RANGE', 'name': 'Grid Range', 'category': 'GRID', 'description': 'Range-bound for grid'},
            
            # Scalping
            {'id': 'AO_SCALE_BUY', 'name': 'AO Scalp Buy', 'category': 'SCALPING', 'description': 'AO zero cross'},
            {'id': 'VOLUME_SPIKE', 'name': 'Volume Spike', 'category': 'SCALPING', 'description': 'Volume spike entry'},
            
            # Custom
            {'id': 'CONFLUENCE_BUY', 'name': 'Confluence Buy', 'category': 'CUSTOM', 'description': 'Multi-factor confluence'}
        ]


# Global instance
strategy_engine = StrategyEngine()


def get_strategy_engine() -> StrategyEngine:
    """Get global strategy engine instance"""
    return strategy_engine