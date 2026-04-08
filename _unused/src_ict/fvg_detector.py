"""
ICT FAIR VALUE GAP (FVG) DETECTOR
Detects price imbalances that institutions will likely fill

FVG = A 3-candle pattern showing inefficient price delivery
- Gap between candle 1's high/low and candle 3's low/high
- Created during rapid institutional moves
- Price tends to return to fill these gaps (50-100%)
- Used as entry zones in ICT trading
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FairValueGap:
    """Fair Value Gap structure"""
    gap_type: str  # 'bullish' or 'bearish'
    start_time: datetime
    end_time: datetime
    top: float  # Upper boundary of gap
    bottom: float  # Lower boundary of gap
    midpoint: float  # 50% level (equilibrium)
    size_pips: float  # Gap size in pips
    filled: bool = False
    fill_percentage: float = 0.0
    fill_time: Optional[datetime] = None
    strength: float = 0.0  # Based on gap size and volume


@dataclass
class InversionFVG:
    """Inversion Fair Value Gap - FVG that becomes support/resistance"""
    original_fvg: FairValueGap
    inversion_time: datetime
    inversion_type: str  # 'support' or 'resistance'
    tested: bool = False
    holding: bool = True


class ICTFVGDetector:
    """
    Detect Fair Value Gaps using ICT methodology
    
    Bullish FVG:
    - Candle 1: Any candle
    - Candle 2: Strong bullish move (body > 50%)
    - Candle 3: Continuation up
    - Gap: Candle 1 high < Candle 3 low
    
    Bearish FVG:
    - Candle 1: Any candle
    - Candle 2: Strong bearish move (body > 50%)
    - Candle 3: Continuation down
    - Gap: Candle 1 low > Candle 3 high
    """
    
    def __init__(self, 
                 min_gap_pips: float = 5.0,
                 min_body_ratio: float = 0.5,
                 use_ote: bool = True):
        """
        Args:
            min_gap_pips: Minimum gap size to qualify as FVG
            min_body_ratio: Minimum body/range ratio for impulse candle
            use_ote: Use Optimal Trade Entry levels (62-78.6%)
        """
        self.min_gap_pips = min_gap_pips
        self.min_body_ratio = min_body_ratio
        self.use_ote = use_ote
        
        self.bullish_fvgs: List[FairValueGap] = []
        self.bearish_fvgs: List[FairValueGap] = []
        self.inversion_fvgs: List[InversionFVG] = []
    
    def detect_fvgs(self, df: pd.DataFrame) -> Dict[str, List[FairValueGap]]:
        """
        Detect all Fair Value Gaps in price data
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            Dict with 'bullish' and 'bearish' FVG lists
        """
        bullish_fvgs = []
        bearish_fvgs = []
        
        # Need at least 3 candles
        for i in range(2, len(df)):
            candle1 = df.iloc[i-2]
            candle2 = df.iloc[i-1]  # Impulse candle
            candle3 = df.iloc[i]
            
            # Check for Bullish FVG
            bullish_fvg = self._detect_bullish_fvg(candle1, candle2, candle3)
            if bullish_fvg:
                bullish_fvgs.append(bullish_fvg)
            
            # Check for Bearish FVG
            bearish_fvg = self._detect_bearish_fvg(candle1, candle2, candle3)
            if bearish_fvg:
                bearish_fvgs.append(bearish_fvg)
        
        self.bullish_fvgs = bullish_fvgs
        self.bearish_fvgs = bearish_fvgs
        
        return {
            'bullish': bullish_fvgs,
            'bearish': bearish_fvgs
        }
    
    def _detect_bullish_fvg(self, candle1: pd.Series, 
                           candle2: pd.Series, 
                           candle3: pd.Series) -> Optional[FairValueGap]:
        """
        Detect bullish FVG (upward imbalance)
        
        Pattern:
        - Candle 2 must be strongly bullish
        - Gap exists between candle 1 high and candle 3 low
        """
        # Candle 2 must be bullish with strong body
        c2_body = abs(candle2['close'] - candle2['open'])
        c2_range = candle2['high'] - candle2['low']
        
        if candle2['close'] <= candle2['open']:  # Not bullish
            return None
        
        if c2_range > 0 and (c2_body / c2_range) < self.min_body_ratio:
            return None
        
        # Check for gap
        gap_bottom = candle1['high']
        gap_top = candle3['low']
        
        # Must have a gap (candle 1 high < candle 3 low)
        if gap_top <= gap_bottom:
            return None
        
        gap_size = gap_top - gap_bottom
        
        # Must meet minimum gap size
        if gap_size < self.min_gap_pips:
            return None
        
        # Calculate midpoint (equilibrium - 50% level)
        midpoint = gap_bottom + (gap_size / 2)
        
        # Calculate strength based on gap size and candle 2 body
        strength = min((gap_size / self.min_gap_pips) * 30, 100)
        
        return FairValueGap(
            gap_type='bullish',
            start_time=candle1['time'],
            end_time=candle3['time'],
            top=gap_top,
            bottom=gap_bottom,
            midpoint=midpoint,
            size_pips=gap_size,
            strength=strength
        )
    
    def _detect_bearish_fvg(self, candle1: pd.Series, 
                           candle2: pd.Series, 
                           candle3: pd.Series) -> Optional[FairValueGap]:
        """
        Detect bearish FVG (downward imbalance)
        
        Pattern:
        - Candle 2 must be strongly bearish
        - Gap exists between candle 1 low and candle 3 high
        """
        # Candle 2 must be bearish with strong body
        c2_body = abs(candle2['close'] - candle2['open'])
        c2_range = candle2['high'] - candle2['low']
        
        if candle2['close'] >= candle2['open']:  # Not bearish
            return None
        
        if c2_range > 0 and (c2_body / c2_range) < self.min_body_ratio:
            return None
        
        # Check for gap
        gap_top = candle1['low']
        gap_bottom = candle3['high']
        
        # Must have a gap (candle 1 low > candle 3 high)
        if gap_bottom >= gap_top:
            return None
        
        gap_size = gap_top - gap_bottom
        
        if gap_size < self.min_gap_pips:
            return None
        
        midpoint = gap_bottom + (gap_size / 2)
        strength = min((gap_size / self.min_gap_pips) * 30, 100)
        
        return FairValueGap(
            gap_type='bearish',
            start_time=candle1['time'],
            end_time=candle3['time'],
            top=gap_top,
            bottom=gap_bottom,
            midpoint=midpoint,
            size_pips=gap_size,
            strength=strength
        )
    
    def update_fvg_fills(self, df: pd.DataFrame) -> None:
        """
        Update fill status of all FVGs based on current price action
        
        Args:
            df: Current OHLCV data
        """
        current_candle = df.iloc[-1]
        current_price = current_candle['close']
        current_high = current_candle['high']
        current_low = current_candle['low']
        
        # Update bullish FVGs
        for fvg in self.bullish_fvgs:
            if fvg.filled:
                continue
            
            # Check if price has entered the gap
            if current_low <= fvg.top:
                # Calculate fill percentage
                if current_low <= fvg.bottom:
                    fvg.fill_percentage = 100.0
                    fvg.filled = True
                else:
                    fill_amount = fvg.top - current_low
                    fvg.fill_percentage = (fill_amount / fvg.size_pips) * 100
                
                if fvg.fill_time is None:
                    fvg.fill_time = current_candle['time']
        
        # Update bearish FVGs
        for fvg in self.bearish_fvgs:
            if fvg.filled:
                continue
            
            if current_high >= fvg.bottom:
                if current_high >= fvg.top:
                    fvg.fill_percentage = 100.0
                    fvg.filled = True
                else:
                    fill_amount = current_high - fvg.bottom
                    fvg.fill_percentage = (fill_amount / fvg.size_pips) * 100
                
                if fvg.fill_time is None:
                    fvg.fill_time = current_candle['time']
    
    def get_unfilled_fvgs(self, gap_type: Optional[str] = None) -> List[FairValueGap]:
        """
        Get all unfilled FVGs
        
        Args:
            gap_type: 'bullish' or 'bearish' or None (both)
            
        Returns:
            List of unfilled FVGs
        """
        unfilled = []
        
        if gap_type is None or gap_type == 'bullish':
            unfilled.extend([fvg for fvg in self.bullish_fvgs if not fvg.filled])
        
        if gap_type is None or gap_type == 'bearish':
            unfilled.extend([fvg for fvg in self.bearish_fvgs if not fvg.filled])
        
        return unfilled
    
    def get_nearest_fvg(self, current_price: float, 
                       gap_type: str) -> Optional[FairValueGap]:
        """
        Get nearest unfilled FVG to current price
        
        Args:
            current_price: Current market price
            gap_type: 'bullish' or 'bearish'
            
        Returns:
            Nearest FairValueGap or None
        """
        fvgs = self.bullish_fvgs if gap_type == 'bullish' else self.bearish_fvgs
        unfilled = [fvg for fvg in fvgs if not fvg.filled]
        
        if not unfilled:
            return None
        
        # Find closest by midpoint distance
        nearest = min(unfilled, key=lambda fvg: abs(fvg.midpoint - current_price))
        return nearest
    
    def get_ote_levels(self, fvg: FairValueGap) -> Dict[str, float]:
        """
        Get Optimal Trade Entry levels (62-78.6% Fibonacci)
        
        Args:
            fvg: FairValueGap to calculate OTE for
            
        Returns:
            Dict with entry levels
        """
        gap_size = fvg.size_pips
        
        # Calculate Fibonacci retracement levels within FVG
        fib_618 = fvg.bottom + (gap_size * 0.618)
        fib_786 = fvg.bottom + (gap_size * 0.786)
        fib_50 = fvg.midpoint
        
        return {
            'ote_low': fib_618,  # Best entry (62%)
            'ote_high': fib_786,  # Max entry (78.6%)
            'equilibrium': fib_50,  # 50% level
            'gap_bottom': fvg.bottom,
            'gap_top': fvg.top
        }
    
    def is_price_in_ote_zone(self, price: float, fvg: FairValueGap) -> bool:
        """
        Check if price is in Optimal Trade Entry zone (62-78.6%)
        
        Args:
            price: Current price
            fvg: FairValueGap to check
            
        Returns:
            True if price is in OTE zone
        """
        if not self.use_ote:
            # If not using OTE, any price in gap is valid
            return fvg.bottom <= price <= fvg.top
        
        ote_levels = self.get_ote_levels(fvg)
        return ote_levels['ote_low'] <= price <= ote_levels['ote_high']
    
    def detect_inversion_fvgs(self, df: pd.DataFrame) -> List[InversionFVG]:
        """
        Detect FVGs that have inverted (become support/resistance)
        
        An FVG inverts when:
        1. Price fills the gap completely
        2. Price reverses at the gap
        3. Gap now acts as support (bullish) or resistance (bearish)
        
        Args:
            df: OHLCV DataFrame
            
        Returns:
            List of InversionFVG objects
        """
        inversions = []
        
        # Check filled bullish FVGs
        for fvg in self.bullish_fvgs:
            if fvg.filled and fvg.fill_percentage >= 50:
                # Check if it's now acting as support
                # Look for price rejecting from FVG zone
                inversion = self._check_fvg_inversion(df, fvg, 'support')
                if inversion:
                    inversions.append(inversion)
        
        # Check filled bearish FVGs
        for fvg in self.bearish_fvgs:
            if fvg.filled and fvg.fill_percentage >= 50:
                inversion = self._check_fvg_inversion(df, fvg, 'resistance')
                if inversion:
                    inversions.append(inversion)
        
        self.inversion_fvgs = inversions
        return inversions
    
    def _check_fvg_inversion(self, df: pd.DataFrame, 
                            fvg: FairValueGap,
                            inversion_type: str) -> Optional[InversionFVG]:
        """Check if FVG has inverted to support/resistance"""
        # Look at recent price action after fill
        if fvg.fill_time is None:
            return None
        
        # Find candles after fill
        fill_idx = df[df['time'] == fvg.fill_time].index[0] if fvg.fill_time in df['time'].values else -1
        
        if fill_idx < 0 or fill_idx >= len(df) - 3:
            return None
        
        # Check next few candles for rejection
        for i in range(fill_idx + 1, min(fill_idx + 5, len(df))):
            candle = df.iloc[i]
            
            if inversion_type == 'support':
                # Price should bounce up from FVG zone
                if candle['low'] <= fvg.top and candle['close'] > fvg.top:
                    return InversionFVG(
                        original_fvg=fvg,
                        inversion_time=candle['time'],
                        inversion_type='support'
                    )
            else:  # resistance
                # Price should reject down from FVG zone
                if candle['high'] >= fvg.bottom and candle['close'] < fvg.bottom:
                    return InversionFVG(
                        original_fvg=fvg,
                        inversion_time=candle['time'],
                        inversion_type='resistance'
                    )
        
        return None
    
    def get_fvg_summary(self) -> Dict:
        """Get summary of all detected FVGs"""
        total_bullish = len(self.bullish_fvgs)
        total_bearish = len(self.bearish_fvgs)
        
        unfilled_bullish = sum(1 for fvg in self.bullish_fvgs if not fvg.filled)
        unfilled_bearish = sum(1 for fvg in self.bearish_fvgs if not fvg.filled)
        
        return {
            'total_bullish_fvgs': total_bullish,
            'total_bearish_fvgs': total_bearish,
            'unfilled_bullish': unfilled_bullish,
            'unfilled_bearish': unfilled_bearish,
            'inversion_fvgs': len(self.inversion_fvgs),
            'bullish_fvgs': self.bullish_fvgs,
            'bearish_fvgs': self.bearish_fvgs
        }
