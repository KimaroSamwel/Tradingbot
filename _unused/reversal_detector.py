"""
8-Signal Reversal Detection System
Identifies market reversals before they fully develop
"""

import numpy as np
import MetaTrader5 as mt5
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ReversalSignal:
    signal_type: str  # BULLISH_REVERSAL or BEARISH_REVERSAL
    confidence: float  # 0-1
    signals_detected: List[str]
    trigger_price: float
    suggested_entry: float
    suggested_sl: float
    suggested_tp: float
    timeframe_confirmation: Dict


class ReversalDetector:
    """
    Professional reversal detection using 8 confirmation layers
    """
    
    def __init__(self):
        self.min_signals_required = 4
        self.min_confidence = 0.65
        
    def detect_reversal(
        self,
        symbol: str,
        timeframe: int,
        lookback: int = 100
    ) -> Optional[ReversalSignal]:
        """
        Comprehensive reversal detection
        """
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is None or len(rates) < lookback:
            return None
        
        high = rates['high']
        low = rates['low']
        close = rates['close']
        volume = rates['tick_volume']
        
        signals = []
        
        # Signal 1: Momentum Divergence
        if self._detect_momentum_divergence(high, low, close):
            signals.append("MOMENTUM_DIVERGENCE")
        
        # Signal 2: Volatility Compression
        if self._detect_volatility_compression(high, low, close):
            signals.append("VOLATILITY_COMPRESSION")
        
        # Signal 3: Failed Retest
        if self._detect_failed_retest(high, low, close):
            signals.append("FAILED_RETEST")
        
        # Signal 4: Multiple Timeframe Rejection
        mtf_rejection = self._detect_mtf_rejection(symbol, close[-1])
        if mtf_rejection['detected']:
            signals.append("MTF_REJECTION")
        
        # Signal 5: Volume Analysis
        if self._detect_volume_exhaustion(close, volume):
            signals.append("VOLUME_EXHAUSTION")
        
        # Signal 6: Sentiment Extreme
        if self._detect_sentiment_extreme(close):
            signals.append("SENTIMENT_EXTREME")
        
        # Signal 7: Structure Break
        structure_break = self._detect_structure_break(high, low, close)
        if structure_break['detected']:
            signals.append("STRUCTURE_BREAK")
        
        # Signal 8: Exhaustion Patterns
        if self._detect_exhaustion_pattern(rates):
            signals.append("EXHAUSTION_PATTERN")
        
        # Require minimum signals
        if len(signals) < self.min_signals_required:
            return None
        
        # Determine reversal direction and confidence
        direction, confidence = self._calculate_reversal_direction(
            high, low, close, signals
        )
        
        if confidence < self.min_confidence:
            return None
        
        # Calculate entry parameters
        entry, sl, tp = self._calculate_entry_params(
            direction, high, low, close, timeframe
        )
        
        return ReversalSignal(
            signal_type=direction,
            confidence=confidence,
            signals_detected=signals,
            trigger_price=close[-1],
            suggested_entry=entry,
            suggested_sl=sl,
            suggested_tp=tp,
            timeframe_confirmation=mtf_rejection
        )
    
    def _detect_momentum_divergence(self, high, low, close) -> bool:
        """
        Detect divergence between price and momentum (RSI/MACD)
        """
        # Calculate RSI
        rsi = self._calculate_rsi(close, 14)
        
        # Find recent peaks/troughs
        price_peaks = self._find_peaks(close[-20:])
        rsi_peaks = self._find_peaks(rsi[-20:])
        
        # Bearish divergence: Price making higher highs, RSI making lower highs
        if len(price_peaks) >= 2 and len(rsi_peaks) >= 2:
            if (close[price_peaks[-1]] > close[price_peaks[-2]] and
                rsi[rsi_peaks[-1]] < rsi[rsi_peaks[-2]]):
                return True
        
        # Bullish divergence: Price making lower lows, RSI making higher lows
        price_troughs = self._find_troughs(close[-20:])
        rsi_troughs = self._find_troughs(rsi[-20:])
        
        if len(price_troughs) >= 2 and len(rsi_troughs) >= 2:
            if (close[price_troughs[-1]] < close[price_troughs[-2]] and
                rsi[rsi_troughs[-1]] > rsi[rsi_troughs[-2]]):
                return True
        
        return False
    
    def _detect_volatility_compression(self, high, low, close) -> bool:
        """
        Bollinger Band squeeze or ATR compression before expansion
        """
        # Calculate ATR
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = self._ema(tr, 14)
        
        # Check if current ATR is significantly below average
        avg_atr = np.mean(atr[-50:-1])
        if atr[-1] < avg_atr * 0.7:
            # And showing signs of expansion
            if atr[-1] > atr[-3]:
                return True
        
        # Bollinger Band squeeze
        std_20 = np.std(close[-20:])
        avg_std = np.mean([np.std(close[i-20:i]) for i in range(30, 50)])
        
        if std_20 < avg_std * 0.6:
            return True
        
        return False
    
    def _detect_failed_retest(self, high, low, close) -> bool:
        """
        Price fails to reclaim a key level (kiss goodbye pattern)
        """
        # Find recent swing high/low
        swing_high = np.max(high[-30:-5])
        swing_low = np.min(low[-30:-5])
        
        # Check if price recently broke below support and failed to reclaim
        if close[-5] < swing_low and close[-1] < swing_low:
            # Attempted retest but failed
            if np.max(high[-5:]) > swing_low * 0.998:
                return True
        
        # Check if price recently broke above resistance and failed to hold
        if close[-5] > swing_high and close[-1] < swing_high:
            # Attempted retest but failed
            if np.min(low[-5:]) < swing_high * 1.002:
                return True
        
        return False
    
    def _detect_mtf_rejection(self, symbol: str, current_price: float) -> Dict:
        """
        Multiple timeframe showing rejection at same levels
        """
        timeframes = [mt5.TIMEFRAME_H1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_D1]
        rejections = 0
        
        for tf in timeframes:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, 5)
            if rates is None:
                continue
            
            # Check for rejection candles
            for i in range(len(rates)):
                body = abs(rates[i]['close'] - rates[i]['open'])
                upper_wick = rates[i]['high'] - max(rates[i]['close'], rates[i]['open'])
                lower_wick = min(rates[i]['close'], rates[i]['open']) - rates[i]['low']
                
                # Bearish rejection (long upper wick)
                if upper_wick > body * 2:
                    rejections += 1
                    break
                
                # Bullish rejection (long lower wick)
                if lower_wick > body * 2:
                    rejections += 1
                    break
        
        return {
            'detected': rejections >= 2,
            'rejection_count': rejections,
            'timeframes_aligned': rejections == 3
        }
    
    def _detect_volume_exhaustion(self, close, volume) -> bool:
        """
        High volume with minimal price change = exhaustion
        """
        recent_volume = volume[-5:]
        avg_volume = np.mean(volume[-50:-5])
        
        # Volume spike
        if np.max(recent_volume) > avg_volume * 1.5:
            # But price range is small
            price_range = (np.max(close[-5:]) - np.min(close[-5:])) / close[-5]
            avg_range = np.mean([
                (np.max(close[i-5:i]) - np.min(close[i-5:i])) / close[i-5]
                for i in range(10, 30)
            ])
            
            if price_range < avg_range * 0.7:
                return True
        
        return False
    
    def _detect_sentiment_extreme(self, close) -> bool:
        """
        Price at extreme relative to recent range
        """
        recent_high = np.max(close[-50:])
        recent_low = np.min(close[-50:])
        current = close[-1]
        
        # At top 5% of range
        if current > recent_low + (recent_high - recent_low) * 0.95:
            return True
        
        # At bottom 5% of range
        if current < recent_low + (recent_high - recent_low) * 0.05:
            return True
        
        return False
    
    def _detect_structure_break(self, high, low, close) -> Dict:
        """
        Break of market structure (BOS) or Change of Character (CHoCH)
        """
        # Find recent swing highs and lows
        highs = []
        lows = []
        
        for i in range(10, len(close) - 10):
            if high[i] == np.max(high[i-5:i+5]):
                highs.append((i, high[i]))
            if low[i] == np.min(low[i-5:i+5]):
                lows.append((i, low[i]))
        
        if len(highs) < 2 or len(lows) < 2:
            return {'detected': False}
        
        # Check for break of structure
        last_swing_high = highs[-1][1]
        last_swing_low = lows[-1][1]
        
        # Bearish BOS: Broke below recent swing low
        if close[-1] < last_swing_low:
            return {
                'detected': True,
                'type': 'BEARISH_BOS',
                'level': last_swing_low
            }
        
        # Bullish BOS: Broke above recent swing high
        if close[-1] > last_swing_high:
            return {
                'detected': True,
                'type': 'BULLISH_BOS',
                'level': last_swing_high
            }
        
        return {'detected': False}
    
    def _detect_exhaustion_pattern(self, rates) -> bool:
        """
        Candlestick exhaustion patterns (shooting star, hammer, engulfing)
        """
        if len(rates) < 3:
            return False
        
        last = rates[-1]
        prev = rates[-2]
        
        body = abs(last['close'] - last['open'])
        range_size = last['high'] - last['low']
        
        if range_size == 0:
            return False
        
        # Pin bar / Hammer / Shooting Star
        upper_wick = last['high'] - max(last['close'], last['open'])
        lower_wick = min(last['close'], last['open']) - last['low']
        
        if upper_wick > body * 2 or lower_wick > body * 2:
            return True
        
        # Engulfing pattern
        prev_body = abs(prev['close'] - prev['open'])
        if body > prev_body * 1.5:
            return True
        
        return False
    
    def _calculate_reversal_direction(
        self,
        high, low, close,
        signals: List[str]
    ) -> Tuple[str, float]:
        """
        Determine if reversal is bullish or bearish
        """
        # Check current trend
        ema_20 = self._ema(close, 20)
        ema_50 = self._ema(close, 50)
        
        current_trend = "BULLISH" if ema_20[-1] > ema_50[-1] else "BEARISH"
        
        # Reversal is opposite of current trend
        reversal_type = "BEARISH_REVERSAL" if current_trend == "BULLISH" else "BULLISH_REVERSAL"
        
        # Confidence based on number of signals
        confidence = min(0.6 + (len(signals) - self.min_signals_required) * 0.1, 0.95)
        
        return reversal_type, confidence
    
    def _calculate_entry_params(
        self,
        direction: str,
        high, low, close,
        timeframe: int
    ) -> Tuple[float, float, float]:
        """
        Calculate entry, stop loss, and take profit
        """
        # Calculate ATR for stop placement
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = self._ema(tr, 14)[-1]
        
        current_price = close[-1]
        
        if "BULLISH" in direction:
            entry = current_price
            sl = current_price - (atr * 2)
            tp = current_price + (atr * 3.5)
        else:
            entry = current_price
            sl = current_price + (atr * 2)
            tp = current_price - (atr * 3.5)
        
        return entry, sl, tp
    
    # Utility functions
    
    def _calculate_rsi(self, close, period=14):
        """Calculate RSI indicator"""
        delta = np.diff(close)
        gain = np.where(delta > 0, delta, 0)
        loss = np.where(delta < 0, -delta, 0)
        
        avg_gain = np.zeros_like(close)
        avg_loss = np.zeros_like(close)
        
        avg_gain[period] = np.mean(gain[:period])
        avg_loss[period] = np.mean(loss[:period])
        
        for i in range(period + 1, len(close)):
            avg_gain[i] = (avg_gain[i-1] * (period - 1) + gain[i-1]) / period
            avg_loss[i] = (avg_loss[i-1] * (period - 1) + loss[i-1]) / period
        
        rs = avg_gain / (avg_loss + 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _ema(self, data, period):
        """Calculate EMA"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def _find_peaks(self, data):
        """Find local peaks in data"""
        peaks = []
        for i in range(1, len(data) - 1):
            if data[i] > data[i-1] and data[i] > data[i+1]:
                peaks.append(i)
        return peaks
    
    def _find_troughs(self, data):
        """Find local troughs in data"""
        troughs = []
        for i in range(1, len(data) - 1):
            if data[i] < data[i-1] and data[i] < data[i+1]:
                troughs.append(i)
        return troughs
