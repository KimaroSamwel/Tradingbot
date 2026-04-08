"""
Order Blocks & Smart Money Concepts
Implements institutional trading concepts:
- Order Blocks (OB)
- Breaker Blocks (BB)
- Mitigation Blocks
- Fair Value Gaps (FVG)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OrderBlock:
    """Order Block structure"""
    ob_type: str  # 'bullish' or 'bearish'
    start_time: datetime
    end_time: datetime
    high: float
    low: float
    close: float
    volume: float
    strength: float  # 0-100
    tested: bool = False
    broken: bool = False
    mitigation_count: int = 0


@dataclass
class FairValueGap:
    """Fair Value Gap (imbalance)"""
    gap_type: str  # 'bullish' or 'bearish'
    start_time: datetime
    top: float
    bottom: float
    size: float
    filled: bool = False
    fill_percentage: float = 0.0


class OrderBlockDetector:
    """
    Detect institutional order blocks
    
    Order Block = Last down candle before strong up move (bullish OB)
                 or last up candle before strong down move (bearish OB)
    """
    
    def __init__(self, min_body_pct: float = 50.0, min_move_pips: float = 20.0):
        """
        Args:
            min_body_pct: Minimum body as % of total candle
            min_move_pips: Minimum move size to qualify
        """
        self.min_body_pct = min_body_pct
        self.min_move_pips = min_move_pips
        self.order_blocks = []
    
    def detect_order_blocks(self, df: pd.DataFrame) -> List[OrderBlock]:
        """
        Detect order blocks in price data
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            List of OrderBlock objects
        """
        order_blocks = []
        
        for i in range(3, len(df) - 3):
            # Bullish Order Block Detection
            # Last bearish candle before strong bullish move
            if self._is_bullish_order_block(df, i):
                ob = self._create_order_block(df, i, 'bullish')
                if ob:
                    order_blocks.append(ob)
            
            # Bearish Order Block Detection
            # Last bullish candle before strong bearish move
            if self._is_bearish_order_block(df, i):
                ob = self._create_order_block(df, i, 'bearish')
                if ob:
                    order_blocks.append(ob)
        
        self.order_blocks = order_blocks
        return order_blocks
    
    def _is_bullish_order_block(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if candle at idx is a bullish order block"""
        current = df.iloc[idx]
        next_candle = df.iloc[idx + 1]
        
        # Current candle should be bearish (close < open)
        if current['close'] >= current['open']:
            return False
        
        # Body should be significant
        body_pct = abs(current['close'] - current['open']) / (current['high'] - current['low']) * 100
        if body_pct < self.min_body_pct:
            return False
        
        # Next candle should be strongly bullish
        next_move = next_candle['close'] - next_candle['open']
        if next_move <= 0:
            return False
        
        # Move should be significant
        move_pips = next_move * 10000  # Assuming 4-digit pricing
        if move_pips < self.min_move_pips:
            return False
        
        # Next candle should break above current high
        if next_candle['close'] <= current['high']:
            return False
        
        return True
    
    def _is_bearish_order_block(self, df: pd.DataFrame, idx: int) -> bool:
        """Check if candle at idx is a bearish order block"""
        current = df.iloc[idx]
        next_candle = df.iloc[idx + 1]
        
        # Current candle should be bullish (close > open)
        if current['close'] <= current['open']:
            return False
        
        # Body should be significant
        body_pct = abs(current['close'] - current['open']) / (current['high'] - current['low']) * 100
        if body_pct < self.min_body_pct:
            return False
        
        # Next candle should be strongly bearish
        next_move = next_candle['open'] - next_candle['close']
        if next_move <= 0:
            return False
        
        # Move should be significant
        move_pips = next_move * 10000
        if move_pips < self.min_move_pips:
            return False
        
        # Next candle should break below current low
        if next_candle['close'] >= current['low']:
            return False
        
        return True
    
    def _create_order_block(self, df: pd.DataFrame, idx: int, ob_type: str) -> Optional[OrderBlock]:
        """Create OrderBlock object"""
        candle = df.iloc[idx]
        next_candle = df.iloc[idx + 1]
        
        # Calculate strength based on subsequent move
        if ob_type == 'bullish':
            move = next_candle['high'] - candle['low']
            strength = min(100, (move / candle['low']) * 10000)  # Normalize to 0-100
        else:
            move = candle['high'] - next_candle['low']
            strength = min(100, (move / candle['high']) * 10000)
        
        return OrderBlock(
            ob_type=ob_type,
            start_time=candle.name,
            end_time=next_candle.name,
            high=candle['high'],
            low=candle['low'],
            close=candle['close'],
            volume=candle.get('tick_volume', 0),
            strength=strength
        )
    
    def get_active_order_blocks(self, current_price: float) -> List[OrderBlock]:
        """Get order blocks that haven't been broken"""
        active = []
        
        for ob in self.order_blocks:
            if ob.broken:
                continue
            
            # Check if price has broken the order block
            if ob.ob_type == 'bullish':
                if current_price < ob.low:
                    ob.broken = True
                else:
                    active.append(ob)
            else:  # bearish
                if current_price > ob.high:
                    ob.broken = True
                else:
                    active.append(ob)
        
        return active
    
    def is_price_at_order_block(self, current_price: float, tolerance_pips: float = 5.0) -> Optional[OrderBlock]:
        """
        Check if current price is near an active order block
        
        Args:
            current_price: Current market price
            tolerance_pips: Distance tolerance in pips
        
        Returns:
            OrderBlock if price is near one, None otherwise
        """
        active_obs = self.get_active_order_blocks(current_price)
        tolerance = tolerance_pips / 10000  # Convert to price
        
        for ob in active_obs:
            if ob.ob_type == 'bullish':
                # Check if price is near the top of bullish OB
                if abs(current_price - ob.high) <= tolerance:
                    ob.tested = True
                    ob.mitigation_count += 1
                    return ob
            else:  # bearish
                # Check if price is near the bottom of bearish OB
                if abs(current_price - ob.low) <= tolerance:
                    ob.tested = True
                    ob.mitigation_count += 1
                    return ob
        
        return None


class FairValueGapDetector:
    """
    Detect Fair Value Gaps (FVG) / Imbalances
    
    FVG = Gap between candle[i-1].low and candle[i+1].high (bullish)
         or gap between candle[i-1].high and candle[i+1].low (bearish)
    """
    
    def __init__(self, min_gap_pips: float = 10.0):
        """
        Args:
            min_gap_pips: Minimum gap size in pips
        """
        self.min_gap_pips = min_gap_pips
        self.fvgs = []
    
    def detect_fair_value_gaps(self, df: pd.DataFrame) -> List[FairValueGap]:
        """
        Detect fair value gaps
        
        Args:
            df: DataFrame with OHLC data
        
        Returns:
            List of FairValueGap objects
        """
        fvgs = []
        
        for i in range(1, len(df) - 1):
            # Bullish FVG
            fvg = self._check_bullish_fvg(df, i)
            if fvg:
                fvgs.append(fvg)
            
            # Bearish FVG
            fvg = self._check_bearish_fvg(df, i)
            if fvg:
                fvgs.append(fvg)
        
        self.fvgs = fvgs
        return fvgs
    
    def _check_bullish_fvg(self, df: pd.DataFrame, idx: int) -> Optional[FairValueGap]:
        """Check for bullish fair value gap"""
        prev = df.iloc[idx - 1]
        current = df.iloc[idx]
        next_candle = df.iloc[idx + 1]
        
        # Bullish FVG: gap between prev.high and next.low
        if prev['high'] < next_candle['low']:
            gap_size = next_candle['low'] - prev['high']
            gap_pips = gap_size * 10000
            
            if gap_pips >= self.min_gap_pips:
                return FairValueGap(
                    gap_type='bullish',
                    start_time=current.name,
                    top=next_candle['low'],
                    bottom=prev['high'],
                    size=gap_size
                )
        
        return None
    
    def _check_bearish_fvg(self, df: pd.DataFrame, idx: int) -> Optional[FairValueGap]:
        """Check for bearish fair value gap"""
        prev = df.iloc[idx - 1]
        current = df.iloc[idx]
        next_candle = df.iloc[idx + 1]
        
        # Bearish FVG: gap between prev.low and next.high
        if prev['low'] > next_candle['high']:
            gap_size = prev['low'] - next_candle['high']
            gap_pips = gap_size * 10000
            
            if gap_pips >= self.min_gap_pips:
                return FairValueGap(
                    gap_type='bearish',
                    start_time=current.name,
                    top=prev['low'],
                    bottom=next_candle['high'],
                    size=gap_size
                )
        
        return None
    
    def get_unfilled_fvgs(self, current_price: float) -> List[FairValueGap]:
        """Get FVGs that haven't been filled yet"""
        return [fvg for fvg in self.fvgs if not fvg.filled]
    
    def update_fvg_status(self, current_price: float):
        """Update FVG fill status based on current price"""
        for fvg in self.fvgs:
            if fvg.filled:
                continue
            
            # Check if price has entered the gap
            if fvg.bottom <= current_price <= fvg.top:
                # Calculate fill percentage
                if fvg.gap_type == 'bullish':
                    fvg.fill_percentage = (current_price - fvg.bottom) / fvg.size * 100
                else:
                    fvg.fill_percentage = (fvg.top - current_price) / fvg.size * 100
                
                # Mark as filled if 50% or more filled
                if fvg.fill_percentage >= 50:
                    fvg.filled = True


class SmartMoneyConceptsAnalyzer:
    """
    Analyze Smart Money Concepts (AMD):
    - Accumulation
    - Manipulation
    - Distribution
    """
    
    def __init__(self):
        self.ob_detector = OrderBlockDetector()
        self.fvg_detector = FairValueGapDetector()
    
    def analyze_market_phase(self, df: pd.DataFrame) -> Dict:
        """
        Determine current market phase (Accumulation, Manipulation, Distribution)
        
        Args:
            df: DataFrame with OHLCV data
        
        Returns:
            Dict with phase analysis
        """
        # Detect order blocks and FVGs
        order_blocks = self.ob_detector.detect_order_blocks(df)
        fvgs = self.fvg_detector.detect_fair_value_gaps(df)
        
        # Analyze recent price action
        recent = df.tail(20)
        
        # Calculate range metrics
        high = recent['high'].max()
        low = recent['low'].min()
        range_size = high - low
        current_price = df.iloc[-1]['close']
        
        # Calculate position in range
        position_in_range = (current_price - low) / range_size if range_size > 0 else 0.5
        
        # Volume analysis
        avg_volume = recent['tick_volume'].mean()
        current_volume = df.iloc[-1]['tick_volume']
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Volatility analysis
        volatility = recent['high'].std() / recent['close'].mean() if len(recent) > 0 else 0
        
        # Determine phase
        phase = self._classify_phase(
            position_in_range, volume_ratio, volatility,
            len([ob for ob in order_blocks if not ob.broken]),
            len([fvg for fvg in fvgs if not fvg.filled])
        )
        
        return {
            'phase': phase,
            'position_in_range': position_in_range,
            'volume_ratio': volume_ratio,
            'volatility': volatility,
            'active_order_blocks': len([ob for ob in order_blocks if not ob.broken]),
            'unfilled_fvgs': len([fvg for fvg in fvgs if not fvg.filled]),
            'order_blocks': order_blocks,
            'fvgs': fvgs
        }
    
    def _classify_phase(self, position: float, volume: float, volatility: float,
                       active_obs: int, unfilled_fvgs: int) -> str:
        """
        Classify market phase based on metrics
        
        Accumulation: Low volatility, consolidation, building positions
        Manipulation: Sudden moves, stop hunts, liquidity grabs
        Distribution: High at top, volume spikes, reversals
        """
        # Accumulation characteristics
        if volatility < 0.005 and 0.3 < position < 0.7:
            if volume < 1.2:  # Normal to low volume
                return 'accumulation'
        
        # Manipulation characteristics
        if volume > 1.5 and active_obs > 2:
            if position < 0.3 or position > 0.7:
                return 'manipulation'
        
        # Distribution characteristics
        if position > 0.7 and volume > 1.3:
            if volatility > 0.008:
                return 'distribution'
        
        # Re-accumulation (mid-trend accumulation)
        if volatility < 0.006 and 0.4 < position < 0.6:
            return 'reaccumulation'
        
        # Default to trending
        return 'trending'
    
    def get_trading_bias(self, phase: str, order_blocks: List[OrderBlock],
                        current_price: float) -> Dict:
        """
        Get trading bias based on phase and order blocks
        
        Args:
            phase: Current market phase
            order_blocks: Active order blocks
            current_price: Current market price
        
        Returns:
            Trading bias and reasoning
        """
        if phase == 'accumulation':
            # Look for breakout direction based on OBs
            bullish_obs = [ob for ob in order_blocks if ob.ob_type == 'bullish' and not ob.broken]
            bearish_obs = [ob for ob in order_blocks if ob.ob_type == 'bearish' and not ob.broken]
            
            if len(bullish_obs) > len(bearish_obs):
                return {
                    'bias': 'bullish',
                    'confidence': 70,
                    'reason': 'Accumulation with more bullish order blocks - expect upward breakout'
                }
            elif len(bearish_obs) > len(bullish_obs):
                return {
                    'bias': 'bearish',
                    'confidence': 70,
                    'reason': 'Accumulation with more bearish order blocks - expect downward breakout'
                }
            else:
                return {
                    'bias': 'neutral',
                    'confidence': 50,
                    'reason': 'Accumulation phase - wait for breakout direction'
                }
        
        elif phase == 'manipulation':
            # During manipulation, expect reversal
            # Check which direction was just manipulated
            recent_obs = sorted(order_blocks, key=lambda x: x.start_time, reverse=True)[:3]
            
            if recent_obs:
                latest_ob = recent_obs[0]
                if latest_ob.ob_type == 'bearish' and latest_ob.tested:
                    return {
                        'bias': 'bullish',
                        'confidence': 80,
                        'reason': 'Liquidity grab below - expect reversal up'
                    }
                elif latest_ob.ob_type == 'bullish' and latest_ob.tested:
                    return {
                        'bias': 'bearish',
                        'confidence': 80,
                        'reason': 'Liquidity grab above - expect reversal down'
                    }
        
        elif phase == 'distribution':
            return {
                'bias': 'bearish',
                'confidence': 75,
                'reason': 'Distribution phase - smart money selling into strength'
            }
        
        elif phase == 'reaccumulation':
            # Continuation of trend
            bullish_obs = [ob for ob in order_blocks if ob.ob_type == 'bullish']
            if bullish_obs:
                return {
                    'bias': 'bullish',
                    'confidence': 75,
                    'reason': 'Re-accumulation in uptrend - expect continuation'
                }
        
        return {
            'bias': 'neutral',
            'confidence': 50,
            'reason': 'No clear phase bias'
        }


@dataclass
class PriceZone:
    """Represents a support or resistance zone"""
    zone_type: str
    price_low: float
    price_high: float
    strength: float
    touches: int
    first_touch: datetime
    last_touch: datetime
    active: bool = True
    
    @property
    def midpoint(self):
        return (self.price_low + self.price_high) / 2
    
    @property
    def width(self):
        return self.price_high - self.price_low


class ZoneMapper:
    """Detects and tracks support/resistance zones"""
    
    def __init__(self, zone_width_pct: float = 0.5, min_touches: int = 2):
        self.zone_width_pct = zone_width_pct
        self.min_touches = min_touches
        self.zones: List[PriceZone] = []
    
    def detect_zones(self, df: pd.DataFrame, lookback: int = 100) -> List[PriceZone]:
        """Detect support and resistance zones from price data"""
        if df.empty or len(df) < 20:
            return []
        
        df = df.copy()
        close_col = 'close' if 'close' in df.columns else 'Close'
        high_col = 'high' if 'high' in df.columns else 'High'
        low_col = 'low' if 'low' in df.columns else 'Low'
        
        if lookback > len(df):
            lookback = len(df)
        
        recent_df = df.iloc[-lookback:].copy()
        self.zones = []
        
        resistance_zones = self._find_resistance_zones(recent_df, high_col, close_col)
        support_zones = self._find_support_zones(recent_df, low_col, close_col)
        
        self.zones.extend(resistance_zones)
        self.zones.extend(support_zones)
        
        self._merge_overlapping_zones()
        self._calculate_zone_strength(recent_df, close_col, high_col, low_col)
        
        self.zones.sort(key=lambda z: z.strength, reverse=True)
        return self.zones
    
    def _find_resistance_zones(self, df: pd.DataFrame, high_col: str, close_col: str) -> List[PriceZone]:
        """Find resistance zones from swing highs"""
        zones = []
        swing_highs = self._find_swing_points(df[high_col].values, mode='high')
        
        for idx in swing_highs:
            if idx < 0 or idx >= len(df):
                continue
            
            price = df[high_col].iloc[idx]
            zone_width = price * (self.zone_width_pct / 100)
            
            zone = PriceZone(
                zone_type='resistance',
                price_low=price - zone_width / 2,
                price_high=price + zone_width / 2,
                strength=1.0,
                touches=1,
                first_touch=df.index[idx],
                last_touch=df.index[idx]
            )
            zones.append(zone)
        
        return zones
    
    def _find_support_zones(self, df: pd.DataFrame, low_col: str, close_col: str) -> List[PriceZone]:
        """Find support zones from swing lows"""
        zones = []
        swing_lows = self._find_swing_points(df[low_col].values, mode='low')
        
        for idx in swing_lows:
            if idx < 0 or idx >= len(df):
                continue
            
            price = df[low_col].iloc[idx]
            zone_width = price * (self.zone_width_pct / 100)
            
            zone = PriceZone(
                zone_type='support',
                price_low=price - zone_width / 2,
                price_high=price + zone_width / 2,
                strength=1.0,
                touches=1,
                first_touch=df.index[idx],
                last_touch=df.index[idx]
            )
            zones.append(zone)
        
        return zones
    
    def _find_swing_points(self, prices: np.ndarray, mode: str = 'high', window: int = 5) -> List[int]:
        """Find swing highs or lows"""
        swings = []
        
        for i in range(window, len(prices) - window):
            if mode == 'high':
                if prices[i] == max(prices[i-window:i+window+1]):
                    swings.append(i)
            else:
                if prices[i] == min(prices[i-window:i+window+1]):
                    swings.append(i)
        
        return swings
    
    def _merge_overlapping_zones(self):
        """Merge zones that overlap significantly"""
        if len(self.zones) < 2:
            return
        
        merged = []
        self.zones.sort(key=lambda z: z.price_low)
        
        i = 0
        while i < len(self.zones):
            current = self.zones[i]
            j = i + 1
            
            while j < len(self.zones):
                next_zone = self.zones[j]
                
                if (current.zone_type == next_zone.zone_type and 
                    self._zones_overlap(current, next_zone)):
                    current = self._merge_two_zones(current, next_zone)
                    j += 1
                else:
                    break
            
            merged.append(current)
            i = j if j > i + 1 else i + 1
        
        self.zones = merged
    
    def _zones_overlap(self, zone1: PriceZone, zone2: PriceZone, threshold: float = 0.5) -> bool:
        """Check if two zones overlap"""
        overlap_low = max(zone1.price_low, zone2.price_low)
        overlap_high = min(zone1.price_high, zone2.price_high)
        
        if overlap_high <= overlap_low:
            return False
        
        overlap = overlap_high - overlap_low
        min_width = min(zone1.width, zone2.width)
        
        return overlap / min_width >= threshold
    
    def _merge_two_zones(self, zone1: PriceZone, zone2: PriceZone) -> PriceZone:
        """Merge two overlapping zones"""
        return PriceZone(
            zone_type=zone1.zone_type,
            price_low=min(zone1.price_low, zone2.price_low),
            price_high=max(zone1.price_high, zone2.price_high),
            strength=(zone1.strength + zone2.strength) / 2,
            touches=zone1.touches + zone2.touches,
            first_touch=min(zone1.first_touch, zone2.first_touch),
            last_touch=max(zone1.last_touch, zone2.last_touch)
        )
    
    def _calculate_zone_strength(self, df: pd.DataFrame, close_col: str, 
                                 high_col: str, low_col: str):
        """Calculate strength of each zone based on touches and bounces"""
        for zone in self.zones:
            touches = 0
            bounces = 0
            
            for i in range(len(df)):
                high = df[high_col].iloc[i]
                low = df[low_col].iloc[i]
                
                if self._price_in_zone(high, zone) or self._price_in_zone(low, zone):
                    touches += 1
                    
                    if i < len(df) - 1:
                        next_close = df[close_col].iloc[i + 1]
                        
                        if zone.zone_type == 'support' and next_close > zone.price_high:
                            bounces += 1
                        elif zone.zone_type == 'resistance' and next_close < zone.price_low:
                            bounces += 1
            
            zone.touches = max(touches, 1)
            
            age_factor = (df.index[-1] - zone.last_touch).total_seconds() / 86400
            age_penalty = 1.0 / (1.0 + age_factor / 30)
            
            zone.strength = (touches * 0.4 + bounces * 0.6) * age_penalty
    
    def _price_in_zone(self, price: float, zone: PriceZone) -> bool:
        """Check if price is within zone"""
        return zone.price_low <= price <= zone.price_high
    
    def get_current_zones(self, current_price: float, 
                         max_distance_pct: float = 5.0) -> List[PriceZone]:
        """Get zones near current price"""
        nearby_zones = []
        max_distance = current_price * (max_distance_pct / 100)
        
        for zone in self.zones:
            if not zone.active:
                continue
            
            distance = min(
                abs(current_price - zone.price_low),
                abs(current_price - zone.price_high)
            )
            
            if distance <= max_distance:
                nearby_zones.append(zone)
        
        nearby_zones.sort(key=lambda z: abs(current_price - z.midpoint))
        return nearby_zones
