"""
Advanced Market Regime Detection System
Classifies market as: STRONG_TREND, WEAK_TREND, RANGING, BREAKOUT, HIGH_VOLATILITY
"""

import numpy as np
import MetaTrader5 as mt5
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class MarketRegime(Enum):
    STRONG_TREND = "STRONG_TREND"
    WEAK_TREND = "WEAK_TREND"
    RANGING = "RANGING"
    BREAKOUT = "BREAKOUT"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    NEUTRAL = "NEUTRAL"


@dataclass
class RegimeAnalysis:
    regime: MarketRegime
    confidence: float
    trend_strength: float
    volatility_level: float
    structure_quality: float
    allowed_strategies: list
    risk_multiplier: float


class AdvancedMarketRegimeDetector:
    """
    Professional-grade regime detection using multiple confirmation layers
    """
    
    def __init__(self):
        self.adx_strong_threshold = 30
        self.adx_weak_threshold = 20
        self.volatility_expansion_threshold = 1.3
        self.volatility_compression_threshold = 0.7
        
    def detect_regime(
        self,
        symbol: str,
        timeframe: int,
        lookback: int = 50
    ) -> RegimeAnalysis:
        """
        Comprehensive regime detection
        """
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is None or len(rates) < lookback:
            return self._neutral_regime()
        
        high = rates['high']
        low = rates['low']
        close = rates['close']
        
        # Layer 1: Trend Strength (ADX)
        adx = self._calculate_adx(high, low, close, period=14)
        
        # Layer 2: EMA Structure
        ema_structure = self._analyze_ema_structure(close)
        
        # Layer 3: Volatility Analysis
        volatility_analysis = self._analyze_volatility(high, low, close)
        
        # Layer 4: Price Action Structure
        structure_quality = self._analyze_structure(high, low, close)
        
        # Layer 5: Market Momentum
        momentum_score = self._calculate_momentum_score(close)
        
        # Classify regime
        regime, confidence = self._classify_regime(
            adx[-1],
            ema_structure,
            volatility_analysis,
            structure_quality,
            momentum_score
        )
        
        # Determine allowed strategies
        allowed_strategies = self._get_allowed_strategies(regime)
        
        # Calculate risk multiplier
        risk_multiplier = self._calculate_risk_multiplier(
            regime,
            volatility_analysis['current_vs_average']
        )
        
        return RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            trend_strength=adx[-1] if adx is not None else 0,
            volatility_level=volatility_analysis['current_vs_average'],
            structure_quality=structure_quality,
            allowed_strategies=allowed_strategies,
            risk_multiplier=risk_multiplier
        )
    
    def _calculate_adx(self, high, low, close, period=14) -> Optional[np.ndarray]:
        """Calculate ADX indicator"""
        try:
            # True Range
            tr1 = high - low
            tr2 = np.abs(high - np.roll(close, 1))
            tr3 = np.abs(low - np.roll(close, 1))
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            
            # Directional Movement
            up_move = high - np.roll(high, 1)
            down_move = np.roll(low, 1) - low
            
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            
            # Smooth
            atr = self._ema(tr, period)
            plus_di = 100 * self._ema(plus_dm, period) / atr
            minus_di = 100 * self._ema(minus_dm, period) / atr
            
            # ADX
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
            adx = self._ema(dx, period)
            
            return adx
        except:
            return None
    
    def _ema(self, data, period):
        """Calculate EMA"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def _analyze_ema_structure(self, close) -> Dict:
        """Analyze EMA alignment and slope"""
        ema_20 = self._ema(close, 20)
        ema_50 = self._ema(close, 50)
        ema_200 = self._ema(close, 200)
        
        # Check alignment
        bullish_alignment = (ema_20[-1] > ema_50[-1] > ema_200[-1])
        bearish_alignment = (ema_20[-1] < ema_50[-1] < ema_200[-1])
        
        # Calculate slopes
        ema_20_slope = (ema_20[-1] - ema_20[-5]) / ema_20[-5]
        ema_50_slope = (ema_50[-1] - ema_50[-5]) / ema_50[-5]
        
        return {
            'bullish_alignment': bullish_alignment,
            'bearish_alignment': bearish_alignment,
            'trend_aligned': bullish_alignment or bearish_alignment,
            'ema_20_slope': ema_20_slope,
            'ema_50_slope': ema_50_slope,
            'slope_strength': abs(ema_20_slope) + abs(ema_50_slope)
        }
    
    def _analyze_volatility(self, high, low, close) -> Dict:
        """Comprehensive volatility analysis"""
        # ATR
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        atr = self._ema(tr, 14)
        atr_avg = np.mean(atr[-50:])
        
        current_vs_average = atr[-1] / atr_avg if atr_avg > 0 else 1.0
        
        # Volatility trend
        atr_slope = (atr[-1] - atr[-10]) / atr[-10] if atr[-10] > 0 else 0
        
        # Bollinger Band Width
        sma_20 = np.mean(close[-20:])
        std_20 = np.std(close[-20:])
        bb_width = (std_20 * 4) / sma_20 if sma_20 > 0 else 0
        
        return {
            'current_atr': atr[-1],
            'average_atr': atr_avg,
            'current_vs_average': current_vs_average,
            'atr_slope': atr_slope,
            'bb_width': bb_width,
            'is_expanding': current_vs_average > self.volatility_expansion_threshold,
            'is_compressing': current_vs_average < self.volatility_compression_threshold
        }
    
    def _analyze_structure(self, high, low, close) -> float:
        """
        Analyze price action structure quality
        Returns 0.0 to 1.0 score
        """
        structure_score = 0.5
        
        # Check for higher highs / lower lows
        recent_highs = high[-20:]
        recent_lows = low[-20:]
        
        higher_highs = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i] > recent_highs[i-1])
        lower_lows = sum(1 for i in range(1, len(recent_lows)) if recent_lows[i] < recent_lows[i-1])
        
        if higher_highs > 15:
            structure_score = 0.9  # Strong uptrend structure
        elif lower_lows > 15:
            structure_score = 0.9  # Strong downtrend structure
        elif higher_highs < 5 and lower_lows < 5:
            structure_score = 0.3  # Ranging/choppy structure
        
        return structure_score
    
    def _calculate_momentum_score(self, close) -> float:
        """Calculate momentum score 0-1"""
        # Rate of change
        roc_10 = (close[-1] - close[-10]) / close[-10] if close[-10] > 0 else 0
        roc_20 = (close[-1] - close[-20]) / close[-20] if close[-20] > 0 else 0
        
        momentum_score = (abs(roc_10) * 2 + abs(roc_20)) / 3
        return min(momentum_score * 10, 1.0)  # Normalize to 0-1
    
    def _classify_regime(
        self,
        adx: float,
        ema_structure: Dict,
        volatility: Dict,
        structure_quality: float,
        momentum_score: float
    ) -> Tuple[MarketRegime, float]:
        """
        Main classification logic
        """
        confidence = 0.5
        
        # STRONG TREND
        if (adx > self.adx_strong_threshold and
            ema_structure['trend_aligned'] and
            structure_quality > 0.7 and
            momentum_score > 0.5):
            return MarketRegime.STRONG_TREND, min(0.7 + (adx - 30) / 100, 0.95)
        
        # WEAK TREND
        if (adx > self.adx_weak_threshold and
            ema_structure['trend_aligned'] and
            structure_quality > 0.5):
            return MarketRegime.WEAK_TREND, 0.65
        
        # BREAKOUT
        if (volatility['is_expanding'] and
            volatility['atr_slope'] > 0.2 and
            momentum_score > 0.6):
            return MarketRegime.BREAKOUT, min(0.7 + momentum_score * 0.2, 0.9)
        
        # HIGH VOLATILITY
        if volatility['current_vs_average'] > 1.5:
            return MarketRegime.HIGH_VOLATILITY, 0.8
        
        # RANGING
        if (adx < self.adx_weak_threshold and
            not ema_structure['trend_aligned'] and
            volatility['is_compressing']):
            return MarketRegime.RANGING, 0.7
        
        # NEUTRAL
        return MarketRegime.NEUTRAL, 0.5
    
    def _get_allowed_strategies(self, regime: MarketRegime) -> list:
        """Determine which strategies are allowed in this regime"""
        strategy_map = {
            MarketRegime.STRONG_TREND: ['trend_following', 'pullback'],
            MarketRegime.WEAK_TREND: ['trend_following', 'pullback', 'breakout'],
            MarketRegime.RANGING: ['mean_reversion', 'range_bounce'],
            MarketRegime.BREAKOUT: ['breakout', 'momentum'],
            MarketRegime.HIGH_VOLATILITY: ['momentum', 'breakout'],
            MarketRegime.NEUTRAL: []
        }
        
        return strategy_map.get(regime, [])
    
    def _calculate_risk_multiplier(self, regime: MarketRegime, volatility_ratio: float) -> float:
        """
        Adjust risk based on regime and volatility
        """
        base_multiplier = {
            MarketRegime.STRONG_TREND: 1.0,
            MarketRegime.WEAK_TREND: 0.8,
            MarketRegime.RANGING: 0.7,
            MarketRegime.BREAKOUT: 1.2,
            MarketRegime.HIGH_VOLATILITY: 0.6,
            MarketRegime.NEUTRAL: 0.5
        }.get(regime, 0.5)
        
        # Adjust for volatility
        if volatility_ratio > 1.5:
            base_multiplier *= 0.7
        elif volatility_ratio > 1.2:
            base_multiplier *= 0.85
        
        return max(0.3, min(base_multiplier, 1.5))
    
    def _neutral_regime(self) -> RegimeAnalysis:
        """Return neutral regime when data is insufficient"""
        return RegimeAnalysis(
            regime=MarketRegime.NEUTRAL,
            confidence=0.3,
            trend_strength=0.0,
            volatility_level=1.0,
            structure_quality=0.5,
            allowed_strategies=[],
            risk_multiplier=0.5
        )
