"""
ADVANCED MARKET REGIME DETECTOR
Multi-dimensional regime detection for optimal strategy selection

Features:
- Trend strength detection (ADX, MA alignment)
- Volatility regime classification (ATR, VIX)
- Liquidity assessment
- Session impact analysis
- Multi-timeframe confirmation
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from enum import Enum


class TrendRegime(Enum):
    """Trend classification"""
    STRONG_UPTREND = "STRONG_UPTREND"
    MODERATE_UPTREND = "MODERATE_UPTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"
    MODERATE_DOWNTREND = "MODERATE_DOWNTREND"
    RANGING = "RANGING"
    TRANSITION = "TRANSITION"


class VolatilityRegime(Enum):
    """Volatility classification"""
    EXTREME_HIGH = "EXTREME_HIGH"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    EXTREME_LOW = "EXTREME_LOW"


@dataclass
class RegimeAnalysis:
    """Comprehensive regime analysis result"""
    trend_regime: TrendRegime
    volatility_regime: VolatilityRegime
    trend_strength: float  # 0-100
    volatility_score: float  # 0-100
    liquidity_score: float  # 0-100
    session_impact: float  # 0-100
    confidence: float  # 0-100
    components: Dict
    
    def get_market_regime(self) -> str:
        """Get simplified market regime string"""
        if self.trend_strength > 70:
            return 'STRONG_TREND'
        elif self.trend_strength > 40:
            return 'MODERATE_TREND'
        elif self.volatility_score > 70:
            return 'HIGH_VOLATILITY'
        elif self.volatility_score < 30:
            return 'LOW_VOLATILITY'
        else:
            return 'RANGING'


class AdvancedMarketRegimeDetector:
    """
    Advanced market regime detection using multiple dimensions
    """
    
    def __init__(self, broker_timezone: str = 'GMT+3'):
        """
        Initialize regime detector
        
        Args:
            broker_timezone: Broker timezone (e.g., 'GMT+3' for Nairobi)
        """
        self.broker_timezone = broker_timezone
        self.regime_history = []
        
        # Regime thresholds
        self.adx_thresholds = {
            'strong_trend': 30,
            'moderate_trend': 20,
            'no_trend': 15
        }
        
        self.volatility_thresholds = {
            'extreme_high': 2.0,  # ATR as % of price
            'high': 1.0,
            'normal': 0.5,
            'low': 0.25
        }
        
    def detect_regime(self, df: pd.DataFrame,
                     df_h1: Optional[pd.DataFrame] = None,
                     df_h4: Optional[pd.DataFrame] = None) -> RegimeAnalysis:
        """
        Comprehensive regime detection
        
        Args:
            df: Primary timeframe data (M15)
            df_h1: 1-hour data (optional)
            df_h4: 4-hour data (optional)
            
        Returns:
            RegimeAnalysis with complete regime information
        """
        # 1. Trend Detection
        trend_regime, trend_strength = self._detect_trend_regime(df, df_h1, df_h4)
        
        # 2. Volatility Detection
        volatility_regime, volatility_score = self._detect_volatility_regime(df)
        
        # 3. Liquidity Assessment
        liquidity_score = self._assess_liquidity(df)
        
        # 4. Session Impact
        session_impact = self._analyze_session_impact()
        
        # 5. Calculate confidence
        confidence = self._calculate_confidence({
            'trend': trend_strength,
            'volatility': volatility_score,
            'liquidity': liquidity_score,
            'session': session_impact
        })
        
        # Create regime analysis
        analysis = RegimeAnalysis(
            trend_regime=trend_regime,
            volatility_regime=volatility_regime,
            trend_strength=trend_strength,
            volatility_score=volatility_score,
            liquidity_score=liquidity_score,
            session_impact=session_impact,
            confidence=confidence,
            components={
                'trend': trend_regime.value,
                'volatility': volatility_regime.value,
                'trend_score': trend_strength,
                'vol_score': volatility_score,
                'liquidity': liquidity_score,
                'session': session_impact
            }
        )
        
        # Store in history
        self.regime_history.append({
            'timestamp': datetime.now(),
            'regime': analysis.get_market_regime(),
            'confidence': confidence
        })
        
        # Keep only last 1000 entries
        if len(self.regime_history) > 1000:
            self.regime_history = self.regime_history[-1000:]
        
        return analysis
    
    def _detect_trend_regime(self, df: pd.DataFrame,
                            df_h1: Optional[pd.DataFrame],
                            df_h4: Optional[pd.DataFrame]) -> Tuple[TrendRegime, float]:
        """
        Multi-timeframe trend detection
        
        Returns:
            (TrendRegime, strength_score)
        """
        trend_scores = []
        weights = []
        
        # M15 timeframe analysis
        if len(df) >= 50:
            score_m15 = self._calculate_trend_score(df)
            trend_scores.append(score_m15)
            weights.append(0.2)  # 20% weight
        
        # H1 timeframe analysis
        if df_h1 is not None and len(df_h1) >= 50:
            score_h1 = self._calculate_trend_score(df_h1)
            trend_scores.append(score_h1)
            weights.append(0.3)  # 30% weight
        
        # H4 timeframe analysis
        if df_h4 is not None and len(df_h4) >= 50:
            score_h4 = self._calculate_trend_score(df_h4)
            trend_scores.append(score_h4)
            weights.append(0.5)  # 50% weight (highest)
        
        # Normalize weights
        if trend_scores:
            total_weight = sum(weights)
            weights = [w / total_weight for w in weights]
            
            # Weighted average
            trend_strength = sum(s * w for s, w in zip(trend_scores, weights))
        else:
            trend_strength = 0
        
        # Classify trend regime
        if trend_strength > 70:
            regime = TrendRegime.STRONG_UPTREND
        elif trend_strength > 40:
            regime = TrendRegime.MODERATE_UPTREND
        elif trend_strength < -70:
            regime = TrendRegime.STRONG_DOWNTREND
        elif trend_strength < -40:
            regime = TrendRegime.MODERATE_DOWNTREND
        elif abs(trend_strength) < 20:
            regime = TrendRegime.RANGING
        else:
            regime = TrendRegime.TRANSITION
        
        return regime, abs(trend_strength)
    
    def _calculate_trend_score(self, df: pd.DataFrame) -> float:
        """
        Calculate trend score for single timeframe
        Range: -100 (strong down) to +100 (strong up)
        """
        score = 0
        
        # Component 1: ADX (30%)
        adx = self._calculate_adx(df)
        if adx > self.adx_thresholds['strong_trend']:
            adx_score = 30
        elif adx > self.adx_thresholds['moderate_trend']:
            adx_score = 20
        else:
            adx_score = 10
        
        # Component 2: Moving Average alignment (30%)
        ma_score = self._calculate_ma_alignment(df)
        
        # Component 3: Price position relative to MAs (20%)
        price_score = self._calculate_price_position(df)
        
        # Component 4: Momentum (20%)
        momentum_score = self._calculate_momentum(df)
        
        # Combine scores
        score = adx_score + ma_score + price_score + momentum_score
        
        return score
    
    def _detect_volatility_regime(self, df: pd.DataFrame) -> Tuple[VolatilityRegime, float]:
        """
        Detect volatility regime
        
        Returns:
            (VolatilityRegime, volatility_score)
        """
        # Calculate ATR as percentage of price
        atr = self._calculate_atr(df)
        current_price = df['close'].iloc[-1]
        atr_pct = (atr / current_price) * 100
        
        # Calculate Bollinger Band width
        bb_width = self._calculate_bb_width(df)
        
        # Calculate recent range
        recent_range = self._calculate_recent_range(df, periods=20)
        
        # Combine into volatility score (0-100)
        volatility_score = (
            (atr_pct / self.volatility_thresholds['extreme_high']) * 40 +
            (bb_width / 4.0) * 30 +
            (recent_range / 2.0) * 30
        )
        volatility_score = min(100, volatility_score)
        
        # Classify regime
        if volatility_score > 80:
            regime = VolatilityRegime.EXTREME_HIGH
        elif volatility_score > 60:
            regime = VolatilityRegime.HIGH
        elif volatility_score > 30:
            regime = VolatilityRegime.NORMAL
        elif volatility_score > 15:
            regime = VolatilityRegime.LOW
        else:
            regime = VolatilityRegime.EXTREME_LOW
        
        return regime, volatility_score
    
    def _assess_liquidity(self, df: pd.DataFrame) -> float:
        """
        Assess market liquidity
        Range: 0-100 (higher = more liquid)
        """
        if 'volume' not in df.columns:
            return 50.0  # Default neutral if no volume data
        
        # Component 1: Volume trend
        recent_volume = df['volume'].iloc[-20:].mean()
        avg_volume = df['volume'].mean()
        volume_score = min(100, (recent_volume / avg_volume) * 50)
        
        # Component 2: Spread analysis (if tick_volume available)
        if 'tick_volume' in df.columns:
            spread_score = min(100, df['tick_volume'].iloc[-20:].mean() / 100)
        else:
            spread_score = 50
        
        liquidity_score = (volume_score * 0.6 + spread_score * 0.4)
        
        return liquidity_score
    
    def _analyze_session_impact(self) -> float:
        """
        Analyze current session impact on volatility/liquidity
        Range: 0-100 (higher = better trading conditions)
        """
        current_time = datetime.now().time()
        
        # Define session times (GMT+3 for Nairobi)
        sessions = {
            'LONDON': (dt_time(11, 0), dt_time(13, 0)),  # 11 AM - 1 PM
            'NY': (dt_time(14, 0), dt_time(23, 0)),  # 2 PM - 11 PM
            'OVERLAP': (dt_time(14, 0), dt_time(17, 0)),  # London-NY overlap
            'ASIAN': (dt_time(3, 0), dt_time(11, 0))  # 3 AM - 11 AM
        }
        
        # Score each session
        if self._is_in_session(current_time, sessions['OVERLAP']):
            return 100  # Best time
        elif self._is_in_session(current_time, sessions['LONDON']):
            return 90
        elif self._is_in_session(current_time, sessions['NY']):
            return 85
        elif self._is_in_session(current_time, sessions['ASIAN']):
            return 40
        else:
            return 20  # Off-hours
    
    def _calculate_confidence(self, components: Dict[str, float]) -> float:
        """
        Calculate overall regime detection confidence
        Range: 0-100
        """
        # Check consistency across components
        values = list(components.values())
        
        # Higher confidence if all components agree
        std_dev = np.std(values)
        mean_val = np.mean(values)
        
        # Low std dev = high agreement = high confidence
        confidence = 100 - (std_dev / mean_val) * 100 if mean_val > 0 else 50
        confidence = max(0, min(100, confidence))
        
        return confidence
    
    # Helper methods
    
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average Directional Index"""
        if len(df) < period + 1:
            return 0
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        # Calculate +DM and -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        # Calculate True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate smoothed values
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        # Calculate ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
    
    def _calculate_ma_alignment(self, df: pd.DataFrame) -> float:
        """Calculate MA alignment score (-30 to +30)"""
        if len(df) < 50:
            return 0
        
        # Calculate MAs
        ema9 = df['close'].ewm(span=9).mean()
        ema21 = df['close'].ewm(span=21).mean()
        ema50 = df['close'].ewm(span=50).mean()
        
        # Check alignment
        current_ema9 = ema9.iloc[-1]
        current_ema21 = ema21.iloc[-1]
        current_ema50 = ema50.iloc[-1]
        
        if current_ema9 > current_ema21 > current_ema50:
            return 30  # Perfect uptrend alignment
        elif current_ema9 < current_ema21 < current_ema50:
            return -30  # Perfect downtrend alignment
        elif current_ema9 > current_ema21:
            return 15
        elif current_ema9 < current_ema21:
            return -15
        else:
            return 0
    
    def _calculate_price_position(self, df: pd.DataFrame) -> float:
        """Calculate price position relative to MAs (-20 to +20)"""
        if len(df) < 50:
            return 0
        
        price = df['close'].iloc[-1]
        ema20 = df['close'].ewm(span=20).mean().iloc[-1]
        
        pct_diff = ((price - ema20) / ema20) * 100
        
        # Scale to -20 to +20
        score = max(-20, min(20, pct_diff * 10))
        
        return score
    
    def _calculate_momentum(self, df: pd.DataFrame) -> float:
        """Calculate momentum score (-20 to +20)"""
        if len(df) < 14:
            return 0
        
        # Use RSI
        rsi = self._calculate_rsi(df)
        
        # Convert RSI to momentum score
        if rsi > 70:
            return 20
        elif rsi > 60:
            return 15
        elif rsi > 50:
            return 10
        elif rsi < 30:
            return -20
        elif rsi < 40:
            return -15
        elif rsi < 50:
            return -10
        else:
            return 0
    
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
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        if len(df) < period + 1:
            return 0
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0
    
    def _calculate_bb_width(self, df: pd.DataFrame, period: int = 20) -> float:
        """Calculate Bollinger Band width as % of price"""
        if len(df) < period:
            return 0
        
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        
        upper = sma + (std * 2)
        lower = sma - (std * 2)
        
        width = ((upper - lower) / sma) * 100
        
        return width.iloc[-1] if not pd.isna(width.iloc[-1]) else 0
    
    def _calculate_recent_range(self, df: pd.DataFrame, periods: int = 20) -> float:
        """Calculate recent price range as % of price"""
        if len(df) < periods:
            return 0
        
        recent_high = df['high'].iloc[-periods:].max()
        recent_low = df['low'].iloc[-periods:].min()
        current_price = df['close'].iloc[-1]
        
        range_pct = ((recent_high - recent_low) / current_price) * 100
        
        return range_pct
    
    def _is_in_session(self, current_time: dt_time,
                       session: Tuple[dt_time, dt_time]) -> bool:
        """Check if current time is in session"""
        start, end = session
        
        if start < end:
            return start <= current_time <= end
        else:  # Session crosses midnight
            return current_time >= start or current_time <= end
    
    def get_regime_statistics(self) -> Dict:
        """Get statistics about regime history"""
        if not self.regime_history:
            return {}
        
        regimes = [entry['regime'] for entry in self.regime_history]
        confidences = [entry['confidence'] for entry in self.regime_history]
        
        return {
            'total_detections': len(self.regime_history),
            'current_regime': regimes[-1] if regimes else 'UNKNOWN',
            'avg_confidence': np.mean(confidences),
            'regime_distribution': {
                regime: regimes.count(regime) / len(regimes) * 100
                for regime in set(regimes)
            },
            'regime_stability': self._calculate_regime_stability(regimes[-100:])
        }
    
    def _calculate_regime_stability(self, recent_regimes: List[str]) -> float:
        """Calculate regime stability (0-100, higher = more stable)"""
        if len(recent_regimes) < 2:
            return 100
        
        # Count regime changes
        changes = sum(1 for i in range(1, len(recent_regimes))
                     if recent_regimes[i] != recent_regimes[i-1])
        
        stability = 100 - (changes / len(recent_regimes) * 100)
        
        return stability
