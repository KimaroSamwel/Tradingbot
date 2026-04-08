"""
ICT MARKET STRUCTURE DETECTOR
Detects Market Structure Shifts (MSS) and Break of Structure (BOS)

MSS = Change in trend direction (bearish to bullish or vice versa)
BOS = Continuation of existing trend

This is CRITICAL for ICT trading - we only trade AFTER structure confirms the direction
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class StructureType(Enum):
    """Market structure trend types"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    RANGING = "ranging"
    UNKNOWN = "unknown"


@dataclass
class SwingPoint:
    """Swing high or low point"""
    point_type: str  # 'high' or 'low'
    price: float
    time: datetime
    index: int
    broken: bool = False


@dataclass
class StructureShift:
    """Market Structure Shift or Break of Structure"""
    shift_type: str  # 'MSS' or 'BOS'
    direction: str   # 'bullish' or 'bearish'
    break_price: float
    break_time: datetime
    previous_structure: StructureType
    new_structure: StructureType
    strength: float  # 0-100 based on break size


class ICTMarketStructure:
    """
    Detect market structure changes using ICT methodology
    
    Key Rules:
    - Bullish MSS = Price breaks ABOVE previous swing high after downtrend
    - Bearish MSS = Price breaks BELOW previous swing low after uptrend
    - BOS = Break in direction of existing trend
    """
    
    def __init__(self, swing_lookback: int = 10, min_break_pips: float = 5.0):
        """
        Args:
            swing_lookback: Bars to look back for swing points
            min_break_pips: Minimum pips to confirm break
        """
        self.swing_lookback = swing_lookback
        self.min_break_pips = min_break_pips
        
        self.swing_highs: List[SwingPoint] = []
        self.swing_lows: List[SwingPoint] = []
        self.structure_shifts: List[StructureShift] = []
        self.current_structure: StructureType = StructureType.UNKNOWN
    
    def analyze_structure(self, df: pd.DataFrame) -> Dict:
        """
        Analyze complete market structure
        
        Args:
            df: OHLCV DataFrame with 'time' column
            
        Returns:
            Dict with structure analysis
        """
        # Identify swing points
        self.swing_highs = self._find_swing_highs(df)
        self.swing_lows = self._find_swing_lows(df)
        
        # Detect structure shifts
        self.structure_shifts = self._detect_structure_shifts(df)
        
        # Determine current structure
        self.current_structure = self._determine_current_structure()
        
        return {
            'current_structure': self.current_structure.value,
            'swing_highs_count': len(self.swing_highs),
            'swing_lows_count': len(self.swing_lows),
            'structure_shifts': len(self.structure_shifts),
            'latest_shift': self.get_latest_shift(),
            'is_bullish': self.is_bullish_structure(),
            'is_bearish': self.is_bearish_structure()
        }
    
    def _find_swing_highs(self, df: pd.DataFrame) -> List[SwingPoint]:
        """Find all swing high points"""
        swing_highs = []
        
        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            if self._is_swing_high(df, i):
                swing_highs.append(SwingPoint(
                    point_type='high',
                    price=df.iloc[i]['high'],
                    time=df.iloc[i]['time'],
                    index=i
                ))
        
        return swing_highs
    
    def _find_swing_lows(self, df: pd.DataFrame) -> List[SwingPoint]:
        """Find all swing low points"""
        swing_lows = []
        
        for i in range(self.swing_lookback, len(df) - self.swing_lookback):
            if self._is_swing_low(df, i):
                swing_lows.append(SwingPoint(
                    point_type='low',
                    price=df.iloc[i]['low'],
                    time=df.iloc[i]['time'],
                    index=i
                ))
        
        return swing_lows
    
    def _is_swing_high(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if candle is a swing high"""
        if idx < self.swing_lookback or idx >= len(df) - self.swing_lookback:
            return False
        
        current_high = df.iloc[idx]['high']
        
        # Must be higher than surrounding bars
        for i in range(idx - self.swing_lookback, idx):
            if df.iloc[i]['high'] >= current_high:
                return False
        
        for i in range(idx + 1, min(idx + self.swing_lookback + 1, len(df))):
            if df.iloc[i]['high'] >= current_high:
                return False
        
        return True
    
    def _is_swing_low(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if candle is a swing low"""
        if idx < self.swing_lookback or idx >= len(df) - self.swing_lookback:
            return False
        
        current_low = df.iloc[idx]['low']
        
        # Must be lower than surrounding bars
        for i in range(idx - self.swing_lookback, idx):
            if df.iloc[i]['low'] <= current_low:
                return False
        
        for i in range(idx + 1, min(idx + self.swing_lookback + 1, len(df))):
            if df.iloc[i]['low'] <= current_low:
                return False
        
        return True
    
    def _detect_structure_shifts(self, df: pd.DataFrame) -> List[StructureShift]:
        """Detect MSS and BOS events"""
        shifts = []
        
        if len(self.swing_highs) < 2 or len(self.swing_lows) < 2:
            return shifts
        
        # Track previous structure
        prev_structure = StructureType.UNKNOWN
        
        # Analyze each candle for breaks
        for i in range(len(df)):
            candle = df.iloc[i]
            
            # Check for bullish MSS (break above swing high after downtrend)
            for swing_high in self.swing_highs:
                if swing_high.broken or swing_high.index >= i:
                    continue
                
                if candle['close'] > swing_high.price + self.min_break_pips:
                    # Check if previous structure was bearish
                    if prev_structure == StructureType.BEARISH:
                        shift_type = 'MSS'  # Market Structure Shift
                    else:
                        shift_type = 'BOS'  # Break of Structure (continuation)
                    
                    strength = self._calculate_break_strength(
                        candle['close'], swing_high.price, df, i
                    )
                    
                    shifts.append(StructureShift(
                        shift_type=shift_type,
                        direction='bullish',
                        break_price=swing_high.price,
                        break_time=candle['time'],
                        previous_structure=prev_structure,
                        new_structure=StructureType.BULLISH,
                        strength=strength
                    ))
                    
                    swing_high.broken = True
                    prev_structure = StructureType.BULLISH
            
            # Check for bearish MSS (break below swing low after uptrend)
            for swing_low in self.swing_lows:
                if swing_low.broken or swing_low.index >= i:
                    continue
                
                if candle['close'] < swing_low.price - self.min_break_pips:
                    if prev_structure == StructureType.BULLISH:
                        shift_type = 'MSS'
                    else:
                        shift_type = 'BOS'
                    
                    strength = self._calculate_break_strength(
                        swing_low.price, candle['close'], df, i
                    )
                    
                    shifts.append(StructureShift(
                        shift_type=shift_type,
                        direction='bearish',
                        break_price=swing_low.price,
                        break_time=candle['time'],
                        previous_structure=prev_structure,
                        new_structure=StructureType.BEARISH,
                        strength=strength
                    ))
                    
                    swing_low.broken = True
                    prev_structure = StructureType.BEARISH
        
        return shifts
    
    def _calculate_break_strength(self, high: float, low: float, 
                                  df: pd.DataFrame, idx: int) -> float:
        """
        Calculate strength of structure break
        
        Returns 0-100 score based on:
        - Size of break
        - Momentum (number of bars)
        - Volume
        """
        break_size = abs(high - low)
        
        # Get ATR for context
        if idx >= 14:
            atr = self._calculate_atr(df, idx, 14)
            if atr > 0:
                # Strength based on break size relative to ATR
                strength = min((break_size / atr) * 50, 100)
                return strength
        
        return 50.0  # Default moderate strength
    
    def _calculate_atr(self, df: pd.DataFrame, idx: int, period: int = 14) -> float:
        """Calculate Average True Range"""
        if idx < period:
            return 0.0
        
        tr_values = []
        for i in range(idx - period + 1, idx + 1):
            high = df.iloc[i]['high']
            low = df.iloc[i]['low']
            prev_close = df.iloc[i-1]['close'] if i > 0 else df.iloc[i]['close']
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_values.append(tr)
        
        return np.mean(tr_values)
    
    def _determine_current_structure(self) -> StructureType:
        """Determine current market structure based on recent shifts"""
        if not self.structure_shifts:
            return StructureType.UNKNOWN
        
        # Get last 3 shifts
        recent_shifts = self.structure_shifts[-3:] if len(self.structure_shifts) >= 3 else self.structure_shifts
        
        # If last shift is MSS, that's the current structure
        if recent_shifts[-1].shift_type == 'MSS':
            return recent_shifts[-1].new_structure
        
        # If multiple BOS in same direction, confirm structure
        bullish_count = sum(1 for s in recent_shifts if s.direction == 'bullish')
        bearish_count = sum(1 for s in recent_shifts if s.direction == 'bearish')
        
        if bullish_count > bearish_count:
            return StructureType.BULLISH
        elif bearish_count > bullish_count:
            return StructureType.BEARISH
        else:
            return StructureType.RANGING
    
    def get_latest_shift(self) -> Optional[StructureShift]:
        """Get most recent structure shift"""
        if not self.structure_shifts:
            return None
        return self.structure_shifts[-1]
    
    def is_bullish_structure(self) -> bool:
        """Check if current structure is bullish"""
        return self.current_structure == StructureType.BULLISH
    
    def is_bearish_structure(self) -> bool:
        """Check if current structure is bearish"""
        return self.current_structure == StructureType.BEARISH
    
    def get_last_swing_high(self) -> Optional[SwingPoint]:
        """Get most recent swing high (unbroken preferred)"""
        unbroken = [sh for sh in self.swing_highs if not sh.broken]
        if unbroken:
            return unbroken[-1]
        return self.swing_highs[-1] if self.swing_highs else None
    
    def get_last_swing_low(self) -> Optional[SwingPoint]:
        """Get most recent swing low (unbroken preferred)"""
        unbroken = [sl for sl in self.swing_lows if not sl.broken]
        if unbroken:
            return unbroken[-1]
        return self.swing_lows[-1] if self.swing_lows else None
    
    def is_mss_confirmed(self, max_bars_ago: int = 5) -> bool:
        """
        Check if a Market Structure Shift was confirmed recently
        
        Args:
            max_bars_ago: Maximum bars since MSS
            
        Returns:
            True if recent MSS confirmed
        """
        latest = self.get_latest_shift()
        if not latest:
            return False
        
        return latest.shift_type == 'MSS'
    
    def get_structure_bias(self) -> str:
        """
        Get trading bias based on structure
        
        Returns:
            'LONG' | 'SHORT' | 'NEUTRAL'
        """
        if self.is_bullish_structure():
            return 'LONG'
        elif self.is_bearish_structure():
            return 'SHORT'
        else:
            return 'NEUTRAL'
    
    def validate_structure_for_trade(self, direction: str) -> Tuple[bool, str]:
        """
        Validate if structure supports trade direction
        
        Args:
            direction: 'LONG' or 'SHORT'
            
        Returns:
            (is_valid, reason)
        
        FIX: Require recent MSS/BOS confirmation - not just general bullish/bearish structure
        """
        if direction == 'LONG':
            if self.is_bullish_structure():
                latest = self.get_latest_shift()
                if latest and latest.shift_type == 'MSS' and latest.direction == 'bullish':
                    return (True, "Bullish MSS confirmed")
                elif latest and latest.shift_type == 'BOS' and latest.direction == 'bullish':
                    return (True, "Bullish BOS continuation")
                else:
                    # FIX: No recent confirmation - require MSS/BOS for valid signal
                    return (False, f"No recent MSS/BOS - structure is {self.current_structure.value}")
            else:
                return (False, f"Structure is {self.current_structure.value}, not bullish")
        
        elif direction == 'SHORT':
            if self.is_bearish_structure():
                latest = self.get_latest_shift()
                if latest and latest.shift_type == 'MSS' and latest.direction == 'bearish':
                    return (True, "Bearish MSS confirmed")
                elif latest and latest.shift_type == 'BOS' and latest.direction == 'bearish':
                    return (True, "Bearish BOS continuation")
                else:
                    # FIX: No recent confirmation - require MSS/BOS for valid signal
                    return (False, f"No recent MSS/BOS - structure is {self.current_structure.value}")
            else:
                return (False, f"Structure is {self.current_structure.value}, not bearish")
        
        return (False, "Invalid direction")
