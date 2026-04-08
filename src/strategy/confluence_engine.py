"""
Confluence Scoring System (0-100 points)
Multi-layer confirmation system for trade entry
"""

import numpy as np
import MetaTrader5 as mt5
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from ..analysis.market_regime_advanced import AdvancedMarketRegimeDetector, MarketRegime
from ..analysis.session_analyzer import SessionAnalyzer
from ..analysis.reversal_detector import ReversalDetector
from ..analysis.precious_metals_engine import PreciousMetalsEngine


@dataclass
class ConfluenceScore:
    total_score: int  # 0-100
    confidence: float  # 0-1
    signal: str  # BUY, SELL, NEUTRAL
    breakdown: Dict[str, int]
    passed_filters: List[str]
    failed_filters: List[str]
    recommended_action: str
    risk_reward_ratio: float
    position_size_multiplier: float


class ConfluenceEngine:
    """
    Professional confluence scoring system
    Requires minimum score to trade
    """
    
    def __init__(self):
        self.regime_detector = AdvancedMarketRegimeDetector()
        self.session_analyzer = SessionAnalyzer()
        self.reversal_detector = ReversalDetector()
        self.metals_engine = PreciousMetalsEngine()
        
        # Scoring weights (total = 100)
        self.weights = {
            'multi_timeframe': 25,
            'trend_alignment': 20,
            'momentum': 15,
            'volatility': 10,
            'order_blocks': 10,
            'session': 10,
            'volume': 5,
            'pattern': 5
        }
        
        self.min_score_to_trade = 65
        self.min_confidence = 0.60
    
    def calculate_confluence(
        self,
        symbol: str,
        timeframe: int,
        lookback: int = 100
    ) -> Optional[ConfluenceScore]:
        """
        Calculate complete confluence score
        """
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, lookback)
        if rates is None or len(rates) < lookback:
            return None
        
        high = rates['high']
        low = rates['low']
        close = rates['close']
        volume = rates['tick_volume']
        
        breakdown = {}
        passed = []
        failed = []
        
        # Layer 1: Multi-Timeframe Alignment (25 points)
        mtf_score = self._score_multi_timeframe(symbol, close[-1])
        breakdown['multi_timeframe'] = mtf_score
        if mtf_score >= 15:
            passed.append("Multi-Timeframe Alignment")
        else:
            failed.append("Multi-Timeframe Alignment")
        
        # Layer 2: Trend Alignment (20 points)
        trend_score = self._score_trend_alignment(close)
        breakdown['trend_alignment'] = trend_score
        if trend_score >= 12:
            passed.append("Trend Alignment")
        else:
            failed.append("Trend Alignment")
        
        # Layer 3: Momentum Indicators (15 points)
        momentum_score = self._score_momentum(high, low, close)
        breakdown['momentum'] = momentum_score
        if momentum_score >= 9:
            passed.append("Momentum")
        else:
            failed.append("Momentum")
        
        # Layer 4: Volatility Analysis (10 points)
        volatility_score = self._score_volatility(high, low, close)
        breakdown['volatility'] = volatility_score
        if volatility_score >= 6:
            passed.append("Volatility")
        else:
            failed.append("Volatility")
        
        # Layer 5: Order Blocks (10 points)
        ob_score = self._score_order_blocks(high, low, close, volume)
        breakdown['order_blocks'] = ob_score
        if ob_score >= 6:
            passed.append("Order Blocks")
        else:
            failed.append("Order Blocks")
        
        # Layer 6: Session Quality (10 points)
        session_score = self._score_session(symbol)
        breakdown['session'] = session_score
        if session_score >= 6:
            passed.append("Session Quality")
        else:
            failed.append("Session Quality")
        
        # Layer 7: Volume Confirmation (5 points)
        volume_score = self._score_volume(close, volume)
        breakdown['volume'] = volume_score
        if volume_score >= 3:
            passed.append("Volume")
        
        # Layer 8: Pattern Recognition (5 points)
        pattern_score = self._score_patterns(rates)
        breakdown['pattern'] = pattern_score
        if pattern_score >= 3:
            passed.append("Pattern")
        
        # Calculate total
        total_score = sum(breakdown.values())
        
        # Determine signal direction
        signal, confidence = self._determine_signal(
            breakdown,
            close,
            total_score
        )
        
        # Calculate R:R
        rr_ratio = self._calculate_risk_reward(symbol, signal, close[-1])
        
        # Position size multiplier
        size_multiplier = self._calculate_position_multiplier(
            total_score,
            confidence,
            symbol
        )
        
        # Recommended action
        action = self._recommend_action(
            total_score,
            confidence,
            len(passed),
            rr_ratio
        )
        
        return ConfluenceScore(
            total_score=total_score,
            confidence=confidence,
            signal=signal,
            breakdown=breakdown,
            passed_filters=passed,
            failed_filters=failed,
            recommended_action=action,
            risk_reward_ratio=rr_ratio,
            position_size_multiplier=size_multiplier
        )
    
    def _score_multi_timeframe(self, symbol: str, current_price: float) -> int:
        """
        Score based on multi-timeframe alignment
        25 points max
        """
        timeframes = [mt5.TIMEFRAME_M15, mt5.TIMEFRAME_H1, mt5.TIMEFRAME_H4, mt5.TIMEFRAME_D1]
        alignments = 0
        
        for tf in timeframes:
            rates = mt5.copy_rates_from_pos(symbol, tf, 0, 50)
            if rates is None:
                continue
            
            close = rates['close']
            ema_20 = self._ema(close, 20)
            ema_50 = self._ema(close, 50)
            
            # Check if trend is clear
            if ema_20[-1] > ema_50[-1] and close[-1] > ema_20[-1]:
                alignments += 1
            elif ema_20[-1] < ema_50[-1] and close[-1] < ema_20[-1]:
                alignments += 1
        
        # Score: 0, 6, 12, 18, 25 points
        score_map = {0: 0, 1: 6, 2: 12, 3: 18, 4: 25}
        return score_map.get(alignments, 0)
    
    def _score_trend_alignment(self, close) -> int:
        """
        Score EMA alignment and trend strength
        20 points max
        """
        ema_8 = self._ema(close, 8)
        ema_21 = self._ema(close, 21)
        ema_50 = self._ema(close, 50)
        ema_200 = self._ema(close, 200)
        
        score = 0
        
        # Perfect bullish alignment
        if (ema_8[-1] > ema_21[-1] > ema_50[-1] > ema_200[-1] and
            close[-1] > ema_8[-1]):
            score = 20
        # Perfect bearish alignment
        elif (ema_8[-1] < ema_21[-1] < ema_50[-1] < ema_200[-1] and
              close[-1] < ema_8[-1]):
            score = 20
        # Partial alignment
        elif ema_8[-1] > ema_21[-1] > ema_50[-1]:
            score = 15
        elif ema_8[-1] < ema_21[-1] < ema_50[-1]:
            score = 15
        # Weak alignment
        elif ema_8[-1] > ema_21[-1]:
            score = 8
        elif ema_8[-1] < ema_21[-1]:
            score = 8
        
        return score
    
    def _score_momentum(self, high, low, close) -> int:
        """
        Score momentum indicators (RSI, ADX, Stochastic)
        15 points max
        """
        score = 0
        
        # RSI
        rsi = self._calculate_rsi(close, 14)
        if 40 < rsi[-1] < 70:  # Bullish zone
            score += 5
        elif 30 < rsi[-1] < 60:  # Bearish zone
            score += 5
        
        # ADX
        adx = self._calculate_adx(high, low, close, 14)
        if adx is not None:
            if adx[-1] > 25:
                score += 5
            elif adx[-1] > 20:
                score += 3
        
        # Momentum direction
        momentum = (close[-1] - close[-10]) / close[-10]
        if abs(momentum) > 0.01:
            score += 5
        elif abs(momentum) > 0.005:
            score += 3
        
        return min(score, 15)
    
    def _score_volatility(self, high, low, close) -> int:
        """
        Score volatility conditions
        10 points max
        """
        # Calculate ATR
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = self._ema(tr, 14)
        
        avg_atr = np.mean(atr[-50:])
        current_vs_avg = atr[-1] / avg_atr if avg_atr > 0 else 1.0
        
        # Ideal: Normal to slightly elevated volatility
        if 0.9 <= current_vs_avg <= 1.2:
            return 10
        elif 0.8 <= current_vs_avg <= 1.4:
            return 7
        elif 0.7 <= current_vs_avg <= 1.6:
            return 4
        else:
            return 2
    
    def _score_order_blocks(self, high, low, close, volume) -> int:
        """
        Score order block proximity
        10 points max
        """
        # Detect recent order blocks
        ob_found = False
        
        for i in range(len(close) - 20, len(close) - 2):
            if i < 1:
                continue
            
            # Bullish order block: down candle followed by strong up move
            if close[i] < close[i-1]:
                next_move = close[i+1] - close[i]
                prev_body = abs(close[i] - close[i-1])
                
                if next_move > prev_body * 1.5:
                    # Check if current price is near this OB
                    ob_low = min(close[i], close[i-1])
                    ob_high = max(close[i], close[i-1])
                    
                    if ob_low <= close[-1] <= ob_high * 1.02:
                        ob_found = True
                        break
            
            # Bearish order block
            elif close[i] > close[i-1]:
                next_move = close[i] - close[i+1]
                prev_body = abs(close[i] - close[i-1])
                
                if next_move > prev_body * 1.5:
                    ob_low = min(close[i], close[i-1])
                    ob_high = max(close[i], close[i-1])
                    
                    if ob_low * 0.98 <= close[-1] <= ob_high:
                        ob_found = True
                        break
        
        return 10 if ob_found else 3
    
    def _score_session(self, symbol: str) -> int:
        """
        Score session quality
        10 points max
        """
        session_analysis = self.session_analyzer.analyze_session(symbol)
        
        if session_analysis.current_session.name == "LONDON_NY_OVERLAP":
            return 10
        elif session_analysis.current_session.name in ["LONDON", "NEW_YORK"]:
            return 8
        elif session_analysis.current_session.name == "ASIAN":
            return 5
        else:
            return 2
    
    def _score_volume(self, close, volume) -> int:
        """
        Score volume confirmation
        5 points max
        """
        avg_volume = np.mean(volume[-50:])
        recent_volume = np.mean(volume[-5:])
        
        # Volume increasing
        if recent_volume > avg_volume * 1.2:
            return 5
        elif recent_volume > avg_volume:
            return 3
        else:
            return 1
    
    def _score_patterns(self, rates) -> int:
        """
        Score candlestick patterns
        5 points max
        """
        if len(rates) < 3:
            return 0
        
        last = rates[-1]
        prev = rates[-2]
        
        body = abs(last['close'] - last['open'])
        range_size = last['high'] - last['low']
        
        if range_size == 0:
            return 0
        
        # Pin bar / Hammer
        upper_wick = last['high'] - max(last['close'], last['open'])
        lower_wick = min(last['close'], last['open']) - last['low']
        
        if upper_wick > body * 2 or lower_wick > body * 2:
            return 5
        
        # Engulfing
        prev_body = abs(prev['close'] - prev['open'])
        if body > prev_body * 1.3:
            return 4
        
        # Strong directional candle
        if body / range_size > 0.7:
            return 3
        
        return 1
    
    def _determine_signal(
        self,
        breakdown: Dict,
        close,
        total_score: int
    ) -> tuple:
        """
        Determine trade signal and confidence
        """
        # Check trend direction
        ema_20 = self._ema(close, 20)
        ema_50 = self._ema(close, 50)
        
        if ema_20[-1] > ema_50[-1] and close[-1] > ema_20[-1]:
            signal = "BUY"
        elif ema_20[-1] < ema_50[-1] and close[-1] < ema_20[-1]:
            signal = "SELL"
        else:
            signal = "NEUTRAL"
        
        # Confidence based on score
        confidence = min(total_score / 100, 0.95)
        
        return signal, confidence
    
    def _calculate_risk_reward(self, symbol: str, signal: str, current_price: float) -> float:
        """
        Calculate expected R:R ratio
        """
        # Get ATR for stop/target calculation
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_H1, 0, 20)
        if rates is None:
            return 1.5
        
        high = rates['high']
        low = rates['low']
        close = rates['close']
        
        tr1 = high - low
        tr2 = np.abs(high - np.roll(close, 1))
        tr3 = np.abs(low - np.roll(close, 1))
        tr = np.maximum(tr1, np.maximum(tr2, tr3))
        atr = np.mean(tr[-14:])
        
        # Stop: 2 x ATR, Target: 3.5 x ATR
        risk = atr * 2
        reward = atr * 3.5
        
        return reward / risk if risk > 0 else 1.5
    
    def _calculate_position_multiplier(
        self,
        total_score: int,
        confidence: float,
        symbol: str
    ) -> float:
        """
        Calculate position size multiplier
        """
        # Base on score
        if total_score >= 80:
            base = 1.0
        elif total_score >= 70:
            base = 0.9
        elif total_score >= 65:
            base = 0.8
        else:
            base = 0.6
        
        # Adjust for confidence
        base *= confidence
        
        # Adjust for asset type
        clean_symbol = symbol.replace('.', '').upper()
        if 'XAU' in clean_symbol or 'GOLD' in clean_symbol:
            base *= 0.8
        elif 'XAG' in clean_symbol or 'SILVER' in clean_symbol:
            base *= 0.6
        
        return max(0.3, min(base, 1.2))
    
    def _recommend_action(
        self,
        total_score: int,
        confidence: float,
        passed_count: int,
        rr_ratio: float
    ) -> str:
        """
        Recommend action based on confluence
        """
        if (total_score >= 75 and 
            confidence >= 0.70 and 
            passed_count >= 6 and
            rr_ratio >= 1.5):
            return "STRONG_ENTRY"
        
        elif (total_score >= self.min_score_to_trade and
              confidence >= self.min_confidence and
              passed_count >= 5 and
              rr_ratio >= 1.2):
            return "ENTRY"
        
        elif total_score >= 55:
            return "WAIT_BETTER_SETUP"
        
        else:
            return "NO_TRADE"
    
    # Utility functions
    
    def _ema(self, data, period):
        """Calculate EMA"""
        alpha = 2 / (period + 1)
        ema = np.zeros_like(data)
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = alpha * data[i] + (1 - alpha) * ema[i-1]
        
        return ema
    
    def _calculate_rsi(self, close, period=14):
        """Calculate RSI"""
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
    
    def _calculate_adx(self, high, low, close, period=14):
        """Calculate ADX"""
        try:
            tr1 = high - low
            tr2 = np.abs(high - np.roll(close, 1))
            tr3 = np.abs(low - np.roll(close, 1))
            tr = np.maximum(tr1, np.maximum(tr2, tr3))
            
            up_move = high - np.roll(high, 1)
            down_move = np.roll(low, 1) - low
            
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            
            atr = self._ema(tr, period)
            plus_di = 100 * self._ema(plus_dm, period) / atr
            minus_di = 100 * self._ema(minus_dm, period) / atr
            
            dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10)
            adx = self._ema(dx, period)
            
            return adx
        except:
            return None
