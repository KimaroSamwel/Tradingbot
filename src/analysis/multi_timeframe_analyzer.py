"""
MULTI-TIMEFRAME ANALYZER
Analyzes M15, H1, H4, and Daily timeframes for confluence

Features:
- Trend alignment across timeframes
- Support/resistance confluence
- Momentum confirmation
- Volume analysis (if available)
- Weighted timeframe scoring
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class TimeframeWeight(Enum):
    """Timeframe importance weights"""
    M15 = 0.15
    H1 = 0.25
    H4 = 0.35
    DAILY = 0.25


@dataclass
class TimeframeAnalysis:
    """Analysis result for single timeframe"""
    timeframe: str
    trend: str  # BULLISH, BEARISH, NEUTRAL
    trend_strength: float  # 0-100
    support_levels: List[float]
    resistance_levels: List[float]
    momentum: float  # -100 to +100
    volatility: float  # 0-100
    volume_trend: str  # INCREASING, DECREASING, STABLE
    key_levels: Dict[str, float]


@dataclass
class MultiTimeframeSignal:
    """Complete multi-timeframe signal"""
    symbol: str
    overall_trend: str
    confidence: float  # 0-100
    timeframe_agreement: float  # 0-100
    
    m15_analysis: TimeframeAnalysis
    h1_analysis: Optional[TimeframeAnalysis]
    h4_analysis: Optional[TimeframeAnalysis]
    daily_analysis: Optional[TimeframeAnalysis]
    
    entry_zone: Tuple[float, float]  # (low, high)
    stop_loss_suggestion: float
    take_profit_zones: List[float]
    
    confluence_factors: List[str]
    risk_reward_ratio: float


class MultiTimeframeAnalyzer:
    """
    Analyzes multiple timeframes for confluence
    Inspired by ODIN and GPS Forex robots
    """
    
    def __init__(self):
        self.timeframe_weights = {
            'M15': TimeframeWeight.M15.value,
            'H1': TimeframeWeight.H1.value,
            'H4': TimeframeWeight.H4.value,
            'D': TimeframeWeight.DAILY.value
        }
    
    def _validate_timeframe_alignment(self, df_m15: pd.DataFrame, 
                                       df_h1: Optional[pd.DataFrame] = None,
                                       df_h4: Optional[pd.DataFrame] = None,
                                       df_daily: Optional[pd.DataFrame] = None) -> bool:
        """
        FIX: Validate that all timeframes have synchronized timestamps.
        Returns False if any timeframe has stale or misaligned data.
        """
        if df_m15 is None or len(df_m15) < 2:
            return False
        
        m15_time = df_m15.index[-1]
        
        if df_h1 is not None and len(df_h1) >= 2:
            h1_time = df_h1.index[-1]
            # H1 candle should be within 2 hours of M15 candle
            if abs((m15_time - h1_time).total_seconds()) > 7200:
                return False
        
        if df_h4 is not None and len(df_h4) >= 2:
            h4_time = df_h4.index[-1]
            # H4 candle should be within 4 hours of M15 candle
            if abs((m15_time - h4_time).total_seconds()) > 14400:
                return False
        
        if df_daily is not None and len(df_daily) >= 2:
            daily_time = df_daily.index[-1]
            # Daily candle should be within 24 hours of M15 candle
            if abs((m15_time - daily_time).total_seconds()) > 86400:
                return False
        
        return True
        
    def analyze(self, symbol: str,
               df_m15: pd.DataFrame,
               df_h1: Optional[pd.DataFrame] = None,
               df_h4: Optional[pd.DataFrame] = None,
               df_daily: Optional[pd.DataFrame] = None) -> MultiTimeframeSignal:
        """
        Complete multi-timeframe analysis
        
        Args:
            symbol: Trading symbol
            df_m15: M15 timeframe data (required)
            df_h1: H1 timeframe data (optional)
            df_h4: H4 timeframe data (optional)
            df_daily: Daily timeframe data (optional)
            
        Returns:
            MultiTimeframeSignal with complete analysis
        
        FIX: Added timestamp validation to ensure timeframes are synchronized
        """
        # FIX: Validate timestamp alignment between timeframes
        if not self._validate_timeframe_alignment(df_m15, df_h1, df_h4, df_daily):
            import logging
            logger = logging.getLogger('SNIPER_PRO_2024')
            logger.warning("Timeframe data not properly aligned - some TFs may be stale")
        
        # Analyze each timeframe
        m15_analysis = self._analyze_timeframe(df_m15, 'M15')
        h1_analysis = self._analyze_timeframe(df_h1, 'H1') if df_h1 is not None else None
        h4_analysis = self._analyze_timeframe(df_h4, 'H4') if df_h4 is not None else None
        daily_analysis = self._analyze_timeframe(df_daily, 'D') if df_daily is not None else None
        
        # Calculate overall trend with weights
        overall_trend, confidence = self._calculate_overall_trend([
            m15_analysis, h1_analysis, h4_analysis, daily_analysis
        ])
        
        # Calculate timeframe agreement
        agreement = self._calculate_timeframe_agreement([
            m15_analysis, h1_analysis, h4_analysis, daily_analysis
        ])
        
        # Find confluence levels
        entry_zone = self._find_entry_zone([
            m15_analysis, h1_analysis, h4_analysis, daily_analysis
        ])
        
        # Calculate stop loss and take profit
        stop_loss = self._calculate_stop_loss(
            m15_analysis, overall_trend, entry_zone
        )
        
        take_profit_zones = self._calculate_take_profit_zones(
            [m15_analysis, h1_analysis, h4_analysis, daily_analysis],
            overall_trend, entry_zone
        )
        
        # Identify confluence factors
        confluence_factors = self._identify_confluence_factors([
            m15_analysis, h1_analysis, h4_analysis, daily_analysis
        ])
        
        # Calculate risk/reward
        if stop_loss and take_profit_zones:
            entry_mid = (entry_zone[0] + entry_zone[1]) / 2
            risk = abs(entry_mid - stop_loss)
            reward = abs(take_profit_zones[0] - entry_mid)
            rr_ratio = reward / risk if risk > 0 else 0
        else:
            rr_ratio = 0
        
        return MultiTimeframeSignal(
            symbol=symbol,
            overall_trend=overall_trend,
            confidence=confidence,
            timeframe_agreement=agreement,
            m15_analysis=m15_analysis,
            h1_analysis=h1_analysis,
            h4_analysis=h4_analysis,
            daily_analysis=daily_analysis,
            entry_zone=entry_zone,
            stop_loss_suggestion=stop_loss,
            take_profit_zones=take_profit_zones,
            confluence_factors=confluence_factors,
            risk_reward_ratio=rr_ratio
        )
    
    def _analyze_timeframe(self, df: Optional[pd.DataFrame],
                          timeframe: str) -> Optional[TimeframeAnalysis]:
        """Analyze single timeframe"""
        if df is None or len(df) < 20:
            return None
        
        # 1. Trend analysis (EMA 8, 21, 200)
        trend, trend_strength = self._analyze_trend(df)
        
        # 2. Support/Resistance levels
        support_levels, resistance_levels = self._find_sr_levels(df)
        
        # 3. Momentum (RSI, MACD)
        momentum = self._calculate_momentum(df)
        
        # 4. Volatility (ATR)
        volatility = self._calculate_volatility(df)
        
        # 5. Volume trend
        volume_trend = self._analyze_volume(df)
        
        # 6. Key levels (pivots, round numbers)
        key_levels = self._identify_key_levels(df)
        
        return TimeframeAnalysis(
            timeframe=timeframe,
            trend=trend,
            trend_strength=trend_strength,
            support_levels=support_levels,
            resistance_levels=resistance_levels,
            momentum=momentum,
            volatility=volatility,
            volume_trend=volume_trend,
            key_levels=key_levels
        )
    
    def _analyze_trend(self, df: pd.DataFrame) -> Tuple[str, float]:
        """
        Analyze trend using EMA 8, 21, 200
        Inspired by GPS Forex Robot
        """
        # Calculate EMAs
        ema8 = df['close'].ewm(span=8).mean()
        ema21 = df['close'].ewm(span=21).mean()
        ema200 = df['close'].ewm(span=200).mean() if len(df) >= 200 else ema21
        
        current_price = df['close'].iloc[-1]
        current_ema8 = ema8.iloc[-1]
        current_ema21 = ema21.iloc[-1]
        current_ema200 = ema200.iloc[-1]
        
        # Strong bullish: Price > EMA8 > EMA21 > EMA200
        if current_price > current_ema8 > current_ema21 > current_ema200:
            return 'BULLISH', 90
        
        # Moderate bullish: Price > EMA21 > EMA200
        if current_price > current_ema21 > current_ema200:
            return 'BULLISH', 70
        
        # Weak bullish: Price > EMA200
        if current_price > current_ema200:
            return 'BULLISH', 50
        
        # Strong bearish: Price < EMA8 < EMA21 < EMA200
        if current_price < current_ema8 < current_ema21 < current_ema200:
            return 'BEARISH', 90
        
        # Moderate bearish: Price < EMA21 < EMA200
        if current_price < current_ema21 < current_ema200:
            return 'BEARISH', 70
        
        # Weak bearish: Price < EMA200
        if current_price < current_ema200:
            return 'BEARISH', 50
        
        # Neutral
        return 'NEUTRAL', 30
    
    def _find_sr_levels(self, df: pd.DataFrame,
                       lookback: int = 50) -> Tuple[List[float], List[float]]:
        """Find support and resistance levels"""
        if len(df) < lookback:
            lookback = len(df)
        
        recent_df = df.iloc[-lookback:]
        current_price = df['close'].iloc[-1]
        
        # Find swing highs (resistance)
        resistance_levels = []
        for i in range(5, len(recent_df) - 5):
            if recent_df['high'].iloc[i] == recent_df['high'].iloc[i-5:i+5].max():
                level = recent_df['high'].iloc[i]
                if level > current_price:
                    resistance_levels.append(level)
        
        # Find swing lows (support)
        support_levels = []
        for i in range(5, len(recent_df) - 5):
            if recent_df['low'].iloc[i] == recent_df['low'].iloc[i-5:i+5].min():
                level = recent_df['low'].iloc[i]
                if level < current_price:
                    support_levels.append(level)
        
        # Remove duplicates and sort
        resistance_levels = sorted(list(set(resistance_levels)))[:5]
        support_levels = sorted(list(set(support_levels)), reverse=True)[:5]
        
        return support_levels, resistance_levels
    
    def _calculate_momentum(self, df: pd.DataFrame) -> float:
        """Calculate momentum score (-100 to +100)"""
        # RSI component
        rsi = self._calculate_rsi(df)
        rsi_score = (rsi - 50) * 2  # Convert to -100 to +100
        
        # MACD component
        macd, signal = self._calculate_macd(df)
        macd_score = 50 if macd > signal else -50
        
        # Combine
        momentum = (rsi_score * 0.6 + macd_score * 0.4)
        
        return max(-100, min(100, momentum))
    
    def _calculate_volatility(self, df: pd.DataFrame) -> float:
        """Calculate volatility score (0-100)"""
        atr = self._calculate_atr(df)
        current_price = df['close'].iloc[-1]
        
        atr_percent = (atr / current_price) * 100
        
        # Normalize to 0-100 scale
        # 1% ATR = 50, 2% = 100
        volatility = min(100, atr_percent * 50)
        
        return volatility
    
    def _analyze_volume(self, df: pd.DataFrame) -> str:
        """Analyze volume trend"""
        if 'volume' not in df.columns:
            return 'STABLE'
        
        recent_volume = df['volume'].iloc[-10:].mean()
        avg_volume = df['volume'].mean()
        
        if recent_volume > avg_volume * 1.2:
            return 'INCREASING'
        elif recent_volume < avg_volume * 0.8:
            return 'DECREASING'
        else:
            return 'STABLE'
    
    def _identify_key_levels(self, df: pd.DataFrame) -> Dict[str, float]:
        """Identify key psychological and technical levels"""
        current_price = df['close'].iloc[-1]
        
        # Round numbers (00, 50)
        round_above = np.ceil(current_price * 100) / 100
        round_below = np.floor(current_price * 100) / 100
        
        # Daily pivot
        high = df['high'].iloc[-1]
        low = df['low'].iloc[-1]
        close = df['close'].iloc[-1]
        
        pivot = (high + low + close) / 3
        r1 = 2 * pivot - low
        s1 = 2 * pivot - high
        
        return {
            'pivot': pivot,
            'r1': r1,
            's1': s1,
            'round_above': round_above,
            'round_below': round_below
        }
    
    def _calculate_overall_trend(self, analyses: List[Optional[TimeframeAnalysis]]) -> Tuple[str, float]:
        """Calculate weighted overall trend"""
        bullish_score = 0
        bearish_score = 0
        total_weight = 0
        
        for analysis in analyses:
            if analysis is None:
                continue
            
            weight = self.timeframe_weights.get(analysis.timeframe, 0.25)
            total_weight += weight
            
            if analysis.trend == 'BULLISH':
                bullish_score += weight * (analysis.trend_strength / 100)
            elif analysis.trend == 'BEARISH':
                bearish_score += weight * (analysis.trend_strength / 100)
        
        if total_weight == 0:
            return 'NEUTRAL', 0
        
        bullish_score /= total_weight
        bearish_score /= total_weight
        
        if bullish_score > bearish_score:
            return 'BULLISH', bullish_score * 100
        elif bearish_score > bullish_score:
            return 'BEARISH', bearish_score * 100
        else:
            return 'NEUTRAL', 50
    
    def _calculate_timeframe_agreement(self, analyses: List[Optional[TimeframeAnalysis]]) -> float:
        """Calculate agreement percentage between timeframes"""
        valid_analyses = [a for a in analyses if a is not None]
        
        if len(valid_analyses) < 2:
            return 50
        
        trends = [a.trend for a in valid_analyses]
        
        # Count most common trend
        bullish_count = trends.count('BULLISH')
        bearish_count = trends.count('BEARISH')
        
        max_count = max(bullish_count, bearish_count)
        agreement = (max_count / len(trends)) * 100
        
        return agreement
    
    def _find_entry_zone(self, analyses: List[Optional[TimeframeAnalysis]]) -> Tuple[float, float]:
        """Find optimal entry zone based on confluence"""
        all_support = []
        all_resistance = []
        
        for analysis in analyses:
            if analysis is None:
                continue
            all_support.extend(analysis.support_levels)
            all_resistance.extend(analysis.resistance_levels)
        
        if not all_support or not all_resistance:
            return (0, 0)
        
        # Find nearest support and resistance
        nearest_support = max(all_support)
        nearest_resistance = min(all_resistance)
        
        # Entry zone is 20% from support to resistance
        zone_size = (nearest_resistance - nearest_support) * 0.2
        
        return (nearest_support, nearest_support + zone_size)
    
    def _calculate_stop_loss(self, m15_analysis: TimeframeAnalysis,
                            trend: str, entry_zone: Tuple[float, float]) -> float:
        """Calculate stop loss based on ATR and support/resistance"""
        if trend == 'BULLISH' and m15_analysis.support_levels:
            # Place below nearest support
            return m15_analysis.support_levels[0] * 0.999
        elif trend == 'BEARISH' and m15_analysis.resistance_levels:
            # Place above nearest resistance
            return m15_analysis.resistance_levels[0] * 1.001
        else:
            # Use ATR-based stop
            entry_mid = (entry_zone[0] + entry_zone[1]) / 2
            atr_multiplier = 1.5
            if trend == 'BULLISH':
                return entry_mid * (1 - (m15_analysis.volatility / 100) * atr_multiplier)
            else:
                return entry_mid * (1 + (m15_analysis.volatility / 100) * atr_multiplier)
    
    def _calculate_take_profit_zones(self, analyses: List[Optional[TimeframeAnalysis]],
                                    trend: str, entry_zone: Tuple[float, float]) -> List[float]:
        """Calculate multiple take profit zones"""
        entry_mid = (entry_zone[0] + entry_zone[1]) / 2
        
        # Find resistance levels for bullish, support for bearish
        target_levels = []
        
        for analysis in analyses:
            if analysis is None:
                continue
            
            if trend == 'BULLISH':
                target_levels.extend(analysis.resistance_levels)
            else:
                target_levels.extend(analysis.support_levels)
        
        if not target_levels:
            # Use ATR-based targets
            m15 = analyses[0]
            if m15:
                atr = m15.volatility / 100 * entry_mid
                if trend == 'BULLISH':
                    return [entry_mid + atr * 1.5, entry_mid + atr * 2.5]
                else:
                    return [entry_mid - atr * 1.5, entry_mid - atr * 2.5]
        
        # Sort and return closest 2-3 levels
        if trend == 'BULLISH':
            target_levels = sorted([l for l in target_levels if l > entry_mid])[:3]
        else:
            target_levels = sorted([l for l in target_levels if l < entry_mid], reverse=True)[:3]
        
        return target_levels
    
    def _identify_confluence_factors(self, analyses: List[Optional[TimeframeAnalysis]]) -> List[str]:
        """Identify confluence factors across timeframes"""
        factors = []
        
        valid_analyses = [a for a in analyses if a is not None]
        
        # Trend agreement
        trends = [a.trend for a in valid_analyses]
        if trends.count('BULLISH') >= 3:
            factors.append("3+ timeframes bullish")
        elif trends.count('BEARISH') >= 3:
            factors.append("3+ timeframes bearish")
        
        # Momentum alignment
        momentums = [a.momentum for a in valid_analyses]
        if all(m > 20 for m in momentums):
            factors.append("All timeframes positive momentum")
        elif all(m < -20 for m in momentums):
            factors.append("All timeframes negative momentum")
        
        # Volume confirmation
        volumes = [a.volume_trend for a in valid_analyses if hasattr(a, 'volume_trend')]
        if volumes.count('INCREASING') >= 2:
            factors.append("Increasing volume across timeframes")
        
        return factors
    
    # Helper calculation methods
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate RSI"""
        if len(df) < period + 1:
            return 50
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def _calculate_macd(self, df: pd.DataFrame) -> Tuple[float, float]:
        """Calculate MACD and signal line"""
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        
        return macd.iloc[-1], signal.iloc[-1]
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0
