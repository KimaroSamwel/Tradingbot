"""
Market Regime Detection - CRITICAL FOR ADAPTING TO MARKET CONDITIONS
Classifies markets as: Strong Trend, Weak Trend, Ranging, High Volatility
"""

import pandas as pd
import numpy as np
from typing import Dict, Literal
from enum import Enum


class MarketRegime(Enum):
    """Market regime classifications"""
    STRONG_TREND = "strong_trend"
    WEAK_TREND = "weak_trend"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    NEUTRAL = "neutral"


class MarketRegimeDetector:
    """
    Detect market regime using multiple factors:
    - ADX strength
    - EMA alignment
    - Bollinger Band width
    - ATR ratio
    - Price action
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.regime_history = []
    
    def detect_regime(self, df: pd.DataFrame) -> Dict:
        """
        Identify current market regime
        
        Returns:
            Dict with regime, confidence, and features
        """
        if len(df) < 50:
            return {'regime': MarketRegime.NEUTRAL, 'confidence': 0, 'features': {}}
        
        last = df.iloc[-1]
        
        # Extract features
        features = {
            'adx_strength': last.get('adx', 0),
            'bb_width': last.get('bb_width', 0),
            'atr_ratio': last.get('atr_ratio', 1.0),
            'ema_alignment': self._check_ema_alignment(df),
            'price_bb_position': last.get('bb_position', 0.5),
            'volatility': last.get('volatility', 'normal'),
            'trend_consistency': self._calculate_trend_consistency(df),
            'range_bound_score': self._calculate_range_bound_score(df)
        }
        
        # Determine regime based on decision tree
        regime, confidence = self._classify_regime(features)
        
        # Store history
        self.regime_history.append({
            'regime': regime,
            'confidence': confidence,
            'timestamp': df.index[-1] if hasattr(df.index[-1], 'isoformat') else None
        })
        
        # Keep only last 100 regime detections
        if len(self.regime_history) > 100:
            self.regime_history.pop(0)
        
        return {
            'regime': regime,
            'confidence': confidence,
            'features': features,
            'volatility': features.get('volatility', 'normal'),
            'trend_strength': features.get('adx_strength', 0),
            'recommended_strategy': self._get_recommended_strategy(regime),
            'risk_adjustment': self._get_risk_adjustment(regime)
        }
    
    def _classify_regime(self, features: Dict) -> tuple:
        """
        Classify regime using decision tree logic
        
        Returns:
            (regime, confidence_score)
        """
        adx = features['adx_strength']
        bb_width = features['bb_width']
        atr_ratio = features['atr_ratio']
        ema_aligned = features['ema_alignment']
        trend_consistency = features['trend_consistency']
        range_score = features['range_bound_score']
        
        # Decision tree
        
        # STRONG TREND: High ADX + EMA alignment + trend consistency
        if adx > 30 and ema_aligned >= 0.66 and trend_consistency > 0.7:
            return (MarketRegime.STRONG_TREND, 0.9)
        
        # WEAK TREND: Moderate ADX + some alignment
        if adx > 20 and (ema_aligned > 0.5 or trend_consistency > 0.5):
            return (MarketRegime.WEAK_TREND, 0.7)
        
        # RANGING: Low ADX + narrow BB + high range score
        if adx < 20 and bb_width < 0.02 and range_score > 0.6:
            return (MarketRegime.RANGING, 0.8)
        
        # HIGH VOLATILITY: High ATR ratio + wide BB
        if atr_ratio > 1.5 or bb_width > 0.04:
            return (MarketRegime.HIGH_VOLATILITY, 0.85)
        
        # NEUTRAL: None of the above
        return (MarketRegime.NEUTRAL, 0.5)
    
    def _check_ema_alignment(self, df: pd.DataFrame) -> float:
        """
        Check EMA alignment strength
        Returns 0-1 score (1 = perfect alignment)
        """
        last = df.iloc[-1]
        
        # Check if we have all EMAs
        if not all(col in df.columns for col in ['ema_8', 'ema_21', 'ema_50', 'ema_200']):
            return 0.5
        
        # Bullish alignment: 8 > 21 > 50 > 200
        bullish_count = 0
        if last['ema_8'] > last['ema_21']:
            bullish_count += 1
        if last['ema_21'] > last['ema_50']:
            bullish_count += 1
        if last['ema_50'] > last['ema_200']:
            bullish_count += 1
        
        # Bearish alignment: 8 < 21 < 50 < 200
        bearish_count = 0
        if last['ema_8'] < last['ema_21']:
            bearish_count += 1
        if last['ema_21'] < last['ema_50']:
            bearish_count += 1
        if last['ema_50'] < last['ema_200']:
            bearish_count += 1
        
        # Return max alignment score
        return max(bullish_count, bearish_count) / 3.0
    
    def _calculate_trend_consistency(self, df: pd.DataFrame, lookback: int = 20) -> float:
        """
        Calculate how consistent the trend direction has been
        Returns 0-1 score (1 = very consistent)
        """
        if len(df) < lookback:
            return 0.5
        
        recent = df.tail(lookback)
        
        # Count how many bars close above/below EMA21
        if 'ema_21' not in df.columns:
            return 0.5
        
        above_ema = (recent['close'] > recent['ema_21']).sum()
        below_ema = (recent['close'] < recent['ema_21']).sum()
        
        # Consistency is the max percentage
        consistency = max(above_ema, below_ema) / lookback
        
        return consistency
    
    def _calculate_range_bound_score(self, df: pd.DataFrame, lookback: int = 20) -> float:
        """
        Calculate how range-bound the market is
        Returns 0-1 score (1 = very range-bound)
        """
        if len(df) < lookback:
            return 0.5
        
        recent = df.tail(lookback)
        
        # Calculate range
        high = recent['high'].max()
        low = recent['low'].min()
        range_size = high - low
        
        # Calculate how many times price touched top/bottom of range
        threshold = range_size * 0.1  # 10% threshold
        
        touches_top = (recent['high'] >= (high - threshold)).sum()
        touches_bottom = (recent['low'] <= (low + threshold)).sum()
        
        # More touches = more range-bound
        total_touches = touches_top + touches_bottom
        max_possible = lookback * 2
        
        range_score = total_touches / max_possible
        
        return range_score
    
    def _get_recommended_strategy(self, regime: MarketRegime) -> str:
        """Get recommended trading strategy for regime"""
        recommendations = {
            MarketRegime.STRONG_TREND: "trend_following",
            MarketRegime.WEAK_TREND: "trend_following_conservative",
            MarketRegime.RANGING: "mean_reversion",
            MarketRegime.HIGH_VOLATILITY: "reduce_exposure",
            MarketRegime.NEUTRAL: "wait_for_clarity"
        }
        return recommendations.get(regime, "wait_for_clarity")
    
    def _get_risk_adjustment(self, regime: MarketRegime) -> float:
        """
        Get risk adjustment multiplier for regime
        Returns multiplier (0.5 = half risk, 1.0 = normal, 1.2 = 20% more)
        """
        adjustments = {
            MarketRegime.STRONG_TREND: 1.0,      # Normal risk
            MarketRegime.WEAK_TREND: 0.8,        # Reduce 20%
            MarketRegime.RANGING: 0.7,           # Reduce 30%
            MarketRegime.HIGH_VOLATILITY: 0.6,   # Reduce 40%
            MarketRegime.NEUTRAL: 0.5            # Reduce 50%
        }
        return adjustments.get(regime, 0.5)
    
    def get_regime_statistics(self) -> Dict:
        """Get statistics on recent regime changes"""
        if not self.regime_history:
            return {}
        
        regimes = [r['regime'] for r in self.regime_history]
        
        # Count regime occurrences
        regime_counts = {}
        for regime in MarketRegime:
            regime_counts[regime.value] = regimes.count(regime)
        
        # Current regime
        current = self.regime_history[-1]
        
        # Regime persistence (how long in current regime)
        persistence = 1
        for i in range(len(self.regime_history) - 2, -1, -1):
            if self.regime_history[i]['regime'] == current['regime']:
                persistence += 1
            else:
                break
        
        return {
            'current_regime': current['regime'].value,
            'current_confidence': current['confidence'],
            'persistence': persistence,
            'regime_distribution': regime_counts,
            'total_samples': len(self.regime_history)
        }


class MultiTimeframeRegimeAnalyzer:
    """
    Analyze regime across multiple timeframes
    Higher timeframes override lower timeframes
    """
    
    def __init__(self):
        self.detector = MarketRegimeDetector()
    
    def analyze_multi_timeframe(self, data_dict: Dict[str, pd.DataFrame]) -> Dict:
        """
        Analyze regime across multiple timeframes
        
        Args:
            data_dict: Dictionary with timeframe keys ('M15', 'H1', 'H4', 'D1')
        
        Returns:
            Dict with combined regime analysis
        """
        regimes = {}
        
        # Analyze each timeframe
        for tf, df in data_dict.items():
            regimes[tf] = self.detector.detect_regime(df)
        
        # Higher timeframes have priority
        priority_order = ['D1', 'H4', 'H1', 'M15', 'M5']
        
        primary_regime = None
        for tf in priority_order:
            if tf in regimes and regimes[tf]['confidence'] > 0.7:
                primary_regime = regimes[tf]
                primary_regime['primary_timeframe'] = tf
                break
        
        # If no high confidence regime found, use H1
        if primary_regime is None and 'H1' in regimes:
            primary_regime = regimes['H1']
            primary_regime['primary_timeframe'] = 'H1'
        
        # Check alignment across timeframes
        regime_values = [r['regime'] for r in regimes.values()]
        regime_alignment = len(set(regime_values)) == 1  # All same = aligned
        
        return {
            'primary_regime': primary_regime,
            'all_regimes': regimes,
            'aligned': regime_alignment,
            'alignment_score': self._calculate_alignment_score(regimes)
        }
    
    def _calculate_alignment_score(self, regimes: Dict) -> float:
        """
        Calculate how aligned the regimes are across timeframes
        Returns 0-1 score
        """
        if not regimes:
            return 0.0
        
        regime_values = [r['regime'] for r in regimes.values()]
        
        # Count most common regime
        from collections import Counter
        counts = Counter(regime_values)
        most_common_count = counts.most_common(1)[0][1]
        
        # Alignment score
        return most_common_count / len(regime_values)
