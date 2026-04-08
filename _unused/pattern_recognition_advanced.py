"""
Advanced Context-Aware Candlestick Pattern Recognition
Patterns are only valid when aligned with trend, regime, and key levels
"""

import numpy as np
import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class PatternType(Enum):
    # Single candle patterns
    HAMMER = "HAMMER"
    HANGING_MAN = "HANGING_MAN"
    SHOOTING_STAR = "SHOOTING_STAR"
    DOJI = "DOJI"
    DRAGONFLY_DOJI = "DRAGONFLY_DOJI"
    GRAVESTONE_DOJI = "GRAVESTONE_DOJI"
    
    # Double candle patterns
    BULLISH_ENGULFING = "BULLISH_ENGULFING"
    BEARISH_ENGULFING = "BEARISH_ENGULFING"
    TWEEZER_TOP = "TWEEZER_TOP"
    TWEEZER_BOTTOM = "TWEEZER_BOTTOM"
    
    # Triple candle patterns
    MORNING_STAR = "MORNING_STAR"
    EVENING_STAR = "EVENING_STAR"
    THREE_WHITE_SOLDIERS = "THREE_WHITE_SOLDIERS"
    THREE_BLACK_CROWS = "THREE_BLACK_CROWS"
    
    # Continuation patterns
    INSIDE_BAR = "INSIDE_BAR"
    OUTSIDE_BAR = "OUTSIDE_BAR"
    
    # Reversal patterns
    PIERCING_PATTERN = "PIERCING_PATTERN"
    DARK_CLOUD_COVER = "DARK_CLOUD_COVER"


@dataclass
class PatternSignal:
    pattern_type: PatternType
    direction: str  # BULLISH or BEARISH
    reliability: float  # 0-1
    context_score: float  # 0-1
    at_key_level: bool
    trend_aligned: bool
    volume_confirmed: bool
    suggested_entry: float
    suggested_sl: float
    suggested_tp: float


class AdvancedPatternRecognition:
    """
    Professional pattern recognition with context validation
    """
    
    def __init__(self):
        self.min_reliability = 0.6
        
    def detect_patterns(
        self,
        symbol: str,
        timeframe: int,
        lookback: int = 50
    ) -> List[PatternSignal]:
        """
        Detect all valid patterns with context
        """
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is None or len(rates) < 10:
            return []
        
        patterns = []
        
        # Get context for validation
        context = self._get_market_context(rates)
        
        # Detect single candle patterns
        patterns.extend(self._detect_single_candle_patterns(rates, context))
        
        # Detect double candle patterns
        patterns.extend(self._detect_double_candle_patterns(rates, context))
        
        # Detect triple candle patterns
        patterns.extend(self._detect_triple_candle_patterns(rates, context))
        
        # Candlestick Bible patterns (Marubozu, Harami, Three Inside, Abandoned Baby, etc.)
        patterns.extend(self._detect_candlestick_bible_patterns(rates, context))
        
        # Filter by reliability
        valid_patterns = [p for p in patterns if p.reliability >= self.min_reliability]
        
        return valid_patterns
    
    def _get_market_context(self, rates) -> Dict:
        """
        Analyze market context for pattern validation
        """
        high = rates['high']
        low = rates['low']
        close = rates['close']
        volume = rates['tick_volume']
        
        # Trend
        ema_20 = self._ema(close, 20)
        ema_50 = self._ema(close, 50)
        trend = "BULLISH" if ema_20[-1] > ema_50[-1] else "BEARISH"
        
        # Key levels
        swing_high = np.max(high[-30:])
        swing_low = np.min(low[-30:])
        
        # Volatility
        atr = self._calculate_atr(high, low, close)
        avg_atr = np.mean(atr[-20:])
        
        # Volume
        avg_volume = np.mean(volume[-20:])
        
        return {
            'trend': trend,
            'ema_20': ema_20,
            'ema_50': ema_50,
            'swing_high': swing_high,
            'swing_low': swing_low,
            'atr': atr[-1],
            'avg_atr': avg_atr,
            'avg_volume': avg_volume,
            'current_price': close[-1]
        }
    
    def _detect_single_candle_patterns(self, rates, context) -> List[PatternSignal]:
        """
        Detect single candle patterns
        """
        if len(rates) < 2:
            return []
        
        patterns = []
        last = rates[-1]
        prev = rates[-2]
        
        o = last['open']
        h = last['high']
        l = last['low']
        c = last['close']
        
        body = abs(c - o)
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        total_range = h - l
        
        if total_range < context['avg_atr'] * 0.3:
            return patterns  # Too small
        
        # HAMMER (Bullish at support)
        if (lower_wick > body * 2 and
            upper_wick < body * 0.3 and
            self._is_at_support(c, context)):
            
            reliability, ctx_score = self._validate_pattern(
                "BULLISH",
                context,
                at_support=True
            )
            
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.HAMMER,
                    "BULLISH",
                    reliability,
                    ctx_score,
                    context,
                    last
                ))
        
        # SHOOTING STAR (Bearish at resistance)
        if (upper_wick > body * 2 and
            lower_wick < body * 0.3 and
            self._is_at_resistance(c, context)):
            
            reliability, ctx_score = self._validate_pattern(
                "BEARISH",
                context,
                at_resistance=True
            )
            
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.SHOOTING_STAR,
                    "BEARISH",
                    reliability,
                    ctx_score,
                    context,
                    last
                ))
        
        # DOJI (Indecision at key levels)
        if body < total_range * 0.1:
            at_level = (self._is_at_support(c, context) or 
                       self._is_at_resistance(c, context))
            
            if at_level:
                # Direction depends on trend
                direction = "BEARISH" if context['trend'] == "BULLISH" else "BULLISH"
                reliability, ctx_score = self._validate_pattern(
                    direction,
                    context,
                    at_support=direction=="BULLISH",
                    at_resistance=direction=="BEARISH"
                )
                
                if reliability > 0:
                    patterns.append(self._create_signal(
                        PatternType.DOJI,
                        direction,
                        reliability * 0.8,  # Doji less reliable
                        ctx_score,
                        context,
                        last
                    ))
        
        return patterns
    
    def _detect_double_candle_patterns(self, rates, context) -> List[PatternSignal]:
        """
        Detect double candle patterns
        """
        if len(rates) < 3:
            return []
        
        patterns = []
        last = rates[-1]
        prev = rates[-2]
        
        prev_o = prev['open']
        prev_h = prev['high']
        prev_l = prev['low']
        prev_c = prev['close']
        
        curr_o = last['open']
        curr_h = last['high']
        curr_l = last['low']
        curr_c = last['close']
        
        prev_body = abs(prev_c - prev_o)
        curr_body = abs(curr_c - curr_o)
        
        # BULLISH ENGULFING
        if (prev_c < prev_o and  # Previous bearish
            curr_c > curr_o and  # Current bullish
            curr_o < prev_c and  # Opens below previous close
            curr_c > prev_o and  # Closes above previous open
            curr_body > prev_body * 1.2):  # Significant engulfing
            
            reliability, ctx_score = self._validate_pattern(
                "BULLISH",
                context,
                at_support=self._is_at_support(curr_c, context)
            )
            
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.BULLISH_ENGULFING,
                    "BULLISH",
                    reliability,
                    ctx_score,
                    context,
                    last
                ))
        
        # BEARISH ENGULFING
        if (prev_c > prev_o and  # Previous bullish
            curr_c < curr_o and  # Current bearish
            curr_o > prev_c and  # Opens above previous close
            curr_c < prev_o and  # Closes below previous open
            curr_body > prev_body * 1.2):
            
            reliability, ctx_score = self._validate_pattern(
                "BEARISH",
                context,
                at_resistance=self._is_at_resistance(curr_c, context)
            )
            
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.BEARISH_ENGULFING,
                    "BEARISH",
                    reliability,
                    ctx_score,
                    context,
                    last
                ))
        
        # TWEEZER TOP
        if (abs(prev_h - curr_h) / context['atr'] < 0.2 and
            prev_c > prev_o and
            curr_c < curr_o and
            self._is_at_resistance(curr_h, context)):
            
            reliability, ctx_score = self._validate_pattern(
                "BEARISH",
                context,
                at_resistance=True
            )
            
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.TWEEZER_TOP,
                    "BEARISH",
                    reliability,
                    ctx_score,
                    context,
                    last
                ))
        
        # TWEEZER BOTTOM
        if (abs(prev_l - curr_l) / context['atr'] < 0.2 and
            prev_c < prev_o and
            curr_c > curr_o and
            self._is_at_support(curr_l, context)):
            
            reliability, ctx_score = self._validate_pattern(
                "BULLISH",
                context,
                at_support=True
            )
            
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.TWEEZER_BOTTOM,
                    "BULLISH",
                    reliability,
                    ctx_score,
                    context,
                    last
                ))
        
        return patterns
    
    def _detect_triple_candle_patterns(self, rates, context) -> List[PatternSignal]:
        """
        Detect triple candle patterns
        """
        if len(rates) < 4:
            return []
        
        patterns = []
        c1 = rates[-3]
        c2 = rates[-2]
        c3 = rates[-1]
        
        # MORNING STAR (Bullish reversal)
        if (c1['close'] < c1['open'] and  # First bearish
            abs(c2['close'] - c2['open']) < (c1['high'] - c1['low']) * 0.3 and  # Small body
            c3['close'] > c3['open'] and  # Third bullish
            c3['close'] > (c1['open'] + c1['close']) / 2):  # Closes above midpoint
            
            reliability, ctx_score = self._validate_pattern(
                "BULLISH",
                context,
                at_support=self._is_at_support(c3['close'], context)
            )
            
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.MORNING_STAR,
                    "BULLISH",
                    reliability,
                    ctx_score,
                    context,
                    c3
                ))
        
        # EVENING STAR (Bearish reversal)
        if (c1['close'] > c1['open'] and  # First bullish
            abs(c2['close'] - c2['open']) < (c1['high'] - c1['low']) * 0.3 and  # Small body
            c3['close'] < c3['open'] and  # Third bearish
            c3['close'] < (c1['open'] + c1['close']) / 2):  # Closes below midpoint
            
            reliability, ctx_score = self._validate_pattern(
                "BEARISH",
                context,
                at_resistance=self._is_at_resistance(c3['close'], context)
            )
            
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.EVENING_STAR,
                    "BEARISH",
                    reliability,
                    ctx_score,
                    context,
                    c3
                ))
        
        # THREE WHITE SOLDIERS (Strong bullish)
        if (c1['close'] > c1['open'] and
            c2['close'] > c2['open'] and
            c3['close'] > c3['open'] and
            c2['close'] > c1['close'] and
            c3['close'] > c2['close']):
            
            reliability, ctx_score = self._validate_pattern(
                "BULLISH",
                context,
                at_support=False
            )
            
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.THREE_WHITE_SOLDIERS,
                    "BULLISH",
                    reliability * 0.9,
                    ctx_score,
                    context,
                    c3
                ))
        
        # THREE BLACK CROWS (Strong bearish)
        if (c1['close'] < c1['open'] and
            c2['close'] < c2['open'] and
            c3['close'] < c3['open'] and
            c2['close'] < c1['close'] and
            c3['close'] < c2['close']):
            
            reliability, ctx_score = self._validate_pattern(
                "BEARISH",
                context,
                at_resistance=False
            )
            
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.THREE_BLACK_CROWS,
                    "BEARISH",
                    reliability * 0.9,
                    ctx_score,
                    context,
                    c3
                ))
        
        return patterns
    
    def _validate_pattern(
        self,
        direction: str,
        context: Dict,
        at_support: bool = False,
        at_resistance: bool = False
    ) -> Tuple[float, float]:
        """
        Validate pattern based on context
        Returns (reliability, context_score)
        """
        reliability = 0.5
        context_score = 0.0
        
        # Trend alignment (most important)
        if direction == "BULLISH" and context['trend'] == "BULLISH":
            reliability += 0.25
            context_score += 0.4
        elif direction == "BEARISH" and context['trend'] == "BEARISH":
            reliability += 0.25
            context_score += 0.4
        
        # Key level proximity (very important)
        if at_support and direction == "BULLISH":
            reliability += 0.2
            context_score += 0.3
        elif at_resistance and direction == "BEARISH":
            reliability += 0.2
            context_score += 0.3
        
        # EMA proximity
        if direction == "BULLISH" and context['current_price'] < context['ema_20'][-1]:
            reliability += 0.1
            context_score += 0.15
        elif direction == "BEARISH" and context['current_price'] > context['ema_20'][-1]:
            reliability += 0.1
            context_score += 0.15
        
        return min(reliability, 1.0), min(context_score, 1.0)
    
    def _is_at_support(self, price: float, context: Dict) -> bool:
        """Check if price is near support"""
        swing_low = context['swing_low']
        tolerance = context['atr'] * 0.5
        
        return abs(price - swing_low) <= tolerance
    
    def _is_at_resistance(self, price: float, context: Dict) -> bool:
        """Check if price is near resistance"""
        swing_high = context['swing_high']
        tolerance = context['atr'] * 0.5
        
        return abs(price - swing_high) <= tolerance
    
    def _create_signal(
        self,
        pattern_type: PatternType,
        direction: str,
        reliability: float,
        context_score: float,
        context: Dict,
        candle
    ) -> PatternSignal:
        """
        Create pattern signal with entry/exit levels
        """
        atr = context['atr']
        current_price = candle['close']
        
        # Calculate entry, SL, TP
        if direction == "BULLISH":
            entry = current_price
            sl = candle['low'] - (atr * 0.5)
            tp = current_price + (atr * 3)
        else:
            entry = current_price
            sl = candle['high'] + (atr * 0.5)
            tp = current_price - (atr * 3)
        
        return PatternSignal(
            pattern_type=pattern_type,
            direction=direction,
            reliability=reliability,
            context_score=context_score,
            at_key_level=self._is_at_support(current_price, context) or 
                         self._is_at_resistance(current_price, context),
            trend_aligned=(direction == context['trend']),
            volume_confirmed=candle['tick_volume'] > context['avg_volume'],
            suggested_entry=entry,
            suggested_sl=sl,
            suggested_tp=tp
        )
    
    def _detect_candlestick_bible_patterns(self, rates, context) -> List[PatternSignal]:
        """
        Additional patterns from 'The Candlestick Bible' for improved accuracy.
        Includes: Marubozu, Harami, Three Inside Up/Down, Abandoned Baby,
        Spinning Top, Inverted Hammer.
        """
        patterns = []
        if len(rates) < 4:
            return patterns
        
        last = rates[-1]
        prev = rates[-2]
        c1 = rates[-3]
        
        o, h, l, c = last['open'], last['high'], last['low'], last['close']
        body = abs(c - o)
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - l
        total_range = max(h - l, 1e-10)
        atr = context['atr']
        
        prev_o, prev_c = prev['open'], prev['close']
        prev_body = abs(prev_c - prev_o)
        
        # ── MARUBOZU (Strong conviction candle - minimal wicks) ──
        if body > total_range * 0.85 and body >= atr * 0.5:
            direction = "BULLISH" if c > o else "BEARISH"
            reliability, ctx_score = self._validate_pattern(
                direction, context,
                at_support=(direction == "BULLISH" and self._is_at_support(c, context)),
                at_resistance=(direction == "BEARISH" and self._is_at_resistance(c, context))
            )
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.OUTSIDE_BAR, direction,
                    reliability * 1.1, ctx_score, context, last
                ))
        
        # ── INVERTED HAMMER (Bullish reversal at support) ──
        if (upper_wick > body * 2 and
            lower_wick < body * 0.3 and
            c <= o and  # Small bearish or neutral body
            self._is_at_support(c, context)):
            reliability, ctx_score = self._validate_pattern(
                "BULLISH", context, at_support=True
            )
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.HAMMER, "BULLISH",
                    reliability * 0.85, ctx_score, context, last
                ))
        
        # ── SPINNING TOP (Indecision - small body, long wicks both sides) ──
        if (body < total_range * 0.25 and
            upper_wick > body and lower_wick > body and
            total_range >= atr * 0.4):
            at_level = (self._is_at_support(c, context) or
                       self._is_at_resistance(c, context))
            if at_level:
                direction = "BEARISH" if context['trend'] == "BULLISH" else "BULLISH"
                reliability, ctx_score = self._validate_pattern(
                    direction, context,
                    at_support=(direction == "BULLISH"),
                    at_resistance=(direction == "BEARISH")
                )
                if reliability > 0:
                    patterns.append(self._create_signal(
                        PatternType.DOJI, direction,
                        reliability * 0.7, ctx_score, context, last
                    ))
        
        # ── BULLISH HARAMI (Small bullish inside previous bearish) ──
        if (prev_c < prev_o and  # Previous bearish
            c > o and           # Current bullish
            o >= prev_c and c <= prev_o and  # Body inside previous
            body < prev_body * 0.6):
            reliability, ctx_score = self._validate_pattern(
                "BULLISH", context,
                at_support=self._is_at_support(c, context)
            )
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.INSIDE_BAR, "BULLISH",
                    reliability * 0.85, ctx_score, context, last
                ))
        
        # ── BEARISH HARAMI (Small bearish inside previous bullish) ──
        if (prev_c > prev_o and  # Previous bullish
            c < o and           # Current bearish
            o <= prev_c and c >= prev_o and  # Body inside previous
            body < prev_body * 0.6):
            reliability, ctx_score = self._validate_pattern(
                "BEARISH", context,
                at_resistance=self._is_at_resistance(c, context)
            )
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.INSIDE_BAR, "BEARISH",
                    reliability * 0.85, ctx_score, context, last
                ))
        
        # ── THREE INSIDE UP (Harami + confirmation) ──
        c1_o, c1_c = c1['open'], c1['close']
        if (c1_c < c1_o and              # First: bearish
            prev_c > prev_o and           # Second: bullish (inside first)
            prev_o >= c1_c and prev_c <= c1_o and  # Harami pattern
            c > o and c > prev_c):        # Third: bullish confirmation above
            reliability, ctx_score = self._validate_pattern(
                "BULLISH", context,
                at_support=self._is_at_support(c, context)
            )
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.MORNING_STAR, "BULLISH",
                    reliability * 1.1, ctx_score, context, last
                ))
        
        # ── THREE INSIDE DOWN (Bearish harami + confirmation) ──
        if (c1_c > c1_o and              # First: bullish
            prev_c < prev_o and           # Second: bearish (inside first)
            prev_o <= c1_c and prev_c >= c1_o and  # Harami pattern
            c < o and c < prev_c):        # Third: bearish confirmation below
            reliability, ctx_score = self._validate_pattern(
                "BEARISH", context,
                at_resistance=self._is_at_resistance(c, context)
            )
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.EVENING_STAR, "BEARISH",
                    reliability * 1.1, ctx_score, context, last
                ))
        
        # ── ABANDONED BABY BULLISH (Gap down doji + gap up) ──
        prev_range = max(prev['high'] - prev['low'], 1e-10)
        prev_is_doji = abs(prev_c - prev_o) < prev_range * 0.1
        if (c1_c < c1_o and                     # First: bearish
            prev_is_doji and                     # Second: doji
            prev['high'] < c1['low'] and         # Gap down from first
            l > prev['high'] and                 # Gap up from doji
            c > o):                              # Third: bullish
            reliability, ctx_score = self._validate_pattern(
                "BULLISH", context, at_support=True
            )
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.MORNING_STAR, "BULLISH",
                    min(reliability * 1.3, 1.0), ctx_score, context, last
                ))
        
        # ── ABANDONED BABY BEARISH (Gap up doji + gap down) ──
        if (c1_c > c1_o and                     # First: bullish
            prev_is_doji and                     # Second: doji
            prev['low'] > c1['high'] and         # Gap up from first
            h < prev['low'] and                  # Gap down from doji
            c < o):                              # Third: bearish
            reliability, ctx_score = self._validate_pattern(
                "BEARISH", context, at_resistance=True
            )
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.EVENING_STAR, "BEARISH",
                    min(reliability * 1.3, 1.0), ctx_score, context, last
                ))
        
        # ── PIERCING PATTERN (Bullish reversal) ──
        if (prev_c < prev_o and            # Previous: bearish
            c > o and                       # Current: bullish
            o < prev['low'] and             # Opens below previous low
            c > (prev_o + prev_c) / 2 and   # Closes above midpoint
            c < prev_o):                    # But doesn't fully engulf
            reliability, ctx_score = self._validate_pattern(
                "BULLISH", context,
                at_support=self._is_at_support(c, context)
            )
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.PIERCING_PATTERN, "BULLISH",
                    reliability, ctx_score, context, last
                ))
        
        # ── DARK CLOUD COVER (Bearish reversal) ──
        if (prev_c > prev_o and            # Previous: bullish
            c < o and                       # Current: bearish
            o > prev['high'] and            # Opens above previous high
            c < (prev_o + prev_c) / 2 and   # Closes below midpoint
            c > prev_o):                    # But doesn't fully engulf
            reliability, ctx_score = self._validate_pattern(
                "BEARISH", context,
                at_resistance=self._is_at_resistance(c, context)
            )
            if reliability > 0:
                patterns.append(self._create_signal(
                    PatternType.DARK_CLOUD_COVER, "BEARISH",
                    reliability, ctx_score, context, last
                ))
        
        return patterns
    
    # Utility functions
    
    def _ema(self, data, period):
        """Calculate EMA"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def _calculate_atr(self, high, low, close):
        """Calculate ATR"""
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        
        return self._ema(tr, 14)
