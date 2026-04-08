"""
Gold & Silver Specialized Trading Logic
Accounts for unique behavior of precious metals vs forex pairs
"""

import numpy as np
import MetaTrader5 as mt5
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class MetalsAnalysis:
    asset: str  # XAUUSD or XAGUSD
    signal: str  # BULLISH, BEARISH, NEUTRAL
    confidence: float
    gold_silver_ratio: float
    gs_ratio_zscore: float
    usd_correlation: float
    safe_haven_score: float
    momentum_score: float
    volatility_regime: str
    recommended_size_multiplier: float
    key_levels: Dict


class PreciousMetalsEngine:
    """
    Professional precious metals analysis engine
    """
    
    def __init__(self):
        self.normal_gs_ratio_mean = 80.0
        self.normal_gs_ratio_std = 10.0
        
    def analyze_gold(
        self,
        symbol: str = "XAUUSD",
        lookback: int = 100
    ) -> Optional[MetalsAnalysis]:
        """
        Comprehensive gold analysis
        """
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, lookback)
        if rates is None or len(rates) < lookback:
            return None
        
        high = rates['high']
        low = rates['low']
        close = rates['close']
        
        # Factor 1: Gold/Silver Ratio
        gs_analysis = self._analyze_gold_silver_ratio()
        
        # Factor 2: USD Correlation
        usd_correlation = self._calculate_usd_correlation(close)
        
        # Factor 3: Safe Haven Demand
        safe_haven_score = self._calculate_safe_haven_demand()
        
        # Factor 4: Momentum Analysis
        momentum_score = self._calculate_momentum(close)
        
        # Factor 5: Volatility Regime
        volatility_regime = self._classify_volatility(high, low, close)
        
        # Factor 6: Technical Levels
        key_levels = self._identify_key_levels(high, low, close)
        
        # Generate Signal
        signal, confidence = self._generate_metals_signal(
            gs_analysis,
            usd_correlation,
            safe_haven_score,
            momentum_score,
            volatility_regime,
            key_levels,
            close[-1]
        )
        
        # Calculate position size multiplier
        size_multiplier = self._calculate_size_multiplier(
            volatility_regime,
            confidence
        )
        
        return MetalsAnalysis(
            asset="XAUUSD",
            signal=signal,
            confidence=confidence,
            gold_silver_ratio=gs_analysis['ratio'],
            gs_ratio_zscore=gs_analysis['zscore'],
            usd_correlation=usd_correlation,
            safe_haven_score=safe_haven_score,
            momentum_score=momentum_score,
            volatility_regime=volatility_regime,
            recommended_size_multiplier=size_multiplier,
            key_levels=key_levels
        )
    
    def analyze_silver(
        self,
        symbol: str = "XAGUSD",
        lookback: int = 100
    ) -> Optional[MetalsAnalysis]:
        """
        Comprehensive silver analysis
        """
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, lookback)
        if rates is None or len(rates) < lookback:
            return None
        
        high = rates['high']
        low = rates['low']
        close = rates['close']
        
        # Silver-specific analysis
        gs_analysis = self._analyze_gold_silver_ratio()
        
        # Silver is more volatile and industrial
        industrial_demand = self._estimate_industrial_demand()
        
        # Technical analysis
        momentum_score = self._calculate_momentum(close)
        volatility_regime = self._classify_volatility(high, low, close)
        key_levels = self._identify_key_levels(high, low, close)
        
        # Silver follows gold but more aggressively
        gold_signal = self._get_gold_signal()
        
        # Generate signal
        signal, confidence = self._generate_silver_signal(
            gs_analysis,
            gold_signal,
            industrial_demand,
            momentum_score,
            volatility_regime,
            key_levels,
            close[-1]
        )
        
        # Silver requires smaller position sizes due to volatility
        size_multiplier = self._calculate_size_multiplier(
            volatility_regime,
            confidence
        ) * 0.7  # Reduce by 30% for silver
        
        return MetalsAnalysis(
            asset="XAGUSD",
            signal=signal,
            confidence=confidence,
            gold_silver_ratio=gs_analysis['ratio'],
            gs_ratio_zscore=gs_analysis['zscore'],
            usd_correlation=0.0,  # Less direct correlation
            safe_haven_score=0.0,  # Not a safe haven
            momentum_score=momentum_score,
            volatility_regime=volatility_regime,
            recommended_size_multiplier=size_multiplier,
            key_levels=key_levels
        )
    
    def _analyze_gold_silver_ratio(self) -> Dict:
        """
        Calculate and analyze Gold/Silver ratio
        """
        # Get current prices
        gold_tick = mt5.symbol_info_tick("XAUUSD")
        silver_tick = mt5.symbol_info_tick("XAGUSD")
        
        if gold_tick is None or silver_tick is None:
            return {
                'ratio': self.normal_gs_ratio_mean,
                'zscore': 0.0,
                'extreme': False
            }
        
        current_ratio = gold_tick.bid / silver_tick.bid
        
        # Calculate z-score
        zscore = (current_ratio - self.normal_gs_ratio_mean) / self.normal_gs_ratio_std
        
        # Extreme ratios suggest mean reversion opportunity
        is_extreme = abs(zscore) > 2.0
        
        return {
            'ratio': current_ratio,
            'zscore': zscore,
            'extreme': is_extreme,
            'direction': 'HIGH' if zscore > 0 else 'LOW'
        }
    
    def _calculate_usd_correlation(self, gold_prices) -> float:
        """
        Calculate correlation with USD (DXY proxy)
        Gold typically has -0.8 to -0.9 correlation with USD
        """
        # Simplified: Use gold price movement as inverse indicator
        # In production, would fetch actual DXY data
        
        gold_returns = np.diff(gold_prices) / gold_prices[:-1]
        
        # Simulate USD movement (inverse of gold for this demo)
        # Negative correlation is expected
        correlation = -0.85  # Default assumption
        
        return correlation
    
    def _calculate_safe_haven_demand(self) -> float:
        """
        Estimate safe haven demand
        In production: would use VIX, market sentiment, geopolitical indicators
        """
        # Simplified scoring
        # Would normally fetch VIX, equity market volatility, etc.
        base_score = 0.5
        
        # Check gold momentum (rising = higher safe haven demand)
        gold_rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 20)
        if gold_rates is not None:
            close = gold_rates['close']
            momentum = (close[-1] - close[-10]) / close[-10]
            
            if momentum > 0.03:  # 3% rise in 10 days
                base_score = 0.8
            elif momentum < -0.03:
                base_score = 0.2
        
        return base_score
    
    def _calculate_momentum(self, close) -> float:
        """
        Calculate momentum score 0-1
        """
        # Multiple timeframe momentum
        mom_5 = (close[-1] - close[-5]) / close[-5] if close[-5] > 0 else 0
        mom_10 = (close[-1] - close[-10]) / close[-10] if close[-10] > 0 else 0
        mom_20 = (close[-1] - close[-20]) / close[-20] if close[-20] > 0 else 0
        
        # Weighted average
        momentum = (mom_5 * 3 + mom_10 * 2 + mom_20) / 6
        
        # Normalize to 0-1 (clamp at ±10%)
        normalized = (momentum + 0.10) / 0.20
        return max(0.0, min(1.0, normalized))
    
    def _classify_volatility(self, high, low, close) -> str:
        """
        Classify volatility regime for metals
        """
        # Calculate ATR
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        atr = self._ema(tr, 14)
        avg_atr = np.mean(atr[-50:])
        
        current_vs_avg = atr[-1] / avg_atr if avg_atr > 0 else 1.0
        
        if current_vs_avg > 1.5:
            return "EXTREME"
        elif current_vs_avg > 1.2:
            return "HIGH"
        elif current_vs_avg > 0.8:
            return "NORMAL"
        else:
            return "LOW"
    
    def _identify_key_levels(self, high, low, close) -> Dict:
        """
        Identify key support/resistance levels
        """
        # Recent swing highs/lows
        swing_high = np.max(high[-50:])
        swing_low = np.min(low[-50:])
        
        # Round numbers (important for gold)
        current_price = close[-1]
        round_above = np.ceil(current_price / 10) * 10
        round_below = np.floor(current_price / 10) * 10
        
        # Pivot points
        pivot = (high[-2] + low[-2] + close[-2]) / 3
        r1 = 2 * pivot - low[-2]
        s1 = 2 * pivot - high[-2]
        
        return {
            'swing_high': swing_high,
            'swing_low': swing_low,
            'round_above': round_above,
            'round_below': round_below,
            'pivot': pivot,
            'resistance_1': r1,
            'support_1': s1,
            'current': current_price
        }
    
    def _generate_metals_signal(
        self,
        gs_analysis: Dict,
        usd_corr: float,
        safe_haven: float,
        momentum: float,
        volatility: str,
        levels: Dict,
        current_price: float
    ) -> Tuple[str, float]:
        """
        Generate trading signal for gold
        """
        score = 0
        max_score = 100
        
        # 1. Technical Momentum (30 points)
        if momentum > 0.65:
            score += 30
        elif momentum > 0.5:
            score += 20
        elif momentum < 0.35:
            score -= 30
        elif momentum < 0.5:
            score -= 20
        
        # 2. Safe Haven Demand (20 points)
        score += safe_haven * 20
        
        # 3. Key Level Position (25 points)
        if current_price > levels['resistance_1']:
            score += 15  # Breakout
        elif current_price < levels['support_1']:
            score -= 15  # Breakdown
        elif abs(current_price - levels['pivot']) / levels['pivot'] < 0.005:
            score += 10  # At pivot
        
        # 4. G/S Ratio (15 points)
        if gs_analysis['extreme']:
            if gs_analysis['zscore'] > 2:
                # Ratio too high, gold expensive relative to silver
                score -= 10
            elif gs_analysis['zscore'] < -2:
                # Ratio too low, gold cheap relative to silver
                score += 10
        
        # 5. Volatility Adjustment (10 points)
        if volatility == "NORMAL":
            score += 10
        elif volatility == "EXTREME":
            score -= 10
        
        # Normalize score
        normalized_score = (score + 50) / 100  # Convert to 0-1
        confidence = max(0.3, min(0.95, normalized_score))
        
        # Determine signal
        if score > 25:
            signal = "BULLISH"
        elif score < -25:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"
            confidence *= 0.5
        
        return signal, confidence
    
    def _estimate_industrial_demand(self) -> float:
        """
        Estimate industrial demand for silver
        Simplified version - would use PMI, industrial production data
        """
        return 0.5  # Neutral default
    
    def _get_gold_signal(self) -> str:
        """
        Get current gold signal (silver follows gold)
        """
        gold_rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 20)
        if gold_rates is None:
            return "NEUTRAL"
        
        close = gold_rates['close']
        momentum = (close[-1] - close[-10]) / close[-10]
        
        if momentum > 0.02:
            return "BULLISH"
        elif momentum < -0.02:
            return "BEARISH"
        return "NEUTRAL"
    
    def _generate_silver_signal(
        self,
        gs_analysis: Dict,
        gold_signal: str,
        industrial: float,
        momentum: float,
        volatility: str,
        levels: Dict,
        current_price: float
    ) -> Tuple[str, float]:
        """
        Generate trading signal for silver
        """
        score = 0
        
        # 1. Follow gold (40 points)
        if gold_signal == "BULLISH":
            score += 40
        elif gold_signal == "BEARISH":
            score -= 40
        
        # 2. Own momentum (30 points)
        if momentum > 0.65:
            score += 30
        elif momentum < 0.35:
            score -= 30
        
        # 3. G/S Ratio mean reversion (20 points)
        if gs_analysis['extreme']:
            if gs_analysis['zscore'] > 2:
                # Ratio high, silver undervalued
                score += 20
            elif gs_analysis['zscore'] < -2:
                # Ratio low, silver overvalued
                score -= 20
        
        # 4. Volatility (10 points)
        if volatility == "EXTREME":
            score -= 20  # Too dangerous
        
        # Normalize
        normalized_score = (score + 50) / 100
        confidence = max(0.3, min(0.9, normalized_score))
        
        # Determine signal
        if score > 30:
            signal = "BULLISH"
        elif score < -30:
            signal = "BEARISH"
        else:
            signal = "NEUTRAL"
            confidence *= 0.5
        
        return signal, confidence
    
    def _calculate_size_multiplier(self, volatility: str, confidence: float) -> float:
        """
        Calculate position size multiplier based on conditions
        """
        base = {
            "LOW": 1.0,
            "NORMAL": 0.8,
            "HIGH": 0.6,
            "EXTREME": 0.4
        }.get(volatility, 0.5)
        
        # Adjust for confidence
        return base * confidence
    
    def _ema(self, data, period):
        """Calculate EMA"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
