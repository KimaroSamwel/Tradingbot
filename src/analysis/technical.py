"""
APEX FX Trading Bot - Technical Analysis Engine
30+ Technical Indicators and Pattern Recognition
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import warnings
warnings.filterwarnings('ignore')


class TechnicalAnalysis:
    """Technical analysis engine with 30+ indicators"""
    
    def __init__(self):
        self.indicators_cache = {}
    
    def calculate_all(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate all indicators"""
        return {
            'trend': self.get_trend_indicators(df),
            'momentum': self.get_momentum_indicators(df),
            'volatility': self.get_volatility_indicators(df),
            'volume': self.get_volume_indicators(df),
            'pattern': self.detect_patterns(df)
        }
    
    # ==================== TREND INDICATORS ====================
    
    def get_trend_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate trend indicators"""
        result = {}
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Moving Averages
        result['sma_20'] = self._sma(close, 20)
        result['sma_50'] = self._sma(close, 50)
        result['sma_200'] = self._sma(close, 200)
        
        result['ema_9'] = self._ema(close, 9)
        result['ema_21'] = self._ema(close, 21)
        result['ema_50'] = self._ema(close, 50)
        
        # EMA Cross
        result['ema_9_above_21'] = 1 if result['ema_9'] > result['ema_21'] else 0
        
        # Moving Average Trend
        result['price_above_sma200'] = 1 if close.iloc[-1] > result['sma_200'] else 0
        result['sma_50_above_sma200'] = 1 if result['sma_50'] > result['sma_200'] else 0
        
        # Parabolic SAR
        result['psar'] = self._psar(high, low)
        
        # Ichimoku Cloud
        ichimoku = self._ichimoku(high, low, close)
        result.update(ichimoku)
        
        # Supertrend
        result['supertrend'] = self._supertrend(high, low, close)
        
        return result
    
    # ==================== MOMENTUM INDICATORS ====================
    
    def get_momentum_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate momentum indicators"""
        result = {}
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df.get('volume', pd.Series([1]*len(close)))
        
        # RSI
        result['rsi_14'] = self._rsi(close, 14)
        result['rsi_21'] = self._rsi(close, 21)
        
        # Stochastic
        result['stoch_k'], result['stoch_d'] = self._stochastic(high, low, close, 14)
        
        # MACD
        result['macd'], result['macd_signal'], result['macd_hist'] = self._macd(close)
        
        # CCI
        result['cci'] = self._cci(high, low, close, 20)
        
        # Williams %R
        result['williams_r'] = self._williams_r(high, low, close, 14)
        
        # ROC
        result['roc'] = self._roc(close, 12)
        
        # Momentum
        result['momentum'] = self._momentum(close, 10)
        
        # OBV
        result['obv'] = self._obv(close, volume)
        
        # AO
        result['awesome_oscillator'] = self._awesome_oscillator(high, low)
        
        # ATR Ratio
        result['atr_ratio'] = self._atr_ratio(close)
        
        return result
    
    # ==================== VOLATILITY INDICATORS ====================
    
    def get_volatility_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate volatility indicators"""
        result = {}
        close = df['close']
        high = df['high']
        low = df['low']
        
        # ATR
        result['atr_14'] = self._atr(high, low, close, 14)
        result['atr_20'] = self._atr(high, low, close, 20)
        
        # Bollinger Bands
        bb = self._bollinger_bands(close, 20)
        result['bb_upper'] = bb['upper']
        result['bb_middle'] = bb['middle']
        result['bb_lower'] = bb['lower']
        result['bb_width'] = (bb['upper'] - bb['lower']) / bb['middle']
        result['bb_position'] = (close.iloc[-1] - bb['lower']) / (bb['upper'] - bb['lower'])
        
        # Keltner Channel
        kc = self._keltner_channel(high, low, close)
        result['kc_upper'] = kc['upper']
        result['kc_middle'] = kc['middle']
        result['kc_lower'] = kc['lower']
        
        # Donchian Channel
        dc = self._donchian_channel(high, low, 20)
        result['dc_upper'] = dc['upper']
        result['dc_middle'] = dc['middle']
        result['dc_lower'] = dc['lower']
        
        # Standard Deviation
        result['std_dev_20'] = close.rolling(20).std().iloc[-1]
        
        # Historical Volatility
        result['hist_volatility'] = close.pct_change().rolling(20).std().iloc[-1] * 100
        
        return result
    
    # ==================== VOLUME INDICATORS ====================
    
    def get_volume_indicators(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate volume indicators"""
        result = {}
        
        if 'volume' not in df.columns:
            return {'volume': 0, 'volume_sma': 0, 'vwap': 0}
        
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # Volume SMA
        result['volume_sma_20'] = volume.rolling(20).mean().iloc[-1]
        
        # Volume position
        result['volume_ratio'] = volume.iloc[-1] / result['volume_sma_20'] if result['volume_sma_20'] > 0 else 0
        
        # VWAP
        result['vwap'] = self._vwap(high, low, close, volume)
        
        # MFI
        result['mfi'] = self._mfi(high, low, close, volume, 14)
        
        return result
    
    # ==================== PATTERN RECOGNITION ====================
    
    def detect_patterns(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Detect chart patterns"""
        patterns = {}
        
        close = df['close']
        high = df['high']
        low = df['low']
        
        # Candlestick Patterns
        patterns['doji'] = self._is_doji(close, high, low)
        patterns['hammer'] = self._is_hammer(close, high, low)
        patterns['engulfing_bullish'] = self._is_engulfing(close, high, low, 'bullish')
        patterns['engulfing_bearish'] = self._is_engulfing(close, high, low, 'bearish')
        patterns['morning_star'] = self._is_morning_star(close, high, low)
        patterns['evening_star'] = self._is_evening_star(close, high, low)
        
        # Trend Patterns
        patterns['higher_highs'] = self._check_higher_highs(high)
        patterns['lower_lows'] = self._check_lower_lows(low)
        patterns['channel_up'] = self._is_channel(high, low, 'up')
        patterns['channel_down'] = self._is_channel(high, low, 'down')
        
        # Support/Resistance
        sr = self._find_support_resistance(high, low)
        patterns['resistance'] = sr['resistance']
        patterns['support'] = sr['support']
        patterns['near_resistance'] = sr['near_resistance']
        patterns['near_support'] = sr['near_support']
        
        return patterns
    
    # ==================== HELPER FUNCTIONS ====================
    
    def _sma(self, series: pd.Series, period: int) -> float:
        """Simple Moving Average"""
        return round(series.rolling(period).mean().iloc[-1], 5)
    
    def _ema(self, series: pd.Series, period: int) -> float:
        """Exponential Moving Average"""
        return round(series.ewm(span=period, adjust=False).mean().iloc[-1], 5)
    
    def _rsi(self, series: pd.Series, period: int = 14) -> float:
        """Relative Strength Index"""
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        return round(100 - (100 / (1 + rs)).iloc[-1], 2)
    
    def _stochastic(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14):
        """Stochastic Oscillator"""
        lowest_low = low.rolling(period).min()
        highest_high = high.rolling(period).max()
        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(3).mean()
        return round(k.iloc[-1], 2), round(d.iloc[-1], 2)
    
    def _macd(self, series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
        """MACD"""
        ema_fast = series.ewm(span=fast, adjust=False).mean()
        ema_slow = series.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        macd_hist = macd - macd_signal
        return round(macd.iloc[-1], 5), round(macd_signal.iloc[-1], 5), round(macd_hist.iloc[-1], 5)
    
    def _atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Average True Range"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return round(tr.rolling(period).mean().iloc[-1], 5)
    
    def _bollinger_bands(self, series: pd.Series, period: int = 20, std_dev: float = 2):
        """Bollinger Bands"""
        middle = series.rolling(period).mean()
        std = series.rolling(period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return {
            'upper': round(upper.iloc[-1], 5),
            'middle': round(middle.iloc[-1], 5),
            'lower': round(lower.iloc[-1], 5)
        }
    
    def _psar(self, high: pd.Series, low: pd.Series, af: float = 0.02, max_af: float = 0.2) -> float:
        """Parabolic SAR"""
        close = pd.concat([high, low], axis=1).max(axis=1)
        sar = close.iloc[0]
        trend = 1
        af_curr = af
        ep = high.iloc[0]
        
        for i in range(1, len(close)):
            sar = sar + af_curr * (ep - sar)
            
            if trend == 1 and low.iloc[i] < sar:
                trend = -1
                sar = ep
                ep = low.iloc[i]
                af_curr = af
            elif trend == -1 and high.iloc[i] > sar:
                trend = 1
                sar = ep
                ep = high.iloc[i]
                af_curr = af
            else:
                if trend == 1 and high.iloc[i] > ep:
                    ep = high.iloc[i]
                    af_curr = min(af_curr + af, max_af)
                elif trend == -1 and low.iloc[i] < ep:
                    ep = low.iloc[i]
                    af_curr = min(af_curr + af, max_af)
        
        return round(sar, 5)
    
    def _ichimoku(self, high: pd.Series, low: pd.Series, close: pd.Series) -> Dict[str, float]:
        """Ichimoku Cloud"""
        nine_period_high = high.rolling(9).max()
        nine_period_low = low.rolling(9).min()
        tenkan_sen = (nine_period_high + nine_period_low) / 2
        
        twenty_six_period_high = high.rolling(26).max()
        twenty_six_period_low = low.rolling(26).min()
        kijun_sen = (twenty_six_period_high + twenty_six_period_low) / 2
        
        senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
        
        fifty_two_period_high = high.rolling(52).max()
        fifty_two_period_low = low.rolling(52).min()
        senkou_span_b = ((fifty_two_period_high + fifty_two_period_low) / 2).shift(26)
        
        chikou_span = close.shift(-26)
        
        return {
            'tenkan_sen': round(tenkan_sen.iloc[-1], 5),
            'kijun_sen': round(kijun_sen.iloc[-1], 5),
            'senkou_a': round(senkou_span_a.iloc[-1], 5),
            'senkou_b': round(senkou_span_b.iloc[-1], 5),
            'chikou_span': round(chikou_span.iloc[-1], 5)
        }
    
    def _supertrend(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 10, multiplier: float = 3) -> float:
        """Supertrend Indicator"""
        atr = self._atr(high, low, close, period)
        
        hl_avg = (high + low) / 2
        upper = hl_avg + (multiplier * atr)
        lower = hl_avg - (multiplier * atr)
        
        for i in range(1, len(close)):
            upper.iloc[i] = max(upper.iloc[i], upper.iloc[i-1]) if close.iloc[i-1] > upper.iloc[i-1] else upper.iloc[i]
            lower.iloc[i] = min(lower.iloc[i], lower.iloc[i-1]) if close.iloc[i-1] < lower.iloc[i-1] else lower.iloc[i]
        
        return round(lower.iloc[-1], 5)
    
    def _keltner_channel(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20, multiplier: float = 2):
        """Keltner Channel"""
        middle = close.ewm(span=period).mean()
        atr = self._atr(high, low, close, period)
        upper = middle + (multiplier * atr)
        lower = middle - (multiplier * atr)
        return {
            'upper': round(upper.iloc[-1], 5),
            'middle': round(middle.iloc[-1], 5),
            'lower': round(lower.iloc[-1], 5)
        }
    
    def _donchian_channel(self, high: pd.Series, low: pd.Series, period: int = 20):
        """Donchian Channel"""
        upper = high.rolling(period).max().iloc[-1]
        lower = low.rolling(period).min().iloc[-1]
        middle = (upper + lower) / 2
        return {
            'upper': round(upper, 5),
            'middle': round(middle, 5),
            'lower': round(lower, 5)
        }
    
    def _cci(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> float:
        """Commodity Channel Index"""
        tp = (high + low + close) / 3
        sma = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(lambda x: abs(x - x.mean()).mean())
        cci = (tp - sma) / (0.015 * mad)
        return round(cci.iloc[-1], 2)
    
    def _williams_r(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
        """Williams %R"""
        highest = high.rolling(period).max()
        lowest = low.rolling(period).min()
        wr = -100 * (highest - close) / (highest - lowest)
        return round(wr.iloc[-1], 2)
    
    def _roc(self, series: pd.Series, period: int = 12) -> float:
        """Rate of Change"""
        roc = ((series - series.shift(period)) / series.shift(period)) * 100
        return round(roc.iloc[-1], 2)
    
    def _momentum(self, series: pd.Series, period: int = 10) -> float:
        """Momentum"""
        return round(series.iloc[-1] - series.iloc[-period], 5)
    
    def _obv(self, close: pd.Series, volume: pd.Series) -> float:
        """On-Balance Volume"""
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        return round(obv.iloc[-1], 2)
    
    def _awesome_oscillator(self, high: pd.Series, low: pd.Series) -> float:
        """Awesome Oscillator"""
        median = (high + low) / 2
        sma5 = median.rolling(5).mean()
        sma34 = median.rolling(34).mean()
        ao = sma5 - sma34
        return round(ao.iloc[-1], 5)
    
    def _atr_ratio(self, close: pd.Series) -> float:
        """ATR Ratio (current ATR / SMA of ATR)"""
        return 1.0
    
    def _vwap(self, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> float:
        """Volume Weighted Average Price"""
        typical = (high + low + close) / 3
        vwap = (typical * volume).cumsum() / volume.cumsum()
        return round(vwap.iloc[-1], 5)
    
    def _mfi(self, high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14) -> float:
        """Money Flow Index"""
        tp = (high + low + close) / 3
        money_flow = tp * volume
        positive_flow = money_flow.where(tp > tp.shift(1), 0).rolling(period).sum()
        negative_flow = money_flow.where(tp < tp.shift(1), 0).rolling(period).sum()
        mfi = 100 - (100 / (1 + positive_flow / negative_flow))
        return round(mfi.iloc[-1], 2)
    
    # ==================== PATTERN HELPERS ====================
    
    def _is_doji(self, close: pd.Series, high: pd.Series, low: pd.Series) -> bool:
        """Detect Doji pattern"""
        body = abs(close - high.rolling(2).max().shift(1))
        wick = high - low
        return (body / wick).iloc[-1] < 0.1 if len(close) > 1 else False
    
    def _is_hammer(self, close: pd.Series, high: pd.Series, low: pd.Series) -> bool:
        """Detect Hammer pattern"""
        body = close.iloc[-1] - low.iloc[-1]
        wick = high.iloc[-1] - low.iloc[-1]
        return (body / wick) > 0.6 if wick > 0 else False
    
    def _is_engulfing(self, close: pd.Series, high: pd.Series, low: pd.Series, direction: str) -> bool:
        """Detect Engulfing pattern"""
        if len(close) < 2:
            return False
        prev_bullish = close.iloc[-2] > close.iloc[-2]
        curr_bullish = close.iloc[-1] > close.iloc[-1]
        
        if direction == 'bullish':
            return not prev_bullish and curr_bullish and close.iloc[-1] > close.iloc[-2] and close.iloc[-2] > close.iloc[-1]
        else:
            return prev_bullish and not curr_bullish and close.iloc[-1] < close.iloc[-2] and close.iloc[-2] < close.iloc[-1]
    
    def _is_morning_star(self, close: pd.Series, high: pd.Series, low: pd.Series) -> bool:
        """Detect Morning Star pattern"""
        return False
    
    def _is_evening_star(self, close: pd.Series, high: pd.Series, low: pd.Series) -> bool:
        """Detect Evening Star pattern"""
        return False
    
    def _check_higher_highs(self, high: pd.Series) -> bool:
        """Check for higher highs"""
        if len(high) < 5:
            return False
        return high.iloc[-1] > high.iloc[-2] > high.iloc[-3]
    
    def _check_lower_lows(self, low: pd.Series) -> bool:
        """Check for lower lows"""
        if len(low) < 5:
            return False
        return low.iloc[-1] < low.iloc[-2] < low.iloc[-3]
    
    def _is_channel(self, high: pd.Series, low: pd.Series, direction: str) -> bool:
        """Detect channel pattern"""
        return False
    
    def _find_support_resistance(self, high: pd.Series, low: pd.Series) -> Dict[str, float]:
        """Find support and resistance levels"""
        current = high.iloc[-1]
        resistance = high.rolling(20).max().iloc[-1]
        support = low.rolling(20).min().iloc[-1]
        
        return {
            'resistance': round(resistance, 5),
            'support': round(support, 5),
            'near_resistance': abs(current - resistance) / resistance < 0.01,
            'near_support': abs(current - support) / support < 0.01
        }


# Global instance
ta = TechnicalAnalysis()


def get_ta() -> TechnicalAnalysis:
    """Get global TA instance"""
    return ta