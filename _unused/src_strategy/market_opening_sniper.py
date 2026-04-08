"""
Market Opening Sniper Entry System
Perfect entry timing after market opens (London/NY sessions)
Waits for initial volatility to settle before precision entries
Includes session filtering for optimal trading times
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
from datetime import datetime, time
from dataclasses import dataclass
import pytz


@dataclass
class SniperEntry:
    """Sniper entry signal"""
    entry_type: str  # 'BUY' or 'SELL'
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    reason: str
    session: str
    minutes_after_open: int


class MarketOpeningSniperStrategy:
    """
    Sniper entry strategy for market openings
    
    Concept:
    1. Wait for first 15-30 minutes after market open (volatility spike)
    2. Identify institutional move direction
    3. Wait for pullback to key level
    4. Enter with precision when confirmation appears
    """
    
    def __init__(self):
        self.session_times = {
            'london': {'open': time(7, 0), 'end': time(8, 30)},
            'newyork': {'open': time(13, 0), 'end': time(14, 30)},
            'tokyo': {'open': time(0, 0), 'end': time(1, 30)}
        }
        
        self.wait_minutes = 15  # Wait after open
        self.entry_window_minutes = 90  # Window to find entry
    
    def detect_session_open(self, current_time: datetime) -> Optional[str]:
        """
        Detect which major session just opened
        
        Args:
            current_time: Current time
        
        Returns:
            Session name or None
        """
        current_time_only = current_time.time()
        
        for session, times in self.session_times.items():
            # Check if within first few minutes of session
            if times['open'] <= current_time_only < times['end']:
                return session
        
        return None
    
    def analyze_opening_move(self, df: pd.DataFrame, session_open_time: datetime) -> Dict:
        """
        Analyze the initial move after market open
        
        Args:
            df: DataFrame with OHLCV data
            session_open_time: Time when session opened
        
        Returns:
            Analysis of opening move
        """
        # Get candles from session open
        session_df = df[df.index >= session_open_time].head(30)  # First 30 minutes
        
        if len(session_df) < 15:
            return {'status': 'insufficient_data'}
        
        # First 15 minutes (initial volatility)
        initial_df = session_df.head(15)
        
        # Calculate opening range
        opening_high = initial_df['high'].max()
        opening_low = initial_df['low'].min()
        opening_range = opening_high - opening_low
        opening_midpoint = (opening_high + opening_low) / 2
        
        # Determine initial direction
        open_price = initial_df.iloc[0]['open']
        price_after_15min = initial_df.iloc[-1]['close']
        
        initial_direction = 'bullish' if price_after_15min > open_price else 'bearish'
        initial_move_pips = abs(price_after_15min - open_price) * 10000
        
        # Calculate volatility
        atr = initial_df['high'] - initial_df['low']
        avg_atr = atr.mean()
        volatility_ratio = (opening_range / avg_atr) if avg_atr > 0 else 1.0
        
        # Volume analysis
        avg_volume = initial_df['tick_volume'].mean()
        peak_volume = initial_df['tick_volume'].max()
        volume_surge = peak_volume / avg_volume if avg_volume > 0 else 1.0
        
        # Determine if move is impulsive or corrective
        move_strength = self._classify_move_strength(
            initial_move_pips, volatility_ratio, volume_surge
        )
        
        return {
            'status': 'analyzed',
            'direction': initial_direction,
            'opening_high': opening_high,
            'opening_low': opening_low,
            'opening_midpoint': opening_midpoint,
            'opening_range_pips': opening_range * 10000,
            'move_pips': initial_move_pips,
            'volatility_ratio': volatility_ratio,
            'volume_surge': volume_surge,
            'move_strength': move_strength,
            'atr': avg_atr
        }
    
    def _classify_move_strength(self, move_pips: float, volatility: float, volume: float) -> str:
        """
        Classify strength of opening move
        
        Returns:
            'strong_impulsive', 'moderate', 'weak', 'choppy'
        """
        # Strong impulsive move
        if move_pips > 30 and volatility > 1.5 and volume > 1.5:
            return 'strong_impulsive'
        
        # Moderate move
        if move_pips > 15 and volatility > 1.0 and volume > 1.0:
            return 'moderate'
        
        # Choppy (no clear direction)
        if volatility > 2.0 and move_pips < 10:
            return 'choppy'
        
        # Weak
        return 'weak'
    
    def find_sniper_entry(self, df: pd.DataFrame, opening_analysis: Dict,
                         current_price: float, order_blocks: list = None) -> Optional[SniperEntry]:
        """
        Find precision entry after opening move analysis
        
        Strategy:
        1. If strong impulsive move up → Wait for pullback to opening high
        2. If strong impulsive move down → Wait for pullback to opening low
        3. Look for confirmation (order block, FVG, or candlestick pattern)
        4. Enter with tight stop
        
        Args:
            df: Current market data
            opening_analysis: Analysis from analyze_opening_move
            current_price: Current market price
            order_blocks: Optional order blocks for confluence
        
        Returns:
            SniperEntry or None
        """
        if opening_analysis.get('status') != 'analyzed':
            return None
        
        direction = opening_analysis['direction']
        move_strength = opening_analysis['move_strength']
        opening_high = opening_analysis['opening_high']
        opening_low = opening_analysis['opening_low']
        opening_mid = opening_analysis['opening_midpoint']
        atr = opening_analysis['atr']
        
        # Only trade strong or moderate moves
        if move_strength in ['weak', 'choppy']:
            return None
        
        # Get recent candles for pattern analysis
        recent = df.tail(10)
        if len(recent) < 5:
            return None
        
        last_candle = recent.iloc[-1]
        prev_candle = recent.iloc[-2]
        
        # === BULLISH ENTRY LOGIC ===
        if direction == 'bullish' and move_strength == 'strong_impulsive':
            # Wait for pullback to opening high or midpoint
            if self._is_near_level(current_price, opening_high, atr, 0.5):
                # Check for bullish confirmation
                if self._is_bullish_reversal_pattern(recent):
                    # Check order block confluence
                    ob_confluence = self._check_order_block_confluence(
                        current_price, order_blocks, 'bullish'
                    ) if order_blocks else False
                    
                    confidence = 75 if ob_confluence else 65
                    
                    return SniperEntry(
                        entry_type='BUY',
                        entry_price=current_price,
                        stop_loss=opening_mid - (atr * 0.5),
                        take_profit=current_price + (atr * 2.5),
                        confidence=confidence,
                        reason=f"Pullback to opening high after {move_strength} move, bullish reversal pattern",
                        session=opening_analysis.get('session', 'unknown'),
                        minutes_after_open=30
                    )
            
            # Alternative: pullback to midpoint (50% retracement)
            elif self._is_near_level(current_price, opening_mid, atr, 0.3):
                if self._is_bullish_reversal_pattern(recent):
                    return SniperEntry(
                        entry_type='BUY',
                        entry_price=current_price,
                        stop_loss=opening_low - (atr * 0.3),
                        take_profit=current_price + (atr * 3.0),
                        confidence=80,
                        reason=f"50% pullback after {move_strength} move, optimal entry",
                        session=opening_analysis.get('session', 'unknown'),
                        minutes_after_open=30
                    )
        
        # === BEARISH ENTRY LOGIC ===
        elif direction == 'bearish' and move_strength == 'strong_impulsive':
            # Wait for pullback to opening low or midpoint
            if self._is_near_level(current_price, opening_low, atr, 0.5):
                if self._is_bearish_reversal_pattern(recent):
                    ob_confluence = self._check_order_block_confluence(
                        current_price, order_blocks, 'bearish'
                    ) if order_blocks else False
                    
                    confidence = 75 if ob_confluence else 65
                    
                    return SniperEntry(
                        entry_type='SELL',
                        entry_price=current_price,
                        stop_loss=opening_mid + (atr * 0.5),
                        take_profit=current_price - (atr * 2.5),
                        confidence=confidence,
                        reason=f"Pullback to opening low after {move_strength} move, bearish reversal pattern",
                        session=opening_analysis.get('session', 'unknown'),
                        minutes_after_open=30
                    )
            
            elif self._is_near_level(current_price, opening_mid, atr, 0.3):
                if self._is_bearish_reversal_pattern(recent):
                    return SniperEntry(
                        entry_type='SELL',
                        entry_price=current_price,
                        stop_loss=opening_high + (atr * 0.3),
                        take_profit=current_price - (atr * 3.0),
                        confidence=80,
                        reason=f"50% pullback after {move_strength} move, optimal entry",
                        session=opening_analysis.get('session', 'unknown'),
                        minutes_after_open=30
                    )
        
        return None
    
    def _is_near_level(self, current_price: float, level: float, atr: float, multiplier: float) -> bool:
        """Check if current price is near a key level"""
        distance = abs(current_price - level)
        threshold = atr * multiplier
        return distance <= threshold
    
    def _is_bullish_reversal_pattern(self, recent: pd.DataFrame) -> bool:
        """
        Check for bullish reversal candlestick patterns
        - Hammer
        - Bullish engulfing
        - Morning star
        """
        if len(recent) < 2:
            return False
        
        last = recent.iloc[-1]
        prev = recent.iloc[-2]
        
        # Hammer pattern
        body = abs(last['close'] - last['open'])
        lower_wick = min(last['close'], last['open']) - last['low']
        upper_wick = last['high'] - max(last['close'], last['open'])
        
        if lower_wick > body * 2 and upper_wick < body * 0.5 and last['close'] > last['open']:
            return True
        
        # Bullish engulfing
        if prev['close'] < prev['open'] and last['close'] > last['open']:
            if last['close'] > prev['open'] and last['open'] < prev['close']:
                return True
        
        return False
    
    def _is_bearish_reversal_pattern(self, recent: pd.DataFrame) -> bool:
        """
        Check for bearish reversal candlestick patterns
        - Shooting star
        - Bearish engulfing
        - Evening star
        """
        if len(recent) < 2:
            return False
        
        last = recent.iloc[-1]
        prev = recent.iloc[-2]
        
        # Shooting star
        body = abs(last['close'] - last['open'])
        upper_wick = last['high'] - max(last['close'], last['open'])
        lower_wick = min(last['close'], last['open']) - last['low']
        
        if upper_wick > body * 2 and lower_wick < body * 0.5 and last['close'] < last['open']:
            return True
        
        # Bearish engulfing
        if prev['close'] > prev['open'] and last['close'] < last['open']:
            if last['close'] < prev['open'] and last['open'] > prev['close']:
                return True
        
        return False
    
    def _check_order_block_confluence(self, current_price: float, 
                                     order_blocks: list, direction: str) -> bool:
        """Check if there's an order block at current level"""
        if not order_blocks:
            return False
        
        tolerance = 0.0005  # 5 pips
        
        for ob in order_blocks:
            if ob.ob_type == direction and not ob.broken:
                if direction == 'bullish':
                    if abs(current_price - ob.high) <= tolerance:
                        return True
                else:
                    if abs(current_price - ob.low) <= tolerance:
                        return True
        
        return False
    
    def get_session_analysis(self, df: pd.DataFrame, current_time: datetime) -> Dict:
        """
        Complete session analysis for sniper entries
        
        Args:
            df: Market data
            current_time: Current time
        
        Returns:
            Complete analysis including entry signal if available
        """
        # Detect session
        session = self.detect_session_open(current_time)
        
        if not session:
            return {
                'status': 'no_active_session',
                'message': 'Not in entry window for any major session'
            }
        
        # Find session open time
        session_open = current_time.replace(
            hour=self.session_times[session]['open'].hour,
            minute=self.session_times[session]['open'].minute,
            second=0
        )
        
        # Check if we're past the wait period
        minutes_since_open = (current_time - session_open).total_seconds() / 60
        
        if minutes_since_open < self.wait_minutes:
            return {
                'status': 'waiting',
                'session': session,
                'minutes_since_open': minutes_since_open,
                'message': f'Waiting for initial {self.wait_minutes} minutes to pass'
            }
        
        if minutes_since_open > self.entry_window_minutes:
            return {
                'status': 'window_closed',
                'session': session,
                'message': 'Entry window has closed for this session'
            }
        
        # Analyze opening move
        opening_analysis = self.analyze_opening_move(df, session_open)
        opening_analysis['session'] = session
        opening_analysis['minutes_since_open'] = minutes_since_open
        
        # Look for sniper entry
        current_price = df.iloc[-1]['close']
        sniper_entry = self.find_sniper_entry(df, opening_analysis, current_price)
        
        if sniper_entry:
            return {
                'status': 'entry_signal',
                'session': session,
                'opening_analysis': opening_analysis,
                'sniper_entry': sniper_entry
            }
        
        return {
            'status': 'monitoring',
            'session': session,
            'opening_analysis': opening_analysis,
            'message': 'Monitoring for precision entry opportunity'
        }


class SessionFilter:
    """
    Filter trades based on forex market sessions
    Best trading: London/NY overlap (12:00-16:00 GMT)
    """
    
    def __init__(self, session_start_gmt: time = time(12, 0), 
                 session_end_gmt: time = time(16, 0)):
        self.session_start = session_start_gmt
        self.session_end = session_end_gmt
        self.gmt_tz = pytz.timezone('GMT')
    
    def is_trading_session(self, timestamp: Optional[datetime] = None) -> bool:
        """Check if current time is within trading session"""
        if timestamp is None:
            timestamp = datetime.now(self.gmt_tz)
        elif timestamp.tzinfo is None:
            timestamp = self.gmt_tz.localize(timestamp)
        else:
            timestamp = timestamp.astimezone(self.gmt_tz)
        
        current_time = timestamp.time()
        return self.session_start <= current_time <= self.session_end
    
    def get_current_session(self, timestamp: Optional[datetime] = None) -> str:
        """Identify which forex session is currently active"""
        if timestamp is None:
            timestamp = datetime.now(self.gmt_tz)
        elif timestamp.tzinfo is None:
            timestamp = self.gmt_tz.localize(timestamp)
        else:
            timestamp = timestamp.astimezone(self.gmt_tz)
        
        current_time = timestamp.time()
        
        if time(12, 0) <= current_time <= time(16, 0):
            return 'OVERLAP'
        
        if time(7, 0) <= current_time < time(16, 0):
            return 'LONDON'
        
        if time(12, 0) <= current_time < time(20, 0):
            return 'NEW_YORK'
        
        if current_time >= time(23, 0) or current_time < time(8, 0):
            return 'ASIAN'
        
        return 'CLOSED'
    
    def should_trade(self, timestamp: Optional[datetime] = None,
                    allow_london: bool = True,
                    allow_ny: bool = True,
                    allow_asian: bool = False) -> Tuple[bool, str]:
        """Determine if trading should be allowed"""
        session = self.get_current_session(timestamp)
        
        if session == 'OVERLAP':
            return (True, "OVERLAP session - highest liquidity")
        
        if session == 'LONDON' and allow_london:
            return (True, "LONDON session - good trending")
        
        if session == 'NEW_YORK' and allow_ny:
            return (True, "NEW YORK session - good volatility")
        
        if session == 'ASIAN' and allow_asian:
            return (True, "ASIAN session - lower liquidity")
        
        if session == 'CLOSED':
            return (False, "Market closed or weekend")
        
        return (False, f"{session} session not enabled")
    
    def is_weekend(self, timestamp: Optional[datetime] = None) -> bool:
        """Check if it's weekend"""
        if timestamp is None:
            timestamp = datetime.now(self.gmt_tz)
        
        weekday = timestamp.weekday()
        current_time = timestamp.time()
        
        if weekday == 5:
            return True
        if weekday == 6 and current_time < time(22, 0):
            return True
        if weekday == 4 and current_time >= time(22, 0):
            return True
        
        return False


class LiquidityGrabDetector:
    """
    Detect liquidity grabs (stop hunts) at market open
    Often precedes strong moves in opposite direction
    """
    
    def __init__(self):
        self.recent_highs = []
        self.recent_lows = []
    
    def detect_liquidity_grab(self, df: pd.DataFrame) -> Optional[Dict]:
        """
        Detect if a liquidity grab just occurred
        
        Signs:
        1. Sharp spike through obvious level (previous high/low)
        2. Quick reversal (long wick)
        3. Volume spike
        
        Args:
            df: Market data
        
        Returns:
            Liquidity grab info or None
        """
        if len(df) < 20:
            return None
        
        recent = df.tail(20)
        last_candle = recent.iloc[-1]
        
        # Find recent swing highs/lows
        swing_high = recent['high'].nlargest(3).iloc[-1]
        swing_low = recent['low'].nsmallest(3).iloc[-1]
        
        # Check for upward liquidity grab (stop hunt above high)
        upper_wick = last_candle['high'] - max(last_candle['close'], last_candle['open'])
        body = abs(last_candle['close'] - last_candle['open'])
        
        if last_candle['high'] > swing_high:
            if upper_wick > body * 2:  # Long upper wick
                return {
                    'type': 'bullish_liquidity_grab',
                    'level': swing_high,
                    'current_price': last_candle['close'],
                    'bias': 'bearish',  # Expect reversal down
                    'confidence': 75,
                    'reason': 'Stop hunt above swing high with rejection'
                }
        
        # Check for downward liquidity grab (stop hunt below low)
        lower_wick = min(last_candle['close'], last_candle['open']) - last_candle['low']
        
        if last_candle['low'] < swing_low:
            if lower_wick > body * 2:  # Long lower wick
                return {
                    'type': 'bearish_liquidity_grab',
                    'level': swing_low,
                    'current_price': last_candle['close'],
                    'bias': 'bullish',  # Expect reversal up
                    'confidence': 75,
                    'reason': 'Stop hunt below swing low with rejection'
                }
        
        return None
