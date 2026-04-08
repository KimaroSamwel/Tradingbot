"""
Multi-Timeframe Strategy Orchestration
Combines signals from M5, M15, H1, H4, D1 timeframes
Only trades when multiple timeframes align
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import MetaTrader5 as mt5
from src.analysis.advanced_indicators import AdvancedIndicators
from src.analysis.market_regime import MarketRegimeDetector
from src.analysis.order_blocks import OrderBlockDetector, SmartMoneyConceptsAnalyzer


@dataclass
class TimeframeSignal:
    """Signal from a single timeframe"""
    timeframe: str
    direction: str  # 'bullish', 'bearish', 'neutral'
    strength: float  # 0-100
    trend: str  # 'strong_up', 'up', 'ranging', 'down', 'strong_down'
    regime: str  # From regime detector
    order_block_bias: str
    entry_quality: float  # 0-100


@dataclass
class MultiTimeframeSignal:
    """Combined signal from multiple timeframes"""
    primary_direction: str
    confidence: int  # 0-100
    timeframe_alignment: Dict[str, str]
    strength_score: float
    entry_timeframe: str
    stop_loss: float
    take_profit: float
    reason: str


class MultiTimeframeOrchestrator:
    """
    Orchestrates trading signals across multiple timeframes
    
    Hierarchy:
    - D1: Overall trend direction
    - H4: Intermediate trend
    - H1: Entry trend
    - M15: Precision entry
    - M5: Exact entry timing
    """
    
    def __init__(self, config: Dict):
        self.config = config
        self.timeframes = {
            'D1': mt5.TIMEFRAME_D1,
            'H4': mt5.TIMEFRAME_H4,
            'H1': mt5.TIMEFRAME_H1,
            'M15': mt5.TIMEFRAME_M15,
            'M5': mt5.TIMEFRAME_M5
        }
        
        # Pass full config - AdvancedIndicators will extract strategy.indicators
        self.indicators = AdvancedIndicators(config)
        # MarketRegimeDetector accepts optional config
        self.regime_detector = MarketRegimeDetector(config)
        self.smc_analyzer = SmartMoneyConceptsAnalyzer()
    
    def get_multi_timeframe_data(self, symbol: str, bars: int = 500) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for all timeframes
        
        Args:
            symbol: Trading symbol
            bars: Number of bars to fetch
        
        Returns:
            Dict of {timeframe: DataFrame}
        """
        data = {}
        
        for tf_name, tf_value in self.timeframes.items():
            rates = mt5.copy_rates_from_pos(symbol, tf_value, 0, bars)
            
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                df.set_index('time', inplace=True)
                data[tf_name] = df
        
        return data
    
    def analyze_timeframe(self, df: pd.DataFrame, timeframe: str) -> TimeframeSignal:
        """
        Analyze single timeframe
        
        Args:
            df: Price data for timeframe
            timeframe: Timeframe name (D1, H4, etc.)
        
        Returns:
            TimeframeSignal
        """
        # Calculate indicators
        df_with_indicators = self.indicators.calculate_all(df)
        
        # Detect regime
        regime = self.regime_detector.detect_regime(df_with_indicators)
        
        # Analyze with Smart Money Concepts
        smc_analysis = self.smc_analyzer.analyze_market_phase(df_with_indicators)
        
        # Get last values
        last = df_with_indicators.iloc[-1]
        
        # Determine trend direction
        trend = self._determine_trend(last)
        
        # Determine directional bias
        direction = self._determine_direction(last, regime, smc_analysis)
        
        # Calculate signal strength
        strength = self._calculate_signal_strength(last, regime, smc_analysis)
        
        # Get order block bias
        trading_bias = self.smc_analyzer.get_trading_bias(
            smc_analysis['phase'],
            smc_analysis.get('order_blocks', []),
            last['close']
        )
        
        return TimeframeSignal(
            timeframe=timeframe,
            direction=direction,
            strength=strength,
            trend=trend,
            regime=regime['regime'],
            order_block_bias=trading_bias['bias'],
            entry_quality=trading_bias['confidence']
        )
    
    def _determine_trend(self, last_row: pd.Series) -> str:
        """Determine trend from indicators"""
        # Use EMA alignment
        if 'ema_8' not in last_row or 'ema_200' not in last_row:
            return 'unknown'
        
        close = last_row['close']
        ema_8 = last_row['ema_8']
        ema_21 = last_row.get('ema_21', close)
        ema_50 = last_row.get('ema_50', close)
        ema_200 = last_row['ema_200']
        
        # Strong uptrend: All EMAs aligned + price above all
        if (close > ema_8 > ema_21 > ema_50 > ema_200):
            return 'strong_up'
        
        # Uptrend: Price above key EMAs
        if close > ema_50 > ema_200:
            return 'up'
        
        # Strong downtrend: All EMAs aligned + price below all
        if (close < ema_8 < ema_21 < ema_50 < ema_200):
            return 'strong_down'
        
        # Downtrend: Price below key EMAs
        if close < ema_50 < ema_200:
            return 'down'
        
        # Ranging: EMAs tangled
        return 'ranging'
    
    def _determine_direction(self, last_row: pd.Series, regime: Dict, smc: Dict) -> str:
        """Determine directional bias"""
        # Check trend direction
        close = last_row['close']
        ema_200 = last_row.get('ema_200', close)
        
        # Check oscillators
        rsi = last_row.get('rsi', 50)
        macd_hist = last_row.get('macd_hist', 0)
        
        bullish_signals = 0
        bearish_signals = 0
        
        # Trend signals
        if close > ema_200:
            bullish_signals += 2
        else:
            bearish_signals += 2
        
        # MACD
        if macd_hist > 0:
            bullish_signals += 1
        else:
            bearish_signals += 1
        
        # RSI
        if rsi > 50:
            bullish_signals += 1
        else:
            bearish_signals += 1
        
        # Regime
        if regime['regime'] in ['strong_trending', 'trending']:
            if regime.get('trend_direction') == 1:
                bullish_signals += 2
            else:
                bearish_signals += 2
        
        # Smart Money Concepts phase
        phase = smc.get('phase', 'unknown')
        if phase == 'accumulation':
            bullish_signals += 1
        elif phase == 'distribution':
            bearish_signals += 1
        
        # Determine direction
        if bullish_signals > bearish_signals + 2:
            return 'bullish'
        elif bearish_signals > bullish_signals + 2:
            return 'bearish'
        else:
            return 'neutral'
    
    def _calculate_signal_strength(self, last_row: pd.Series, regime: Dict, smc: Dict) -> float:
        """Calculate signal strength 0-100"""
        strength = 50.0  # Base
        
        # ADX strength
        adx = last_row.get('adx', 0)
        if adx > 40:
            strength += 15
        elif adx > 30:
            strength += 10
        elif adx > 25:
            strength += 5
        elif adx < 15:
            strength -= 10
        
        # Regime confidence
        regime_conf = regime.get('confidence', 50)
        strength += (regime_conf - 50) * 0.3
        
        # Order blocks
        active_obs = smc.get('active_order_blocks', 0)
        if active_obs > 0:
            strength += min(10, active_obs * 3)
        
        # Volume
        volume_strength = last_row.get('volume_imbalance', 0)
        if abs(volume_strength) > 0.3:
            strength += 5
        
        return max(0, min(100, strength))
    
    def get_multi_timeframe_signal(self, symbol: str) -> Optional[MultiTimeframeSignal]:
        """
        Get combined multi-timeframe signal
        
        Args:
            symbol: Trading symbol
        
        Returns:
            MultiTimeframeSignal if alignment found, None otherwise
        """
        # Fetch all timeframe data
        mtf_data = self.get_multi_timeframe_data(symbol)
        
        if len(mtf_data) < 3:
            return None
        
        # Analyze each timeframe
        signals = {}
        for tf_name, df in mtf_data.items():
            signals[tf_name] = self.analyze_timeframe(df, tf_name)
        
        # Check alignment
        alignment = self._check_timeframe_alignment(signals)
        
        if not alignment['aligned']:
            return None
        
        # Determine entry timeframe and levels
        entry_tf = self._determine_entry_timeframe(signals, alignment)
        
        # Calculate stop loss and take profit
        sl, tp = self._calculate_levels(mtf_data, signals, entry_tf, alignment['direction'])
        
        return MultiTimeframeSignal(
            primary_direction=alignment['direction'],
            confidence=alignment['confidence'],
            timeframe_alignment={tf: sig.direction for tf, sig in signals.items()},
            strength_score=alignment['strength'],
            entry_timeframe=entry_tf,
            stop_loss=sl,
            take_profit=tp,
            reason=alignment['reason']
        )
    
    def _check_timeframe_alignment(self, signals: Dict[str, TimeframeSignal]) -> Dict:
        """
        Check if timeframes are aligned
        
        Rules:
        1. D1 and H4 must agree (higher timeframe context)
        2. H1 must not conflict
        3. M15/M5 for entry timing
        
        Args:
            signals: Dict of timeframe signals
        
        Returns:
            Dict with alignment info
        """
        # Get higher timeframe signals
        d1 = signals.get('D1')
        h4 = signals.get('H4')
        h1 = signals.get('H1')
        m15 = signals.get('M15')
        
        if not d1 or not h4 or not h1:
            return {'aligned': False, 'reason': 'Missing required timeframes'}
        
        # Check D1 and H4 alignment (most important)
        if d1.direction == 'neutral' or h4.direction == 'neutral':
            return {'aligned': False, 'reason': 'Higher timeframes neutral'}
        
        if d1.direction != h4.direction:
            return {'aligned': False, 'reason': 'D1 and H4 divergence'}
        
        # H1 must not contradict
        if h1.direction != 'neutral' and h1.direction != h4.direction:
            # Allow if H1 is just consolidating in higher timeframe trend
            if h1.trend != 'ranging':
                return {'aligned': False, 'reason': 'H1 conflicts with higher timeframes'}
        
        # Calculate confidence
        confidence = 50
        
        # All timeframes aligned
        if all(sig.direction == d1.direction for sig in [h4, h1]):
            confidence += 20
        
        # Strong trends on higher TFs
        if d1.trend in ['strong_up', 'strong_down']:
            confidence += 10
        if h4.trend in ['strong_up', 'strong_down']:
            confidence += 5
        
        # High strength scores
        avg_strength = np.mean([sig.strength for sig in signals.values()])
        if avg_strength > 70:
            confidence += 10
        elif avg_strength > 60:
            confidence += 5
        
        # Order block alignment
        if m15 and m15.order_block_bias == d1.direction:
            confidence += 5
        
        # Calculate combined strength
        strength = np.mean([sig.strength for sig in signals.values()])
        
        return {
            'aligned': True,
            'direction': d1.direction,
            'confidence': min(100, confidence),
            'strength': strength,
            'reason': f"Multi-timeframe alignment: D1/{h4.timeframe}/{h1.timeframe} all {d1.direction}"
        }
    
    def _determine_entry_timeframe(self, signals: Dict[str, TimeframeSignal],
                                   alignment: Dict) -> str:
        """
        Determine which timeframe to use for entry
        
        Generally: M15 for swing trades, M5 for scalps
        """
        # If M15 has high quality setup, use it
        m15 = signals.get('M15')
        if m15 and m15.entry_quality > 70:
            return 'M15'
        
        # If H1 has strong setup and trending, use H1
        h1 = signals.get('H1')
        if h1 and h1.strength > 70 and h1.trend in ['strong_up', 'strong_down']:
            return 'H1'
        
        # Default to M15
        return 'M15'
    
    def _calculate_levels(self, mtf_data: Dict[str, pd.DataFrame],
                         signals: Dict[str, TimeframeSignal],
                         entry_tf: str, direction: str) -> Tuple[float, float]:
        """
        Calculate stop loss and take profit levels
        
        Args:
            mtf_data: Multi-timeframe data
            signals: Multi-timeframe signals
            entry_tf: Entry timeframe
            direction: Trade direction
        
        Returns:
            (stop_loss, take_profit)
        """
        # Get entry timeframe data
        entry_data = mtf_data.get(entry_tf)
        if entry_data is None:
            return (0.0, 0.0)
        
        last = entry_data.iloc[-1]
        current_price = last['close']
        
        # Use ATR from H1 for stop placement
        h1_data = mtf_data.get('H1', entry_data)
        atr = h1_data.iloc[-1].get('atr', (h1_data['high'].iloc[-20:] - h1_data['low'].iloc[-20:]).mean())
        
        # Calculate stop loss
        if direction == 'bullish':
            # Stop below recent swing low
            recent_low = entry_data['low'].iloc[-20:].min()
            sl = recent_low - (atr * 0.5)
            
            # Take profit based on H4 targets
            h4_data = mtf_data.get('H4', entry_data)
            h4_atr = h4_data.iloc[-1].get('atr', atr * 2)
            tp = current_price + (h4_atr * 2.5)
        
        else:  # bearish
            # Stop above recent swing high
            recent_high = entry_data['high'].iloc[-20:].max()
            sl = recent_high + (atr * 0.5)
            
            # Take profit
            h4_data = mtf_data.get('H4', entry_data)
            h4_atr = h4_data.iloc[-1].get('atr', atr * 2)
            tp = current_price - (h4_atr * 2.5)
        
        return (sl, tp)
    
    def get_detailed_analysis(self, symbol: str) -> Dict:
        """
        Get detailed multi-timeframe analysis for review
        
        Args:
            symbol: Trading symbol
        
        Returns:
            Complete analysis Dict
        """
        # Fetch data
        mtf_data = self.get_multi_timeframe_data(symbol)
        
        # Analyze each timeframe
        signals = {}
        for tf_name, df in mtf_data.items():
            signals[tf_name] = self.analyze_timeframe(df, tf_name)
        
        # Check alignment
        alignment = self._check_timeframe_alignment(signals)
        
        # Get multi-timeframe signal if aligned
        mtf_signal = None
        if alignment['aligned']:
            mtf_signal = self.get_multi_timeframe_signal(symbol)
        
        return {
            'symbol': symbol,
            'signals': signals,
            'alignment': alignment,
            'mtf_signal': mtf_signal,
            'timestamp': pd.Timestamp.now()
        }
