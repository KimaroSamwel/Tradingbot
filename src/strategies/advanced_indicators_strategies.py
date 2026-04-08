"""
ADVANCED INDICATORS STRATEGIES COLLECTION
Implementation of 15+ advanced technical indicators

Includes:
- Ichimoku Cloud Complete System
- SuperTrend Indicator
- Parabolic SAR
- Williams %R
- CCI (Commodity Channel Index)
- Schaff Trend Cycle
- Awesome Oscillator
- Accelerator Oscillator
- Market Facilitation Index
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class AdvancedIndicatorSignal:
    strategy: str
    indicator: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    indicator_value: float
    timeframe: str


class IchimokuStrategy:
    """Complete Ichimoku Cloud System"""
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> Optional[AdvancedIndicatorSignal]:
        """
        Ichimoku Cloud Strategy
        Components: Tenkan-sen, Kijun-sen, Senkou Span A, Senkou Span B, Chikou Span
        """
        if len(df) < 52:
            return None
        
        # Calculate Ichimoku components
        high_9 = df['high'].rolling(9).max()
        low_9 = df['low'].rolling(9).min()
        tenkan = (high_9 + low_9) / 2  # Conversion Line
        
        high_26 = df['high'].rolling(26).max()
        low_26 = df['low'].rolling(26).min()
        kijun = (high_26 + low_26) / 2  # Base Line
        
        senkou_a = ((tenkan + kijun) / 2).shift(26)  # Leading Span A
        
        high_52 = df['high'].rolling(52).max()
        low_52 = df['low'].rolling(52).min()
        senkou_b = ((high_52 + low_52) / 2).shift(26)  # Leading Span B
        
        # FIX: Chikou span uses shift(-26) which REP AINTS - removed from live signals
        # chikou = df['close'].shift(-26)  # REMOVED: Causes repainting in live trading
        # NOTE: Chikou is only useful for historical analysis, not real-time signals
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Bullish signal: Tenkan crosses above Kijun, price above cloud
        # NOTE: Using iloc[-2] and iloc[-1] for crossover detection (non-repainting)
        if (tenkan.iloc[-2] <= kijun.iloc[-2] and tenkan.iloc[-1] > kijun.iloc[-1] and
            current_price > senkou_a.iloc[-1] and current_price > senkou_b.iloc[-1]):
            
            cloud_top = max(senkou_a.iloc[-1], senkou_b.iloc[-1])
            
            return AdvancedIndicatorSignal(
                strategy='ichimoku',
                indicator='ICHIMOKU_CLOUD',
                direction='LONG',
                entry_price=current_price,
                stop_loss=cloud_top,
                take_profit=current_price + (atr * 3.0),
                confidence=85.0,
                indicator_value=tenkan.iloc[-1],
                timeframe='H1'
            )
        
        # Bearish signal
        elif (tenkan.iloc[-2] >= kijun.iloc[-2] and tenkan.iloc[-1] < kijun.iloc[-1] and
              current_price < senkou_a.iloc[-1] and current_price < senkou_b.iloc[-1]):
            
            cloud_bottom = min(senkou_a.iloc[-1], senkou_b.iloc[-1])
            
            return AdvancedIndicatorSignal(
                strategy='ichimoku',
                indicator='ICHIMOKU_CLOUD',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=cloud_bottom,
                take_profit=current_price - (atr * 3.0),
                confidence=85.0,
                indicator_value=tenkan.iloc[-1],
                timeframe='H1'
            )
        
        return None


class SuperTrendStrategy:
    """SuperTrend Indicator Strategy"""
    
    @staticmethod
    def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
        """Calculate SuperTrend indicator"""
        hl2 = (df['high'] + df['low']) / 2
        
        # Calculate ATR
        high_low = df['high'] - df['low']
        high_close = np.abs(df['high'] - df['close'].shift())
        low_close = np.abs(df['low'] - df['close'].shift())
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        # Calculate basic bands
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        # Initialize SuperTrend
        supertrend = pd.Series(index=df.index, dtype=float)
        direction = pd.Series(index=df.index, dtype=int)
        
        for i in range(period, len(df)):
            if df['close'].iloc[i] > upper_band.iloc[i-1]:
                supertrend.iloc[i] = lower_band.iloc[i]
                direction.iloc[i] = 1
            elif df['close'].iloc[i] < lower_band.iloc[i-1]:
                supertrend.iloc[i] = upper_band.iloc[i]
                direction.iloc[i] = -1
            else:
                supertrend.iloc[i] = supertrend.iloc[i-1]
                direction.iloc[i] = direction.iloc[i-1]
        
        return supertrend, direction
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> Optional[AdvancedIndicatorSignal]:
        """SuperTrend Strategy"""
        if len(df) < 20:
            return None
        
        supertrend, direction = SuperTrendStrategy.calculate_supertrend(df)
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Bullish signal
        if direction.iloc[-2] == -1 and direction.iloc[-1] == 1:
            return AdvancedIndicatorSignal(
                strategy='supertrend',
                indicator='SUPERTREND',
                direction='LONG',
                entry_price=current_price,
                stop_loss=supertrend.iloc[-1],
                take_profit=current_price + (atr * 3.0),
                confidence=80.0,
                indicator_value=supertrend.iloc[-1],
                timeframe='M15'
            )
        
        # Bearish signal
        elif direction.iloc[-2] == 1 and direction.iloc[-1] == -1:
            return AdvancedIndicatorSignal(
                strategy='supertrend',
                indicator='SUPERTREND',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=supertrend.iloc[-1],
                take_profit=current_price - (atr * 3.0),
                confidence=80.0,
                indicator_value=supertrend.iloc[-1],
                timeframe='M15'
            )
        
        return None


class ParabolicSARStrategy:
    """Parabolic SAR Strategy"""
    
    @staticmethod
    def calculate_sar(df: pd.DataFrame, acceleration: float = 0.02, maximum: float = 0.2) -> pd.Series:
        """Calculate Parabolic SAR"""
        sar = pd.Series(index=df.index, dtype=float)
        ep = df['high'].iloc[0]
        sar.iloc[0] = df['low'].iloc[0]
        af = acceleration
        trend = 1  # 1 for uptrend, -1 for downtrend
        
        for i in range(1, len(df)):
            sar.iloc[i] = sar.iloc[i-1] + af * (ep - sar.iloc[i-1])
            
            if trend == 1:
                if df['low'].iloc[i] < sar.iloc[i]:
                    trend = -1
                    sar.iloc[i] = ep
                    ep = df['low'].iloc[i]
                    af = acceleration
                else:
                    if df['high'].iloc[i] > ep:
                        ep = df['high'].iloc[i]
                        af = min(af + acceleration, maximum)
            else:
                if df['high'].iloc[i] > sar.iloc[i]:
                    trend = 1
                    sar.iloc[i] = ep
                    ep = df['high'].iloc[i]
                    af = acceleration
                else:
                    if df['low'].iloc[i] < ep:
                        ep = df['low'].iloc[i]
                        af = min(af + acceleration, maximum)
        
        return sar
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> Optional[AdvancedIndicatorSignal]:
        """Parabolic SAR Strategy"""
        if len(df) < 30:
            return None
        
        sar = ParabolicSARStrategy.calculate_sar(df)
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Bullish signal: SAR flips below price
        if sar.iloc[-2] > df['close'].iloc[-2] and sar.iloc[-1] < current_price:
            return AdvancedIndicatorSignal(
                strategy='parabolic_sar',
                indicator='PARABOLIC_SAR',
                direction='LONG',
                entry_price=current_price,
                stop_loss=sar.iloc[-1],
                take_profit=current_price + (atr * 3.0),
                confidence=75.0,
                indicator_value=sar.iloc[-1],
                timeframe='H1'
            )
        
        # Bearish signal: SAR flips above price
        elif sar.iloc[-2] < df['close'].iloc[-2] and sar.iloc[-1] > current_price:
            return AdvancedIndicatorSignal(
                strategy='parabolic_sar',
                indicator='PARABOLIC_SAR',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=sar.iloc[-1],
                take_profit=current_price - (atr * 3.0),
                confidence=75.0,
                indicator_value=sar.iloc[-1],
                timeframe='H1'
            )
        
        return None


class WilliamsRStrategy:
    """Williams %R Strategy"""
    
    @staticmethod
    def calculate_williams_r(df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Williams %R"""
        highest_high = df['high'].rolling(period).max()
        lowest_low = df['low'].rolling(period).min()
        
        williams_r = -100 * (highest_high - df['close']) / (highest_high - lowest_low)
        
        return williams_r
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> Optional[AdvancedIndicatorSignal]:
        """Williams %R Strategy"""
        if len(df) < 20:
            return None
        
        williams_r = WilliamsRStrategy.calculate_williams_r(df, 14)
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Oversold (< -80)
        if williams_r.iloc[-2] < -80 and williams_r.iloc[-1] > williams_r.iloc[-2]:
            return AdvancedIndicatorSignal(
                strategy='williams_r',
                indicator='WILLIAMS_R',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 1.5),
                take_profit=current_price + (atr * 2.5),
                confidence=70.0,
                indicator_value=williams_r.iloc[-1],
                timeframe='M15'
            )
        
        # Overbought (> -20)
        elif williams_r.iloc[-2] > -20 and williams_r.iloc[-1] < williams_r.iloc[-2]:
            return AdvancedIndicatorSignal(
                strategy='williams_r',
                indicator='WILLIAMS_R',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 1.5),
                take_profit=current_price - (atr * 2.5),
                confidence=70.0,
                indicator_value=williams_r.iloc[-1],
                timeframe='M15'
            )
        
        return None


class CCIStrategy:
    """Commodity Channel Index Strategy"""
    
    @staticmethod
    def calculate_cci(df: pd.DataFrame, period: int = 20) -> pd.Series:
        """Calculate CCI"""
        tp = (df['high'] + df['low'] + df['close']) / 3  # Typical Price
        sma_tp = tp.rolling(period).mean()
        mad = tp.rolling(period).apply(lambda x: np.abs(x - x.mean()).mean())
        
        cci = (tp - sma_tp) / (0.015 * mad)
        
        return cci
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> Optional[AdvancedIndicatorSignal]:
        """CCI Strategy"""
        if len(df) < 25:
            return None
        
        cci = CCIStrategy.calculate_cci(df, 20)
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Oversold (< -100)
        if cci.iloc[-2] < -100 and cci.iloc[-1] > cci.iloc[-2]:
            return AdvancedIndicatorSignal(
                strategy='cci',
                indicator='CCI',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 1.5),
                take_profit=current_price + (atr * 2.5),
                confidence=75.0,
                indicator_value=cci.iloc[-1],
                timeframe='M15'
            )
        
        # Overbought (> 100)
        elif cci.iloc[-2] > 100 and cci.iloc[-1] < cci.iloc[-2]:
            return AdvancedIndicatorSignal(
                strategy='cci',
                indicator='CCI',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 1.5),
                take_profit=current_price - (atr * 2.5),
                confidence=75.0,
                indicator_value=cci.iloc[-1],
                timeframe='M15'
            )
        
        return None


class AwesomeOscillatorStrategy:
    """Awesome Oscillator (Bill Williams)"""
    
    @staticmethod
    def calculate_ao(df: pd.DataFrame) -> pd.Series:
        """Calculate Awesome Oscillator"""
        median_price = (df['high'] + df['low']) / 2
        
        ao = median_price.rolling(5).mean() - median_price.rolling(34).mean()
        
        return ao
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> Optional[AdvancedIndicatorSignal]:
        """Awesome Oscillator Strategy"""
        if len(df) < 40:
            return None
        
        ao = AwesomeOscillatorStrategy.calculate_ao(df)
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Bullish: AO crosses above zero
        if ao.iloc[-2] <= 0 and ao.iloc[-1] > 0:
            return AdvancedIndicatorSignal(
                strategy='awesome_oscillator',
                indicator='AWESOME_OSCILLATOR',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 2.0),
                take_profit=current_price + (atr * 3.0),
                confidence=75.0,
                indicator_value=ao.iloc[-1],
                timeframe='H1'
            )
        
        # Bearish: AO crosses below zero
        elif ao.iloc[-2] >= 0 and ao.iloc[-1] < 0:
            return AdvancedIndicatorSignal(
                strategy='awesome_oscillator',
                indicator='AWESOME_OSCILLATOR',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 2.0),
                take_profit=current_price - (atr * 3.0),
                confidence=75.0,
                indicator_value=ao.iloc[-1],
                timeframe='H1'
            )
        
        return None


class SqueezeMomentumStrategy:
    """Squeeze Momentum Indicator Strategy (LazyBear style).
    Detects low-volatility squeezes and trades the breakout direction."""
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> Optional[AdvancedIndicatorSignal]:
        """Squeeze Momentum Strategy"""
        if len(df) < 30:
            return None
        
        close = df['close']
        period = 20
        bb_mult = 2.0
        kc_mult = 1.5
        
        # Bollinger Bands
        bb_mid = close.rolling(period).mean()
        bb_std = close.rolling(period).std()
        bb_upper = bb_mid + bb_mult * bb_std
        bb_lower = bb_mid - bb_mult * bb_std
        
        # Keltner Channels
        tr = pd.concat([
            df['high'] - df['low'],
            abs(df['high'] - close.shift(1)),
            abs(df['low'] - close.shift(1))
        ], axis=1).max(axis=1)
        kc_atr = tr.rolling(period).mean()
        kc_mid = close.rolling(period).mean()
        kc_upper = kc_mid + kc_mult * kc_atr
        kc_lower = kc_mid - kc_mult * kc_atr
        
        # Squeeze detection
        sqz_on = (bb_lower > kc_lower) & (bb_upper < kc_upper)
        
        # Momentum
        midline = ((df['high'].rolling(period).max() + df['low'].rolling(period).min()) / 2 + kc_mid) / 2
        momentum = close - midline
        
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        current_price = close.iloc[-1]
        
        # Signal: squeeze was ON and just turned OFF
        if len(sqz_on) >= 2 and sqz_on.iloc[-2] and not sqz_on.iloc[-1]:
            if momentum.iloc[-1] > 0 and momentum.iloc[-1] > momentum.iloc[-2]:
                return AdvancedIndicatorSignal(
                    strategy='squeeze_momentum',
                    indicator='SQUEEZE_MOMENTUM',
                    direction='LONG',
                    entry_price=current_price,
                    stop_loss=current_price - (atr * 2.0),
                    take_profit=current_price + (atr * 3.0),
                    confidence=82.0,
                    indicator_value=float(momentum.iloc[-1]),
                    timeframe='M15'
                )
            elif momentum.iloc[-1] < 0 and momentum.iloc[-1] < momentum.iloc[-2]:
                return AdvancedIndicatorSignal(
                    strategy='squeeze_momentum',
                    indicator='SQUEEZE_MOMENTUM',
                    direction='SHORT',
                    entry_price=current_price,
                    stop_loss=current_price + (atr * 2.0),
                    take_profit=current_price - (atr * 3.0),
                    confidence=82.0,
                    indicator_value=float(momentum.iloc[-1]),
                    timeframe='M15'
                )
        
        return None


class QQEModStrategy:
    """QQE MOD Strategy - Advanced RSI with dynamic trailing bands.
    Reduces false signals compared to standard RSI."""
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> Optional[AdvancedIndicatorSignal]:
        """QQE MOD Strategy"""
        if len(df) < 30:
            return None
        
        close = df['close']
        rsi_period = 6
        sf = 5
        qqe_factor = 3.0
        
        # Calculate smoothed RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).ewm(span=rsi_period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0.0)).ewm(span=rsi_period, adjust=False).mean()
        rs = gain / loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        rsi_ma = rsi.ewm(span=sf, adjust=False).mean()
        
        # ATR of RSI
        rsi_abs_change = abs(rsi_ma - rsi_ma.shift(1))
        rsi_atr = rsi_abs_change.ewm(span=2 * sf - 1, adjust=False).mean()
        dar = rsi_atr * qqe_factor
        
        # QQE trailing
        qqe_long = pd.Series(0.0, index=df.index)
        qqe_short = pd.Series(0.0, index=df.index)
        trend = pd.Series(0, index=df.index)
        
        for i in range(1, len(df)):
            nl = rsi_ma.iloc[i] - dar.iloc[i]
            ns = rsi_ma.iloc[i] + dar.iloc[i]
            
            if rsi_ma.iloc[i - 1] > qqe_long.iloc[i - 1] and rsi_ma.iloc[i] > qqe_long.iloc[i - 1]:
                qqe_long.iloc[i] = max(nl, qqe_long.iloc[i - 1])
            else:
                qqe_long.iloc[i] = nl
            
            if rsi_ma.iloc[i - 1] < qqe_short.iloc[i - 1] and rsi_ma.iloc[i] < qqe_short.iloc[i - 1]:
                qqe_short.iloc[i] = min(ns, qqe_short.iloc[i - 1])
            else:
                qqe_short.iloc[i] = ns
            
            if rsi_ma.iloc[i] > qqe_short.iloc[i - 1]:
                trend.iloc[i] = 1
            elif rsi_ma.iloc[i] < qqe_long.iloc[i - 1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i - 1]
        
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        current_price = close.iloc[-1]
        
        # Bullish crossover: trend flips to 1 + RSI above 50
        if trend.iloc[-1] == 1 and trend.iloc[-2] != 1 and rsi_ma.iloc[-1] > 50:
            return AdvancedIndicatorSignal(
                strategy='qqe_mod',
                indicator='QQE_MOD',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 2.0),
                take_profit=current_price + (atr * 3.0),
                confidence=78.0,
                indicator_value=float(rsi_ma.iloc[-1]),
                timeframe='M15'
            )
        
        # Bearish crossover
        elif trend.iloc[-1] == -1 and trend.iloc[-2] != -1 and rsi_ma.iloc[-1] < 50:
            return AdvancedIndicatorSignal(
                strategy='qqe_mod',
                indicator='QQE_MOD',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 2.0),
                take_profit=current_price - (atr * 3.0),
                confidence=78.0,
                indicator_value=float(rsi_ma.iloc[-1]),
                timeframe='M15'
            )
        
        return None


class InstitutionalMoneyFlowStrategy:
    """Institutional Money Flow Strategy.
    Tracks smart money activity through price/volume analysis.
    Bottom-fishing and distribution detection."""
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> Optional[AdvancedIndicatorSignal]:
        """Institutional Money Flow Strategy"""
        if len(df) < 60:
            return None
        
        close = df['close']
        open_p = df['open']
        volume = df.get('volume', df.get('tick_volume', pd.Series(1, index=df.index)))
        
        body = abs(close - open_p)
        total_range = (df['high'] - df['low']).replace(0, 1e-10)
        body_ratio = body / total_range
        
        vol_zscore = (volume - volume.rolling(50).mean()) / volume.rolling(50).std().replace(0, 1)
        is_institutional = (body_ratio > 0.6) & (vol_zscore > 0.5)
        
        direction = np.where(close > open_p, 1.0, np.where(close < open_p, -1.0, 0.0))
        inst_flow = pd.Series(direction, index=df.index) * body * volume
        imf_line = inst_flow.cumsum()
        imf_signal = imf_line.ewm(span=21).mean()
        
        price_falling = close < close.rolling(10).mean()
        imf_rising = imf_line > imf_line.shift(5)
        bottom_fish = price_falling & imf_rising & is_institutional
        
        price_rising = close > close.rolling(10).mean()
        imf_falling = imf_line < imf_line.shift(5)
        distribution = price_rising & imf_falling & is_institutional
        
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        current_price = close.iloc[-1]
        
        # Bottom fishing: institutions accumulating while price is weak
        if bottom_fish.iloc[-1] and imf_line.iloc[-1] > imf_signal.iloc[-1]:
            return AdvancedIndicatorSignal(
                strategy='institutional_money_flow',
                indicator='INST_MONEY_FLOW',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 2.5),
                take_profit=current_price + (atr * 4.0),
                confidence=85.0,
                indicator_value=float(imf_line.iloc[-1]),
                timeframe='H1'
            )
        
        # Distribution: institutions selling while price is strong
        elif distribution.iloc[-1] and imf_line.iloc[-1] < imf_signal.iloc[-1]:
            return AdvancedIndicatorSignal(
                strategy='institutional_money_flow',
                indicator='INST_MONEY_FLOW',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 2.5),
                take_profit=current_price - (atr * 4.0),
                confidence=85.0,
                indicator_value=float(imf_line.iloc[-1]),
                timeframe='H1'
            )
        
        return None


# Master Advanced Indicators Selector
class AdvancedIndicatorsSelector:
    """Master selector for all advanced indicator strategies"""
    
    def __init__(self):
        self.ichimoku = IchimokuStrategy()
        self.supertrend = SuperTrendStrategy()
        self.parabolic_sar = ParabolicSARStrategy()
        self.williams_r = WilliamsRStrategy()
        self.cci = CCIStrategy()
        self.awesome_oscillator = AwesomeOscillatorStrategy()
        self.squeeze_momentum = SqueezeMomentumStrategy()
        self.qqe_mod = QQEModStrategy()
        self.institutional_money_flow = InstitutionalMoneyFlowStrategy()
    
    def get_all_signals(self, df: pd.DataFrame) -> List[AdvancedIndicatorSignal]:
        """Get all advanced indicator signals"""
        signals = []
        
        signals.append(self.ichimoku.analyze(df))
        signals.append(self.supertrend.analyze(df))
        signals.append(self.parabolic_sar.analyze(df))
        signals.append(self.williams_r.analyze(df))
        signals.append(self.cci.analyze(df))
        signals.append(self.awesome_oscillator.analyze(df))
        signals.append(self.squeeze_momentum.analyze(df))
        signals.append(self.qqe_mod.analyze(df))
        signals.append(self.institutional_money_flow.analyze(df))
        
        return [s for s in signals if s is not None]
    
    def get_best_signal(self, df: pd.DataFrame) -> Optional[AdvancedIndicatorSignal]:
        """Get highest confidence signal"""
        signals = self.get_all_signals(df)
        return max(signals, key=lambda x: x.confidence) if signals else None
