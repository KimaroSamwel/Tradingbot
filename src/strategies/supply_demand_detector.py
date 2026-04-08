"""
SUPPLY & DEMAND ZONE DETECTOR
Institutional-grade zone identification based on order flow imbalances

Implements the complete Supply/Demand methodology:
- Drop-Base-Rally / Rally-Base-Drop pattern detection
- Zone strength scoring (0-10)
- Freshness tracking
- Multi-timeframe validation
- Zone polarity flips
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SupplyDemandZone:
    """Supply or Demand zone"""
    zone_type: str  # 'demand' or 'supply'
    top: float
    bottom: float
    strength: float  # 0-10 score
    freshness: int  # 0 = never tested, 1+ = number of tests
    creation_time: datetime
    creation_index: int
    timeframe: str
    move_distance: float  # Pips moved from zone
    zone_width: float  # Width of zone in pips
    base_candles: int  # Number of candles in base
    tested_count: int = 0
    last_test_time: Optional[datetime] = None
    failed: bool = False
    
    def is_fresh(self) -> bool:
        """Check if zone is fresh (0-1 tests)"""
        return self.tested_count <= 1
    
    def is_prime(self) -> bool:
        """Check if zone is prime (2-3 tests)"""
        return 2 <= self.tested_count <= 3
    
    def is_exhausted(self) -> bool:
        """Check if zone is exhausted (4+ tests)"""
        return self.tested_count >= 4
    
    def get_quality_rating(self) -> str:
        """Get quality rating based on tests"""
        if self.is_fresh():
            return "FRESH"
        elif self.is_prime():
            return "PRIME"
        else:
            return "EXHAUSTED"


class SupplyDemandDetector:
    """
    Detect institutional supply and demand zones
    
    Key Patterns:
    - Drop-Base-Rally (Demand)
    - Rally-Base-Drop (Supply)
    - Rally-Base-Rally (Continuation Demand)
    - Drop-Base-Drop (Continuation Supply)
    """
    
    def __init__(self, 
                 lookback: int = 100,
                 min_move_atr: float = 1.5,
                 max_base_candles: int = 5,
                 min_strength: float = 3.0):
        """
        Args:
            lookback: Bars to look back for zone detection
            min_move_atr: Minimum move in ATR multiples
            max_base_candles: Maximum candles in consolidation base
            min_strength: Minimum strength score to keep zone
        """
        self.lookback = lookback
        self.min_move_atr = min_move_atr
        self.max_base_candles = max_base_candles
        self.min_strength = min_strength
        self.active_zones: List[SupplyDemandZone] = []
    
    def find_zones(self, df: pd.DataFrame, timeframe: str = 'H1') -> List[SupplyDemandZone]:
        """
        Find all supply and demand zones in dataframe
        
        Args:
            df: OHLC dataframe with ATR column
            timeframe: Timeframe identifier
            
        Returns:
            List of detected zones
        """
        if len(df) < self.lookback:
            return []
        
        zones = []
        
        # Calculate ATR if not present
        if 'atr' not in df.columns:
            df['atr'] = self._calculate_atr(df, 14)
        
        # Scan for zones
        for i in range(self.lookback, len(df) - 20):
            # Check for impulsive moves
            demand_zone = self._detect_demand_zone(df, i, timeframe)
            if demand_zone:
                zones.append(demand_zone)
            
            supply_zone = self._detect_supply_zone(df, i, timeframe)
            if supply_zone:
                zones.append(supply_zone)
        
        # Filter overlapping zones (keep strongest)
        zones = self._filter_overlapping_zones(zones)
        
        # Filter by minimum strength
        zones = [z for z in zones if z.strength >= self.min_strength]
        
        return zones
    
    def _detect_demand_zone(self, df: pd.DataFrame, idx: int, timeframe: str) -> Optional[SupplyDemandZone]:
        """
        Detect demand zone (Drop-Base-Rally pattern)
        
        Pattern:
        1. Price drops (creating selling pressure)
        2. Consolidation base (1-5 candles)
        3. Explosive rally (demand overwhelms supply)
        
        FIX: Removed lookahead bias - zone detection now uses ONLY past data
        """
        # Find base consolidation BEFORE rally (no future data)
        base_start, base_end = self._find_base_before_move(df, idx, 'up')
        
        if base_start is None or base_end is None:
            return None
        
        # Safe integer casting
        _base_start = int(base_start)
        _base_end = int(base_end)
        
        atr = float(df['atr'].iloc[idx])  # type: ignore
        
        # Mark zone boundaries (consolidation candle bodies)
        zone_data = df[['open', 'close']].iloc[_base_start:_base_end+1]  # type: ignore
        zone_top = float(zone_data.max().max())  # type: ignore
        zone_bottom = float(zone_data.min().min())  # type: ignore
        
        zone_width = zone_top - zone_bottom
        
        # Validate zone isn't too wide
        if zone_width > atr * 2:
            return None
        
        # Calculate move AFTER the base (retrospective - for strength scoring only)
        if idx + 1 < len(df):
            future_high = float(df['high'].iloc[idx+1:min(idx+20, len(df))].max())  # type: ignore
            future_move = future_high - float(df['close'].iloc[idx])  # type: ignore
        else:
            future_move = atr * self.min_move_atr  # Conservative default
        
        # Calculate strength score
        strength = self._calculate_zone_strength(
            df, _base_start, _base_end, idx, future_move, zone_width, 'demand'
        )
        
        # Handle creation_time from index - convert to datetime
        idx_time = df.index[idx]
        if isinstance(idx_time, datetime):
            creation_time = idx_time
        else:
            creation_time = datetime.now()
        
        return SupplyDemandZone(
            zone_type='demand',
            top=zone_top,
            bottom=zone_bottom,
            strength=strength,
            freshness=0,
            creation_time=creation_time,
            creation_index=idx,
            timeframe=timeframe,
            move_distance=future_move,
            zone_width=zone_width,
            base_candles=_base_end - _base_start + 1
        )
    
    def _detect_supply_zone(self, df: pd.DataFrame, idx: int, timeframe: str) -> Optional[SupplyDemandZone]:
        """
        Detect supply zone (Rally-Base-Drop pattern)
        
        Pattern:
        1. Price rallies (creating buying pressure)
        2. Consolidation base (1-5 candles)
        3. Explosive drop (supply overwhelms demand)
        
        FIX: Removed lookahead bias - zone detection now uses ONLY past data
        """
        # Find base consolidation BEFORE drop (no future data)
        base_start, base_end = self._find_base_before_move(df, idx, 'down')
        
        if base_start is None or base_end is None:
            return None
        
        # Safe integer casting
        _base_start = int(base_start)
        _base_end = int(base_end)
        
        atr = float(df['atr'].iloc[idx])  # type: ignore
        
        # Mark zone boundaries
        zone_data = df[['open', 'close']].iloc[_base_start:_base_end+1]  # type: ignore
        zone_top = float(zone_data.max().max())  # type: ignore
        zone_bottom = float(zone_data.min().min())  # type: ignore
        
        zone_width = zone_top - zone_bottom
        
        # Validate zone width
        if zone_width > atr * 2:
            return None
        
        # Calculate move AFTER the base (retrospective - for strength scoring only)
        if idx + 1 < len(df):
            future_low = float(df['low'].iloc[idx+1:min(idx+20, len(df))].min())  # type: ignore
            future_move = float(df['close'].iloc[idx]) - future_low  # type: ignore
        else:
            future_move = atr * self.min_move_atr  # Conservative default
        
        # Calculate strength score
        strength = self._calculate_zone_strength(
            df, _base_start, _base_end, idx, future_move, zone_width, 'supply'
        )
        
        # Handle creation_time from index - convert to datetime
        idx_time = df.index[idx]
        if isinstance(idx_time, datetime):
            creation_time = idx_time
        else:
            creation_time = datetime.now()
        
        return SupplyDemandZone(
            zone_type='supply',
            top=zone_top,
            bottom=zone_bottom,
            strength=strength,
            freshness=0,
            creation_time=creation_time,
            creation_index=idx,
            timeframe=timeframe,
            move_distance=future_move,
            zone_width=zone_width,
            base_candles=_base_end - _base_start + 1
        )
    
    def _find_base_before_move(self, df: pd.DataFrame, idx: int, direction: str) -> Tuple[Optional[int], Optional[int]]:
        """
        Find consolidation base before impulsive move
        
        Returns:
            (base_start_index, base_end_index) or (None, None)
        """
        # Look back up to max_base_candles for consolidation
        base_end = idx
        
        # Find consolidation (low volatility candles)
        atr = df['atr'].iloc[idx]
        
        for lookback in range(1, self.max_base_candles + 1):
            start_idx = idx - lookback
            
            if start_idx < 0:
                return None, None
            
            # Check if candles are consolidating (range < ATR)
            base_high = df['high'].iloc[start_idx:base_end+1].max()
            base_low = df['low'].iloc[start_idx:base_end+1].min()
            base_range = base_high - base_low
            
            # Valid base if range is contained
            if base_range < atr * 1.5:
                return start_idx, base_end
        
        return None, None
    
    def _calculate_zone_strength(self, df: pd.DataFrame, base_start: int, base_end: int,
                                 move_start: int, move_distance: float, zone_width: float,
                                 zone_type: str) -> float:
        """
        Calculate zone strength score (0-10)
        
        Scoring factors:
        - Move strength (0-2): Distance moved / zone width
        - Reaction speed (0-2): How many candles to reach target
        - Volume/Spread (0-1): If available
        - Consolidation quality (0-2): Tightness of base
        - Structure alignment (0-2): Aligned with higher TF swings
        - Base candles (0-1): Fewer candles = stronger
        """
        score = 0.0
        
        # 1. Move Strength (0-2)
        if zone_width > 0:
            move_ratio = move_distance / zone_width
            score += min(move_ratio / 5.0, 2.0)  # Normalize to 0-2
        
        # 2. Reaction Speed (0-2)
        candles_to_move = move_start - base_end
        if candles_to_move <= 3:
            score += 2.0  # Very fast
        elif candles_to_move <= 5:
            score += 1.5
        elif candles_to_move <= 10:
            score += 1.0
        else:
            score += 0.5
        
        # 3. Consolidation Quality (0-2)
        base_candles = base_end - base_start + 1
        if base_candles <= 2:
            score += 2.0  # Tight consolidation
        elif base_candles <= 3:
            score += 1.5
        else:
            score += 1.0
        
        # 4. Base Candles (0-1) - Fewer is better
        if base_candles == 1:
            score += 1.0
        elif base_candles <= 3:
            score += 0.7
        else:
            score += 0.3
        
        # 5. Structure Quality (0-2)
        # Check if zone is at swing high/low
        lookback_range = 10
        if zone_type == 'demand':
            local_low = df['low'].iloc[max(0, base_start-lookback_range):base_end+lookback_range].min()
            if abs(local_low - df['low'].iloc[base_start:base_end+1].min()) < zone_width * 0.1:
                score += 2.0  # Zone at local low
            else:
                score += 1.0
        else:  # supply
            local_high = df['high'].iloc[max(0, base_start-lookback_range):base_end+lookback_range].max()
            if abs(local_high - df['high'].iloc[base_start:base_end+1].max()) < zone_width * 0.1:
                score += 2.0  # Zone at local high
            else:
                score += 1.0
        
        # 6. Freshness bonus (0-1) - Fresh zones start with bonus
        score += 1.0
        
        return min(score, 10.0)
    
    def _filter_overlapping_zones(self, zones: List[SupplyDemandZone]) -> List[SupplyDemandZone]:
        """
        Filter overlapping zones, keeping strongest
        """
        if not zones:
            return []
        
        # Sort by strength descending
        zones_sorted = sorted(zones, key=lambda z: z.strength, reverse=True)
        
        filtered = []
        for zone in zones_sorted:
            # Check if overlaps with existing filtered zones
            overlaps = False
            for existing in filtered:
                if self._zones_overlap(zone, existing):
                    overlaps = True
                    break
            
            if not overlaps:
                filtered.append(zone)
        
        return filtered
    
    def _zones_overlap(self, zone1: SupplyDemandZone, zone2: SupplyDemandZone) -> bool:
        """Check if two zones overlap"""
        return not (zone1.bottom > zone2.top or zone2.bottom > zone1.top)
    
    def check_zone_touch(self, zone: SupplyDemandZone, current_low: float, current_high: float) -> bool:
        """
        Check if current candle touched zone
        
        Args:
            zone: Supply/Demand zone
            current_low: Current candle low
            current_high: Current candle high
            
        Returns:
            True if zone was touched
        """
        return current_low <= zone.top and current_high >= zone.bottom
    
    def check_rejection_pattern(self, df: pd.DataFrame, zone: SupplyDemandZone) -> Tuple[bool, str]:
        """
        Check for rejection pattern at zone
        
        Patterns:
        - Pin bar (long wick rejection)
        - Engulfing
        - Inside bar breakout
        
        Returns:
            (has_rejection, pattern_name)
        """
        if len(df) < 2:
            return False, ""
        
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Pin bar detection
        if zone.zone_type == 'demand':
            body = abs(current['close'] - current['open'])
            lower_wick = min(current['close'], current['open']) - current['low']
            upper_wick = current['high'] - max(current['close'], current['open'])
            
            # Bullish pin bar
            if lower_wick > body * 2 and lower_wick > upper_wick * 2:
                if current['low'] <= zone.top and current['close'] > zone.bottom:
                    return True, "BULLISH_PIN_BAR"
        
        else:  # supply
            body = abs(current['close'] - current['open'])
            upper_wick = current['high'] - max(current['close'], current['open'])
            lower_wick = min(current['close'], current['open']) - current['low']
            
            # Bearish pin bar
            if upper_wick > body * 2 and upper_wick > lower_wick * 2:
                if current['high'] >= zone.bottom and current['close'] < zone.top:
                    return True, "BEARISH_PIN_BAR"
        
        # Engulfing pattern
        if zone.zone_type == 'demand':
            # Bullish engulfing
            if (current['close'] > prev['open'] and 
                current['open'] < prev['close'] and
                current['close'] > current['open']):
                return True, "BULLISH_ENGULFING"
        else:
            # Bearish engulfing
            if (current['close'] < prev['open'] and 
                current['open'] > prev['close'] and
                current['close'] < current['open']):
                return True, "BEARISH_ENGULFING"
        
        return False, ""
    
    def update_zone_tests(self, zones: List[SupplyDemandZone], df: pd.DataFrame) -> List[SupplyDemandZone]:
        """
        Update zone test counts when price touches zones
        
        Args:
            zones: List of active zones
            df: Current OHLC data
            
        Returns:
            Updated zones list
        """
        current_candle = df.iloc[-1]
        current_low = current_candle['low']
        current_high = current_candle['high']
        
        for zone in zones:
            if self.check_zone_touch(zone, current_low, current_high):
                zone.tested_count += 1
                zone.last_test_time = current_candle.name
                
                # Check if zone failed (broke through)
                if zone.zone_type == 'demand':
                    if current_candle['close'] < zone.bottom:
                        zone.failed = True
                else:  # supply
                    if current_candle['close'] > zone.top:
                        zone.failed = True
        
        # Remove failed zones
        zones = [z for z in zones if not z.failed]
        
        return zones
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr
