"""
WYCKOFF METHOD ANALYZER
Institutional accumulation/distribution pattern detection

Wyckoff Phases:
1. Accumulation (Phase A-E)
2. Markup (Bullish trend)
3. Distribution (Phase A-E)
4. Markdown (Bearish trend)

Key Events:
- PS (Preliminary Support)
- SC (Selling Climax)
- AR (Automatic Rally)
- ST (Secondary Test)
- Spring (Shakeout)
- SOS (Sign of Strength)
- LPS (Last Point of Support)

References:
- Richard D. Wyckoff "Studies in Tape Reading"
- VSA (Volume Spread Analysis) methodology
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class WyckoffPhase(Enum):
    """Wyckoff market phases"""
    ACCUMULATION_A = "ACCUMULATION_A"  # Stopping action
    ACCUMULATION_B = "ACCUMULATION_B"  # Building cause
    ACCUMULATION_C = "ACCUMULATION_C"  # Testing/spring
    ACCUMULATION_D = "ACCUMULATION_D"  # Sign of strength
    ACCUMULATION_E = "ACCUMULATION_E"  # Ready for markup
    
    MARKUP = "MARKUP"  # Uptrend
    
    DISTRIBUTION_A = "DISTRIBUTION_A"  # Preliminary supply
    DISTRIBUTION_B = "DISTRIBUTION_B"  # Building cause
    DISTRIBUTION_C = "DISTRIBUTION_C"  # Testing/upthrust
    DISTRIBUTION_D = "DISTRIBUTION_D"  # Sign of weakness
    DISTRIBUTION_E = "DISTRIBUTION_E"  # Ready for markdown
    
    MARKDOWN = "MARKDOWN"  # Downtrend
    
    UNKNOWN = "UNKNOWN"


class WyckoffEvent(Enum):
    """Wyckoff key events"""
    # Accumulation events
    PS = "Preliminary Support"
    SC = "Selling Climax"
    AR = "Automatic Rally"
    ST = "Secondary Test"
    SPRING = "Spring (Shakeout)"
    SOS = "Sign of Strength"
    LPS = "Last Point of Support"
    
    # Distribution events
    PSY = "Preliminary Supply"
    BC = "Buying Climax"
    LPSY = "Last Point of Supply"
    SOW = "Sign of Weakness"
    UTAD = "Upthrust After Distribution"
    
    NONE = "No Event"


@dataclass
class WyckoffSignal:
    """Wyckoff analysis result"""
    phase: WyckoffPhase
    current_event: WyckoffEvent
    direction: str  # BUY, SELL, NEUTRAL
    confidence: float  # 0-100
    price_level: float
    volume_confirmation: bool
    spread_analysis: str
    cause_effect_ratio: float  # Potential move size
    recommendation: str


class WyckoffAnalyzer:
    """
    Analyzes price and volume for Wyckoff patterns
    """
    
    def __init__(self, lookback_period: int = 100):
        """
        Args:
            lookback_period: Bars to analyze for pattern detection
        """
        self.lookback = lookback_period
        
    def analyze(self, df: pd.DataFrame) -> WyckoffSignal:
        """
        Perform complete Wyckoff analysis
        
        Args:
            df: OHLCV dataframe
            
        Returns:
            Wyckoff signal with phase and event detection
        """
        if len(df) < self.lookback:
            return self._neutral_signal(df['close'].iloc[-1])
            
        # Detect current phase
        phase = self._detect_phase(df)
        
        # Detect current event
        event = self._detect_event(df, phase)
        
        # Analyze volume
        volume_confirmed = self._analyze_volume(df)
        
        # Spread analysis
        spread_analysis = self._analyze_spread(df)
        
        # Calculate cause-effect
        cause_effect = self._calculate_cause_effect(df, phase)
        
        # Generate trading signal
        direction, confidence = self._generate_signal(phase, event, volume_confirmed)
        
        # Create recommendation
        recommendation = self._create_recommendation(phase, event, direction)
        
        return WyckoffSignal(
            phase=phase,
            current_event=event,
            direction=direction,
            confidence=confidence,
            price_level=df['close'].iloc[-1],
            volume_confirmation=volume_confirmed,
            spread_analysis=spread_analysis,
            cause_effect_ratio=cause_effect,
            recommendation=recommendation
        )
    
    def _detect_phase(self, df: pd.DataFrame) -> WyckoffPhase:
        """Detect current Wyckoff phase"""
        recent_bars = df.tail(self.lookback)
        
        # Calculate trend
        prices = recent_bars['close'].values
        trend = np.polyfit(range(len(prices)), prices, 1)[0]
        
        # Calculate range
        high_range = recent_bars['high'].max()
        low_range = recent_bars['low'].min()
        range_size = high_range - low_range
        
        # Calculate volatility
        recent_volatility = recent_bars['close'].pct_change().std()
        
        # Detect if in range (accumulation/distribution)
        recent_20 = df.tail(20)
        range_20 = recent_20['high'].max() - recent_20['low'].min()
        is_ranging = range_20 / high_range < 0.4  # Tight range
        
        # Volume pattern
        avg_volume = recent_bars['volume'].mean()
        recent_volume = recent_bars['volume'].tail(10).mean()
        volume_increasing = recent_volume > avg_volume * 1.1
        
        # Phase detection logic
        if is_ranging:
            # Accumulation or distribution?
            if trend > 0 and volume_increasing:
                # Potentially accumulation ending
                return WyckoffPhase.ACCUMULATION_D
            elif trend < 0 and volume_increasing:
                # Potentially distribution ending
                return WyckoffPhase.DISTRIBUTION_D
            elif volume_increasing:
                # Middle of accumulation/distribution
                if recent_bars['close'].iloc[-1] < recent_bars['close'].mean():
                    return WyckoffPhase.ACCUMULATION_B
                else:
                    return WyckoffPhase.DISTRIBUTION_B
            else:
                return WyckoffPhase.ACCUMULATION_B
        else:
            # Trending
            if trend > 0:
                return WyckoffPhase.MARKUP
            elif trend < 0:
                return WyckoffPhase.MARKDOWN
                
        return WyckoffPhase.UNKNOWN
    
    def _detect_event(self, df: pd.DataFrame, phase: WyckoffPhase) -> WyckoffEvent:
        """Detect Wyckoff events"""
        recent = df.tail(20)
        last = df.tail(5)
        
        # Volume spike detection
        avg_volume = recent['volume'].mean()
        current_volume = last['volume'].iloc[-1]
        volume_spike = current_volume > avg_volume * 1.5
        
        # Price movement
        price_range = recent['high'].max() - recent['low'].min()
        current_close = df['close'].iloc[-1]
        current_low = df['low'].iloc[-1]
        current_high = df['high'].iloc[-1]
        
        if phase in [WyckoffPhase.ACCUMULATION_A, WyckoffPhase.ACCUMULATION_B, 
                     WyckoffPhase.ACCUMULATION_C]:
            # Look for accumulation events
            if volume_spike and current_close < recent['low'].quantile(0.2):
                return WyckoffEvent.SC  # Selling climax
            elif current_low < recent['low'].min() and current_close > current_low:
                return WyckoffEvent.SPRING  # Spring/shakeout
            elif current_close > recent['high'].quantile(0.8) and volume_spike:
                return WyckoffEvent.SOS  # Sign of strength
            elif current_close > recent['close'].mean():
                return WyckoffEvent.AR  # Automatic rally
            else:
                return WyckoffEvent.ST  # Secondary test
                
        elif phase in [WyckoffPhase.DISTRIBUTION_A, WyckoffPhase.DISTRIBUTION_B,
                       WyckoffPhase.DISTRIBUTION_C]:
            # Look for distribution events
            if volume_spike and current_close > recent['high'].quantile(0.8):
                return WyckoffEvent.BC  # Buying climax
            elif current_high > recent['high'].max() and current_close < current_high:
                return WyckoffEvent.UTAD  # Upthrust
            elif current_close < recent['low'].quantile(0.2) and volume_spike:
                return WyckoffEvent.SOW  # Sign of weakness
                
        return WyckoffEvent.NONE
    
    def _analyze_volume(self, df: pd.DataFrame) -> bool:
        """
        Analyze if volume confirms price action
        
        Returns:
            True if volume confirms, False otherwise
        """
        recent = df.tail(20)
        last_5 = df.tail(5)
        
        avg_volume = recent['volume'].mean()
        recent_volume = last_5['volume'].mean()
        
        # Check if volume is confirming trend
        price_change = last_5['close'].pct_change().sum()
        volume_change = (recent_volume - avg_volume) / avg_volume
        
        # Volume should increase with price movement
        if abs(price_change) > 0.01 and volume_change > 0.2:
            return True
        elif abs(price_change) < 0.005:  # Range - volume should be lower
            return volume_change < 0
            
        return False
    
    def _analyze_spread(self, df: pd.DataFrame) -> str:
        """
        Analyze spread (high-low range) characteristics
        
        Returns:
            Description of spread analysis
        """
        recent = df.tail(10)
        
        # Calculate average spread
        spreads = recent['high'] - recent['low']
        avg_spread = spreads.mean()
        current_spread = df['high'].iloc[-1] - df['low'].iloc[-1]
        
        # Classify spread
        if current_spread > avg_spread * 1.5:
            return "Wide spread - strong activity"
        elif current_spread < avg_spread * 0.5:
            return "Narrow spread - weak activity"
        else:
            return "Normal spread"
    
    def _calculate_cause_effect(self, df: pd.DataFrame, 
                                phase: WyckoffPhase) -> float:
        """
        Calculate cause (accumulation/distribution) to effect (price move) ratio
        
        Returns:
            Expected move ratio (1.0 = 100% of range)
        """
        if phase == WyckoffPhase.MARKUP or phase == WyckoffPhase.MARKDOWN:
            return 0.0  # Already in effect phase
            
        recent = df.tail(self.lookback)
        
        # Count bars in range (cause building)
        range_high = recent['high'].max()
        range_low = recent['low'].min()
        range_size = range_high - range_low
        
        # Count bars in tight range (stronger cause)
        tight_range_pct = 0.3
        tight_bars = 0
        
        for i in range(len(recent)):
            bar_range = recent['high'].iloc[i] - recent['low'].iloc[i]
            if bar_range < range_size * tight_range_pct:
                tight_bars += 1
                
        # More bars in tight range = larger expected move
        cause_strength = tight_bars / len(recent)
        
        # Wyckoff rule: Cause × Time = Effect
        # Rough approximation: move = range_size × cause_strength × 2
        expected_move_ratio = cause_strength * 2.0
        
        return min(expected_move_ratio, 3.0)  # Cap at 3x range
    
    def _generate_signal(self, phase: WyckoffPhase, 
                        event: WyckoffEvent,
                        volume_confirmed: bool) -> Tuple[str, float]:
        """
        Generate trading signal from Wyckoff analysis
        
        Returns:
            (direction, confidence)
        """
        direction = "NEUTRAL"
        confidence = 50.0
        
        # Accumulation signals (bullish)
        if phase == WyckoffPhase.ACCUMULATION_D:
            if event == WyckoffEvent.SOS:
                direction = "BUY"
                confidence = 85.0
            elif event == WyckoffEvent.LPS:
                direction = "BUY"
                confidence = 80.0
        elif phase == WyckoffPhase.ACCUMULATION_C:
            if event == WyckoffEvent.SPRING:
                direction = "BUY"
                confidence = 75.0
        elif phase == WyckoffPhase.ACCUMULATION_E:
            direction = "BUY"
            confidence = 90.0
            
        # Distribution signals (bearish)
        elif phase == WyckoffPhase.DISTRIBUTION_D:
            if event == WyckoffEvent.SOW:
                direction = "SELL"
                confidence = 85.0
            elif event == WyckoffEvent.LPSY:
                direction = "SELL"
                confidence = 80.0
        elif phase == WyckoffPhase.DISTRIBUTION_C:
            if event == WyckoffEvent.UTAD:
                direction = "SELL"
                confidence = 75.0
        elif phase == WyckoffPhase.DISTRIBUTION_E:
            direction = "SELL"
            confidence = 90.0
            
        # Trending phases
        elif phase == WyckoffPhase.MARKUP:
            direction = "BUY"
            confidence = 70.0
        elif phase == WyckoffPhase.MARKDOWN:
            direction = "SELL"
            confidence = 70.0
            
        # Volume confirmation boost
        if volume_confirmed and direction != "NEUTRAL":
            confidence = min(confidence + 10, 95.0)
        elif not volume_confirmed and direction != "NEUTRAL":
            confidence = max(confidence - 15, 40.0)
            
        return direction, confidence
    
    def _create_recommendation(self, phase: WyckoffPhase,
                              event: WyckoffEvent,
                              direction: str) -> str:
        """Create trading recommendation"""
        if direction == "BUY":
            if event == WyckoffEvent.SPRING:
                return "Spring detected - buy after shakeout on volume confirmation"
            elif event == WyckoffEvent.SOS:
                return "Sign of strength - buy on pullback to support"
            elif phase == WyckoffPhase.ACCUMULATION_E:
                return "Accumulation complete - ready for markup, buy breakout"
            else:
                return "Accumulation phase - wait for sign of strength"
                
        elif direction == "SELL":
            if event == WyckoffEvent.UTAD:
                return "Upthrust detected - sell the false breakout"
            elif event == WyckoffEvent.SOW:
                return "Sign of weakness - sell rallies to resistance"
            elif phase == WyckoffPhase.DISTRIBUTION_E:
                return "Distribution complete - ready for markdown, sell breakdown"
            else:
                return "Distribution phase - wait for sign of weakness"
                
        else:
            return "No clear Wyckoff signal - wait for phase development"
    
    def _neutral_signal(self, price: float) -> WyckoffSignal:
        """Return neutral signal when insufficient data"""
        return WyckoffSignal(
            phase=WyckoffPhase.UNKNOWN,
            current_event=WyckoffEvent.NONE,
            direction="NEUTRAL",
            confidence=0.0,
            price_level=price,
            volume_confirmation=False,
            spread_analysis="Insufficient data",
            cause_effect_ratio=0.0,
            recommendation="Need more data for Wyckoff analysis"
        )
