"""
Advanced Technical Indicators with All Accuracy Components
CRITICAL FOR PROFITABILITY
"""

import warnings

import pandas as pd
import numpy as np
from typing import Dict, Tuple
import talib


class AdvancedIndicators:
    """
    Advanced technical indicators with accuracy enhancements
    Includes all indicators from specification
    """
    
    def __init__(self, config: Dict = None):
        # Extract indicator settings from nested config or use defaults
        if config and 'strategy' in config and 'indicators' in config['strategy']:
            self.config = config['strategy']['indicators']
        elif config and 'ema_fast' in config:
            # Config already has indicator settings directly
            self.config = config
        else:
            self.config = self._default_config()
    
    def _default_config(self) -> Dict:
        return {
            'ema_fast': 8,
            'ema_medium': 21,
            'ema_slow': 50,
            'ema_trend': 200,
            'rsi_period': 14,
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'adx_period': 14,
            'atr_period': 14,
            'bb_period': 20,
            'bb_std': 2.0
        }
    
    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate ALL indicators for complete analysis
        Returns df with all indicator columns added
        """
        df = df.copy()
        
        # Suppress pandas PerformanceWarning from incremental column inserts.
        # The DataFrame is defragmented via .copy() before returning.
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', pd.errors.PerformanceWarning)
        
            # 1. TREND INDICATORS
            df = self._calculate_emas(df)
            df = self._calculate_adx(df)
            
            # 2. MOMENTUM INDICATORS
            df = self._calculate_rsi(df)
            df = self._calculate_macd(df)
            df = self._calculate_stochastic(df)
            df = self._calculate_williams_r(df)
            df = self._calculate_cci(df)
            df = self._calculate_roc(df)
            df = self._calculate_ultimate_oscillator(df)
            
            # 3. VOLATILITY INDICATORS
            df = self._calculate_bollinger_bands(df)
            df = self._calculate_atr(df)
            
            # 4. SUPPORT/RESISTANCE LEVELS
            df = self._calculate_pivot_points(df)
            
            # 5. VOLUME ANALYSIS (Tick Volume for Forex)
            df = self._calculate_volume_indicators(df)
            df = self._calculate_mfi(df)
            df = self._calculate_obv(df)
            df = self._calculate_awesome_oscillator(df)
            
            # 6. MARKET MICROSTRUCTURE
            df = self._calculate_tick_imbalance(df)
            df = self._calculate_vwap(df)
            
            # 7. HULL MOVING AVERAGE (reduces lag vs EMA)
            df = self._calculate_hma(df)
            
            # 8. VOLUME PROFILE (POC, HVN, Value Area)
            df = self._calculate_volume_profile(df)
            
            # 9. SQUEEZE MOMENTUM INDICATOR (BB inside Keltner + momentum)
            df = self._calculate_squeeze_momentum(df)
            
            # 10. QQE MOD (advanced RSI with smoothing filters)
            df = self._calculate_qqe_mod(df)
            
            # 11. INSTITUTIONAL MONEY FLOW (smart money tracker)
            df = self._calculate_institutional_money_flow(df)
            
            # 12. ADVANCED FEATURES
            df = self._calculate_advanced_features(df)
        
        # Defragment: single contiguous memory block after all column inserts
        return df.copy()
    
    def _calculate_emas(self, df: pd.DataFrame) -> pd.DataFrame:
        """EMA Ribbon: 8, 21, 50, 200"""
        df['ema_8'] = talib.EMA(df['close'], timeperiod=self.config.get('ema_fast', 8))
        df['ema_21'] = talib.EMA(df['close'], timeperiod=self.config.get('ema_medium', 21))
        df['ema_50'] = talib.EMA(df['close'], timeperiod=self.config.get('ema_slow', 50))
        df['ema_200'] = talib.EMA(df['close'], timeperiod=self.config.get('ema_trend', 200))
        
        # EMA alignment score (-1 to 1)
        df['ema_bullish_align'] = (
            (df['ema_8'] > df['ema_21']).astype(int) +
            (df['ema_21'] > df['ema_50']).astype(int) +
            (df['ema_50'] > df['ema_200']).astype(int)
        ) / 3
        
        df['ema_bearish_align'] = (
            (df['ema_8'] < df['ema_21']).astype(int) +
            (df['ema_21'] < df['ema_50']).astype(int) +
            (df['ema_50'] < df['ema_200']).astype(int)
        ) / 3
        
        return df
    
    def _calculate_adx(self, df: pd.DataFrame) -> pd.DataFrame:
        """ADX for trend strength with +DI and -DI"""
        adx_period = self.config.get('adx_period', 14)
        df['adx'] = talib.ADX(df['high'], df['low'], df['close'], 
                             timeperiod=adx_period)
        df['plus_di'] = talib.PLUS_DI(df['high'], df['low'], df['close'], 
                                      timeperiod=adx_period)
        df['minus_di'] = talib.MINUS_DI(df['high'], df['low'], df['close'], 
                                        timeperiod=adx_period)
        
        # ADX strength classification
        df['adx_strength'] = pd.cut(df['adx'], 
                                    bins=[0, 20, 25, 40, 100],
                                    labels=['weak', 'moderate', 'strong', 'very_strong'])
        
        # Trend direction from DI
        df['di_trend'] = np.where(df['plus_di'] > df['minus_di'], 1, -1)
        
        return df
    
    def _calculate_rsi(self, df: pd.DataFrame) -> pd.DataFrame:
        """RSI with divergence detection"""
        df['rsi'] = talib.RSI(df['close'], timeperiod=self.config.get('rsi_period', 14))
        
        # RSI zones
        df['rsi_oversold'] = df['rsi'] < 30
        df['rsi_overbought'] = df['rsi'] > 70
        df['rsi_neutral'] = (df['rsi'] >= 40) & (df['rsi'] <= 60)
        
        # RSI divergence (simplified)
        df['rsi_bullish_div'] = self._detect_bullish_divergence(df['close'], df['rsi'])
        df['rsi_bearish_div'] = self._detect_bearish_divergence(df['close'], df['rsi'])
        
        return df
    
    def _calculate_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """MACD with histogram and signal crossovers"""
        df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(
            df['close'],
            fastperiod=self.config.get('macd_fast', 12),
            slowperiod=self.config.get('macd_slow', 26),
            signalperiod=self.config.get('macd_signal', 9)
        )
        
        # MACD crossovers
        df['macd_bullish_cross'] = (
            (df['macd'] > df['macd_signal']) &
            (df['macd'].shift(1) <= df['macd_signal'].shift(1))
        )
        
        df['macd_bearish_cross'] = (
            (df['macd'] < df['macd_signal']) &
            (df['macd'].shift(1) >= df['macd_signal'].shift(1))
        )
        
        # MACD histogram momentum
        df['macd_hist_increasing'] = df['macd_hist'] > df['macd_hist'].shift(1)
        
        return df
    
    def _calculate_stochastic(self, df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> pd.DataFrame:
        """
        Stochastic Oscillator - Powerful for scalping
        Shows overbought/oversold conditions accurately
        """
        df['stoch_k'], df['stoch_d'] = talib.STOCH(
            df['high'], df['low'], df['close'],
            fastk_period=k_period,
            slowk_period=3,
            slowk_matype=0,
            slowd_period=d_period,
            slowd_matype=0
        )
        
        df['stoch_oversold'] = df['stoch_k'] < 20
        df['stoch_overbought'] = df['stoch_k'] > 80
        df['stoch_bullish_cross'] = (
            (df['stoch_k'] > df['stoch_d']) & 
            (df['stoch_k'].shift(1) <= df['stoch_d'].shift(1))
        )
        df['stoch_bearish_cross'] = (
            (df['stoch_k'] < df['stoch_d']) & 
            (df['stoch_k'].shift(1) >= df['stoch_d'].shift(1))
        )
        
        return df
    
    def _calculate_williams_r(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """Williams %R - Shows overbought/oversold, Range: -100 to 0"""
        df['williams_r'] = talib.WILLR(df['high'], df['low'], df['close'], timeperiod=period)
        df['willr_oversold'] = df['williams_r'] < -80
        df['willr_overbought'] = df['williams_r'] > -20
        return df
    
    def _calculate_cci(self, df: pd.DataFrame, period: int = 20) -> pd.DataFrame:
        """CCI - Commodity Channel Index, Identifies cyclical trends"""
        df['cci'] = talib.CCI(df['high'], df['low'], df['close'], timeperiod=period)
        df['cci_oversold'] = df['cci'] < -100
        df['cci_overbought'] = df['cci'] > 100
        df['cci_bullish'] = df['cci'] > 0
        df['cci_bearish'] = df['cci'] < 0
        return df
    
    def _calculate_roc(self, df: pd.DataFrame, period: int = 10) -> pd.DataFrame:
        """ROC - Rate of Change, Measures momentum"""
        df['roc'] = talib.ROC(df['close'], timeperiod=period)
        df['roc_bullish'] = df['roc'] > 0
        df['roc_bearish'] = df['roc'] < 0
        df['roc_strong_bullish'] = df['roc'] > 2
        df['roc_strong_bearish'] = df['roc'] < -2
        return df
    
    def _calculate_ultimate_oscillator(self, df: pd.DataFrame) -> pd.DataFrame:
        """Ultimate Oscillator - Combines 3 timeframes, Very reliable"""
        df['ult_osc'] = talib.ULTOSC(
            df['high'], df['low'], df['close'],
            timeperiod1=7, timeperiod2=14, timeperiod3=28
        )
        df['ult_oversold'] = df['ult_osc'] < 30
        df['ult_overbought'] = df['ult_osc'] > 70
        df['ult_bullish'] = df['ult_osc'] > 50
        return df
    
    def _calculate_mfi(self, df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """MFI - Money Flow Index (volume-weighted RSI)"""
        volume = df.get('tick_volume', pd.Series(1, index=df.index))
        df['mfi'] = talib.MFI(df['high'], df['low'], df['close'], volume, timeperiod=period)
        df['mfi_oversold'] = df['mfi'] < 20
        df['mfi_overbought'] = df['mfi'] > 80
        df['mfi_bullish'] = df['mfi'] > 50
        return df
    
    def _calculate_obv(self, df: pd.DataFrame) -> pd.DataFrame:
        """OBV - On Balance Volume"""
        volume = df.get('tick_volume', pd.Series(1, index=df.index))
        df['obv'] = talib.OBV(df['close'], volume)
        df['obv_sma'] = df['obv'].rolling(20).mean()
        df['obv_bullish'] = df['obv'] > df['obv_sma']
        df['obv_bearish'] = df['obv'] < df['obv_sma']
        return df
    
    def _calculate_awesome_oscillator(self, df: pd.DataFrame) -> pd.DataFrame:
        """Awesome Oscillator - Momentum indicator"""
        midpoint = (df['high'] + df['low']) / 2
        df['ao'] = midpoint.rolling(5).mean() - midpoint.rolling(34).mean()
        df['ao_bullish'] = df['ao'] > 0
        df['ao_bearish'] = df['ao'] < 0
        df['ao_increasing'] = df['ao'] > df['ao'].shift(1)
        df['ao_decreasing'] = df['ao'] < df['ao'].shift(1)
        return df
    
    def _calculate_bollinger_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        """Bollinger Bands with width and position"""
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
            df['close'],
            timeperiod=self.config.get('bb_period', 20),
            nbdevup=self.config.get('bb_std', 2.0),
            nbdevdn=self.config.get('bb_std', 2.0)
        )
        
        # BB Width (volatility measure)
        df['bb_width'] = (df['bb_upper'] - df['bb_lower']) / df['bb_middle']
        
        # Price position in BB (0 = lower, 0.5 = middle, 1 = upper)
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        # BB squeeze (volatility contraction)
        df['bb_squeeze'] = df['bb_width'] < df['bb_width'].rolling(20).mean() * 0.7
        
        return df
    
    def _calculate_atr(self, df: pd.DataFrame) -> pd.DataFrame:
        """ATR for volatility and dynamic stops"""
        df['atr'] = talib.ATR(df['high'], df['low'], df['close'], 
                             timeperiod=self.config.get('atr_period', 14))
        
        # ATR ratio (current vs average)
        df['atr_ratio'] = df['atr'] / df['atr'].rolling(20).mean()
        
        # ATR as % of price
        df['atr_pct'] = (df['atr'] / df['close']) * 100
        
        # Volatility classification
        df['volatility'] = pd.cut(df['atr_ratio'],
                                  bins=[0, 0.7, 1.3, 2.0, 10],
                                  labels=['low', 'normal', 'high', 'extreme'])
        
        return df
    
    def _calculate_pivot_points(self, df: pd.DataFrame) -> pd.DataFrame:
        """Daily pivot points and support/resistance levels"""
        # Standard pivot points
        df['pivot'] = (df['high'].shift(1) + df['low'].shift(1) + df['close'].shift(1)) / 3
        df['r1'] = 2 * df['pivot'] - df['low'].shift(1)
        df['s1'] = 2 * df['pivot'] - df['high'].shift(1)
        df['r2'] = df['pivot'] + (df['high'].shift(1) - df['low'].shift(1))
        df['s2'] = df['pivot'] - (df['high'].shift(1) - df['low'].shift(1))
        
        return df
    
    def _calculate_volume_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Volume analysis (tick volume for forex)"""
        if 'volume' not in df.columns:
            df['volume'] = 1  # Placeholder if no volume data
        
        # Volume ratio
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        
        # High volume bars
        df['high_volume'] = df['volume'] > df['volume'].rolling(20).mean() * 1.5
        
        # On-Balance Volume
        df['obv'] = talib.OBV(df['close'], df['volume'])
        
        return df
    
    def _calculate_tick_imbalance(self, df: pd.DataFrame) -> pd.DataFrame:
        """Track buy/sell pressure from price changes"""
        price_changes = df['close'].diff()
        volume = df.get('volume', pd.Series(1, index=df.index))
        
        # Positive = buying pressure, Negative = selling pressure
        imbalance = np.where(price_changes > 0, volume,
                           np.where(price_changes < 0, -volume, 0))
        
        df['tick_imbalance'] = pd.Series(imbalance, index=df.index).rolling(20).sum()
        df['tick_imbalance_ratio'] = df['tick_imbalance'] / df['volume'].rolling(20).sum()
        
        return df
    
    def _calculate_vwap(self, df: pd.DataFrame) -> pd.DataFrame:
        """Volume Weighted Average Price"""
        volume = df.get('volume', pd.Series(1, index=df.index))
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        
        df['vwap'] = (volume * typical_price).cumsum() / volume.cumsum()
        df['price_vs_vwap'] = (df['close'] - df['vwap']) / df['vwap']
        
        return df
    
    def _calculate_hma(self, df: pd.DataFrame, period: int = 21) -> pd.DataFrame:
        """Hull Moving Average - reduces lag while maintaining smoothness.
        HMA = WMA(2*WMA(n/2) - WMA(n), sqrt(n))"""
        half_period = max(int(period / 2), 1)
        sqrt_period = max(int(np.sqrt(period)), 1)
        
        close = df['close']
        
        # WMA helper
        def _wma(series, p):
            weights = np.arange(1, p + 1, dtype=float)
            return series.rolling(p).apply(lambda x: np.dot(x, weights) / weights.sum(), raw=True)
        
        wma_half = _wma(close, half_period)
        wma_full = _wma(close, period)
        diff = 2 * wma_half - wma_full
        df['hma'] = _wma(diff, sqrt_period)
        
        # HMA trend direction
        df['hma_trend'] = np.where(df['hma'] > df['hma'].shift(1), 1,
                                   np.where(df['hma'] < df['hma'].shift(1), -1, 0))
        df['price_vs_hma'] = np.where(close > df['hma'], 1, -1)
        
        return df
    
    def _calculate_volume_profile(self, df: pd.DataFrame, bins: int = 24) -> pd.DataFrame:
        """Volume Profile - identifies POC, High Volume Nodes, Value Area.
        Shows where the most trading occurred at specific price levels."""
        volume = df.get('volume', df.get('tick_volume', pd.Series(1, index=df.index)))
        lookback = min(100, len(df))
        recent = df.iloc[-lookback:]
        recent_vol = volume.iloc[-lookback:]
        
        price_min = recent['low'].min()
        price_max = recent['high'].max()
        
        if price_max <= price_min or lookback < 10:
            df['vp_poc'] = df['close']  # Fallback
            df['vp_value_area_high'] = price_max
            df['vp_value_area_low'] = price_min
            df['vp_at_poc'] = False
            df['vp_at_hvn'] = False
            return df
        
        bin_edges = np.linspace(price_min, price_max, bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        # Distribute volume into price bins
        vol_profile = np.zeros(bins)
        for i in range(len(recent)):
            bar_low = recent['low'].iloc[i]
            bar_high = recent['high'].iloc[i]
            bar_vol = float(recent_vol.iloc[i])
            for b in range(bins):
                if bin_edges[b + 1] >= bar_low and bin_edges[b] <= bar_high:
                    vol_profile[b] += bar_vol
        
        # POC = price level with highest volume
        poc_idx = np.argmax(vol_profile)
        poc_price = float(bin_centers[poc_idx])
        
        # Value Area (70% of total volume around POC)
        total_vol = vol_profile.sum()
        if total_vol > 0:
            sorted_idx = np.argsort(vol_profile)[::-1]
            cumvol = 0.0
            va_indices = []
            for idx in sorted_idx:
                va_indices.append(idx)
                cumvol += vol_profile[idx]
                if cumvol >= total_vol * 0.70:
                    break
            va_high = float(bin_edges[max(va_indices) + 1])
            va_low = float(bin_edges[min(va_indices)])
        else:
            va_high = price_max
            va_low = price_min
        
        # High Volume Nodes (bins with volume > 1.5x average)
        avg_vol = vol_profile.mean()
        hvn_mask = vol_profile > avg_vol * 1.5
        
        df['vp_poc'] = poc_price
        df['vp_value_area_high'] = va_high
        df['vp_value_area_low'] = va_low
        
        # Price proximity to POC and HVN
        current_price = df['close']
        price_range = price_max - price_min
        poc_distance = abs(current_price - poc_price) / max(price_range, 1e-10)
        df['vp_at_poc'] = poc_distance < 0.05  # Within 5% of range from POC
        
        # Check if price is at any HVN
        df['vp_at_hvn'] = False
        for b in range(bins):
            if hvn_mask[b]:
                hvn_low = bin_edges[b]
                hvn_high = bin_edges[b + 1]
                df['vp_at_hvn'] = df['vp_at_hvn'] | (
                    (current_price >= hvn_low) & (current_price <= hvn_high)
                )
        
        return df
    
    def _calculate_squeeze_momentum(self, df: pd.DataFrame) -> pd.DataFrame:
        """Squeeze Momentum Indicator (LazyBear style).
        Detects when Bollinger Bands are INSIDE Keltner Channels (the squeeze),
        then uses linear regression momentum to determine breakout direction."""
        period = 20
        bb_mult = 2.0
        kc_mult = 1.5
        
        close = df['close']
        
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
        
        # Squeeze: BB inside KC
        df['sqz_on'] = (bb_lower > kc_lower) & (bb_upper < kc_upper)
        df['sqz_off'] = ~df['sqz_on']
        
        # Momentum (linear regression of close - midline)
        midline = (df['high'].rolling(period).max() + df['low'].rolling(period).min()) / 2
        midline = (midline + kc_mid) / 2
        val = close - midline
        
        # Simple momentum approximation (rate of change of val)
        df['sqz_momentum'] = val
        df['sqz_momentum_rising'] = val > val.shift(1)
        
        # Signal: squeeze just released + momentum direction
        df['sqz_fired'] = df['sqz_on'].shift(1) & df['sqz_off']
        df['sqz_bullish'] = df['sqz_fired'] & (df['sqz_momentum'] > 0)
        df['sqz_bearish'] = df['sqz_fired'] & (df['sqz_momentum'] < 0)
        
        return df
    
    def _calculate_qqe_mod(self, df: pd.DataFrame) -> pd.DataFrame:
        """QQE MOD (Quantitative Qualitative Estimation Modified).
        Advanced RSI with smoothing filters to reduce false signals.
        Combines fast and slow QQE lines for precise momentum signals."""
        rsi_period = 6
        sf = 5  # Smoothing factor
        qqe_factor = 3.0
        
        close = df['close']
        
        # Calculate RSI
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0).ewm(span=rsi_period, adjust=False).mean()
        loss = (-delta.where(delta < 0, 0.0)).ewm(span=rsi_period, adjust=False).mean()
        rs = gain / loss.replace(0, 1e-10)
        rsi = 100 - (100 / (1 + rs))
        
        # Smooth RSI
        rsi_ma = rsi.ewm(span=sf, adjust=False).mean()
        
        # ATR of RSI for dynamic bands
        rsi_abs_change = abs(rsi_ma - rsi_ma.shift(1))
        rsi_atr = rsi_abs_change.ewm(span=2 * sf - 1, adjust=False).mean()
        dar = rsi_atr * qqe_factor
        
        # QQE line (dynamic trailing of smoothed RSI)
        qqe_long = pd.Series(0.0, index=df.index)
        qqe_short = pd.Series(0.0, index=df.index)
        trend = pd.Series(0, index=df.index)
        
        for i in range(1, len(df)):
            new_long = rsi_ma.iloc[i] - dar.iloc[i]
            new_short = rsi_ma.iloc[i] + dar.iloc[i]
            
            if rsi_ma.iloc[i - 1] > qqe_long.iloc[i - 1] and rsi_ma.iloc[i] > qqe_long.iloc[i - 1]:
                qqe_long.iloc[i] = max(new_long, qqe_long.iloc[i - 1])
            else:
                qqe_long.iloc[i] = new_long
            
            if rsi_ma.iloc[i - 1] < qqe_short.iloc[i - 1] and rsi_ma.iloc[i] < qqe_short.iloc[i - 1]:
                qqe_short.iloc[i] = min(new_short, qqe_short.iloc[i - 1])
            else:
                qqe_short.iloc[i] = new_short
            
            if rsi_ma.iloc[i] > qqe_short.iloc[i - 1]:
                trend.iloc[i] = 1
            elif rsi_ma.iloc[i] < qqe_long.iloc[i - 1]:
                trend.iloc[i] = -1
            else:
                trend.iloc[i] = trend.iloc[i - 1]
        
        df['qqe_rsi_smooth'] = rsi_ma
        df['qqe_line'] = np.where(trend == 1, qqe_long, qqe_short)
        df['qqe_trend'] = trend
        df['qqe_bullish'] = (trend == 1) & (trend.shift(1) != 1)
        df['qqe_bearish'] = (trend == -1) & (trend.shift(1) != -1)
        df['qqe_above_50'] = rsi_ma > 50
        
        return df
    
    def _calculate_institutional_money_flow(self, df: pd.DataFrame) -> pd.DataFrame:
        """Institutional Money Flow indicator.
        Estimates smart money activity by analyzing price/volume relationships.
        Large-body candles with high volume = institutional activity."""
        close = df['close']
        open_p = df['open']
        high = df['high']
        low = df['low']
        volume = df.get('volume', df.get('tick_volume', pd.Series(1, index=df.index)))
        
        # Body ratio (large bodies = institutional, small bodies = retail)
        body = abs(close - open_p)
        total_range = (high - low).replace(0, 1e-10)
        body_ratio = body / total_range
        
        # Institutional activity score
        # High volume + large body + directional = institutional
        vol_zscore = (volume - volume.rolling(50).mean()) / volume.rolling(50).std().replace(0, 1)
        is_institutional = (body_ratio > 0.6) & (vol_zscore > 0.5)
        
        # Directional money flow
        direction = np.where(close > open_p, 1.0, np.where(close < open_p, -1.0, 0.0))
        inst_flow = pd.Series(direction, index=df.index) * body * volume
        
        # Cumulative institutional money flow line
        df['imf_line'] = inst_flow.cumsum()
        df['imf_signal'] = df['imf_line'].ewm(span=21).mean()
        df['imf_bullish'] = df['imf_line'] > df['imf_signal']
        df['imf_bearish'] = df['imf_line'] < df['imf_signal']
        
        # Bottom fishing signal (IMF rising while price falling)
        price_falling = close < close.rolling(10).mean()
        imf_rising = df['imf_line'] > df['imf_line'].shift(5)
        df['imf_bottom_fish'] = price_falling & imf_rising & is_institutional
        
        # Distribution signal (IMF falling while price rising)
        price_rising = close > close.rolling(10).mean()
        imf_falling = df['imf_line'] < df['imf_line'].shift(5)
        df['imf_distribution'] = price_rising & imf_falling & is_institutional
        
        df['imf_institutional_active'] = is_institutional
        
        return df
    
    def _calculate_advanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Advanced features for ML and accuracy"""
        # Price action features
        df['high_low_ratio'] = df['high'] / df['low']
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'])
        
        # Momentum features
        df['momentum_1h'] = df['close'].pct_change(4)  # 4 periods
        df['momentum_4h'] = df['close'].pct_change(16)  # 16 periods
        
        # Mean reversion features
        df['price_vs_ema21'] = df['close'] / df['ema_21']
        df['price_vs_bb_mid'] = (df['close'] - df['bb_middle']) / (df['bb_upper'] - df['bb_lower'])
        
        # Volatility features
        df['volatility_ratio'] = df['atr'].rolling(20).std() / df['atr'].rolling(20).mean()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        df['realized_volatility'] = df['log_returns'].rolling(20).std() * np.sqrt(252)
        
        return df
    
    def _detect_bullish_divergence(self, price: pd.Series, indicator: pd.Series, 
                                   lookback: int = 20) -> pd.Series:
        """Detect bullish divergence (price makes lower low, indicator makes higher low)"""
        divergence = pd.Series(False, index=price.index)
        
        # CRITICAL FIX: Use proper peak/trough detection instead of window min/max
        for i in range(lookback + 5, len(price)):
            # Find local troughs (lows) in the lookback window
            price_troughs = self._find_local_troughs(price.iloc[i-lookback:i+1], window=5)
            
            if len(price_troughs) < 2:
                continue
            
            # Get the last two price troughs
            trough1_idx = price_troughs[-2]
            trough2_idx = price_troughs[-1]
            
            # Ensure troughs are in valid range
            if trough1_idx >= len(ind_window := indicator.iloc[i-lookback:i+1]):
                continue
            
            price1 = price.iloc[i-lookback + trough1_idx]
            price2 = price.iloc[i-lookback + trough2_idx]
            ind1 = indicator.iloc[i-lookback + trough1_idx]
            ind2 = indicator.iloc[i-lookback + trough2_idx]
            
            # Bullish divergence: price making lower low, indicator making higher low
            if price2 < price1 and ind2 > ind1:
                divergence.iloc[i] = True
        
        return divergence
    
    def _find_local_troughs(self, series: pd.Series, window: int = 5) -> list:
        """Find local minimum points (troughs) in a series"""
        troughs = []
        for i in range(window, len(series) - window):
            local_min = True
            for j in range(i - window, i + window + 1):
                if j != i and series.iloc[j] < series.iloc[i]:
                    local_min = False
                    break
            if local_min:
                troughs.append(i)
        return troughs
    
    def _find_local_peaks(self, series: pd.Series, window: int = 5) -> list:
        """Find local maximum points (peaks) in a series"""
        peaks = []
        for i in range(window, len(series) - window):
            local_max = True
            for j in range(i - window, i + window + 1):
                if j != i and series.iloc[j] > series.iloc[i]:
                    local_max = False
                    break
            if local_max:
                peaks.append(i)
        return peaks
    
    def _detect_bearish_divergence(self, price: pd.Series, indicator: pd.Series,
                                   lookback: int = 20) -> pd.Series:
        """Detect bearish divergence (price makes higher high, indicator makes lower high)"""
        divergence = pd.Series(False, index=price.index)
        
        # CRITICAL FIX: Use proper peak/trough detection instead of window min/max
        for i in range(lookback + 5, len(price)):
            # Find local peaks (highs) in the lookback window
            price_peaks = self._find_local_peaks(price.iloc[i-lookback:i+1], window=5)
            
            if len(price_peaks) < 2:
                continue
            
            # Get the last two price peaks
            peak1_idx = price_peaks[-2]
            peak2_idx = price_peaks[-1]
            
            # Ensure peaks are in valid range
            if peak1_idx >= len(ind_window := indicator.iloc[i-lookback:i+1]):
                continue
            
            price1 = price.iloc[i-lookback + peak1_idx]
            price2 = price.iloc[i-lookback + peak2_idx]
            ind1 = indicator.iloc[i-lookback + peak1_idx]
            ind2 = indicator.iloc[i-lookback + peak2_idx]
            
            # Bearish divergence: price making higher high, indicator making lower high
            if price2 > price1 and ind2 < ind1:
                divergence.iloc[i] = True
        
        return divergence
    
    def get_indicator_alignment(self, df: pd.DataFrame) -> Dict:
        """
        Check alignment of ALL indicators for signal confirmation.
        Uses proper indicator combinations:
        - Trend category: EMA alignment, HMA trend, ADX strength
        - Momentum category: RSI zone, MACD histogram, QQE MOD trend
        - Volatility category: BB position, Squeeze Momentum state
        - Volume category: Volume Profile (POC/HVN), Institutional Money Flow
        Returns dict with scores and signals.
        """
        last = df.iloc[-1]
        
        # Helper for safe column access
        def _get(col, default=0):
            return last.get(col, default) if col in last.index else default
        
        signals = {
            # TREND indicators
            'ema_bullish': _get('ema_bullish_align', 0) > 0.66,
            'ema_bearish': _get('ema_bearish_align', 0) > 0.66,
            'hma_bullish': _get('hma_trend', 0) == 1 and _get('price_vs_hma', 0) == 1,
            'hma_bearish': _get('hma_trend', 0) == -1 and _get('price_vs_hma', 0) == -1,
            'adx_strong': _get('adx', 0) > 25,
            # MOMENTUM indicators
            'rsi_bullish': 40 < _get('rsi', 50) < 70,
            'rsi_bearish': 30 < _get('rsi', 50) < 60,
            'macd_bullish': _get('macd_hist', 0) > 0,
            'macd_bearish': _get('macd_hist', 0) < 0,
            'qqe_bullish': _get('qqe_trend', 0) == 1 and _get('qqe_above_50', False),
            'qqe_bearish': _get('qqe_trend', 0) == -1 and not _get('qqe_above_50', True),
            # VOLATILITY indicators
            'bb_bullish': _get('bb_position', 0.5) > 0.5,
            'bb_bearish': _get('bb_position', 0.5) < 0.5,
            'sqz_bullish': bool(_get('sqz_bullish', False)),
            'sqz_bearish': bool(_get('sqz_bearish', False)),
            'volatility_normal': _get('volatility', 'normal') in ['normal', 'high'],
            # VOLUME indicators
            'vp_at_poc': bool(_get('vp_at_poc', False)),
            'vp_at_hvn': bool(_get('vp_at_hvn', False)),
            'imf_bullish': bool(_get('imf_bullish', False)),
            'imf_bearish': bool(_get('imf_bearish', False)),
            'imf_bottom_fish': bool(_get('imf_bottom_fish', False)),
            'imf_distribution': bool(_get('imf_distribution', False)),
        }
        
        # Weighted scoring: Trend(3) + Momentum(3) + Volatility(2) + Volume(2) = 10 max
        bullish_score = sum([
            signals['ema_bullish'],           # Trend
            signals['hma_bullish'],           # Trend
            signals['adx_strong'],            # Trend strength
            signals['rsi_bullish'],           # Momentum
            signals['macd_bullish'],          # Momentum
            signals['qqe_bullish'],           # Momentum
            signals['bb_bullish'],            # Volatility
            signals['volatility_normal'],     # Volatility
            signals['imf_bullish'],           # Volume/Smart Money
            signals['vp_at_poc'] or signals['vp_at_hvn'],  # Volume Profile
        ])
        
        bearish_score = sum([
            signals['ema_bearish'],
            signals['hma_bearish'],
            signals['adx_strong'],
            signals['rsi_bearish'],
            signals['macd_bearish'],
            signals['qqe_bearish'],
            signals['bb_bearish'],
            signals['volatility_normal'],
            signals['imf_bearish'],
            signals['vp_at_poc'] or signals['vp_at_hvn'],
        ])
        
        max_score = 10
        
        return {
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'max_score': max_score,
            'bullish_pct': (bullish_score / max_score) * 100,
            'bearish_pct': (bearish_score / max_score) * 100,
            'signals': signals,
            'direction': 1 if bullish_score > bearish_score else -1 if bearish_score > bullish_score else 0,
            'squeeze_active': bool(_get('sqz_on', False)),
            'institutional_active': bool(_get('imf_institutional_active', False)),
        }
    
    def detect_trend(self, df: pd.DataFrame) -> Dict:
        """
        Detect current trend direction and strength
        
        Returns:
            Dict with trend direction, strength, and confidence
        """
        if len(df) < 50:
            return {'direction': 'neutral', 'strength': 0, 'confidence': 0}
        
        last = df.iloc[-1]
        
        # Check EMA alignment
        ema_bullish = last.get('ema_bullish_align', 0) > 0.66
        ema_bearish = last.get('ema_bearish_align', 0) > 0.66
        
        # Check ADX for trend strength
        adx = last.get('adx', 0)
        
        # Check price vs EMAs
        price = last['close']
        above_ema_200 = price > last.get('ema_200', price)
        
        # Determine direction
        if ema_bullish and above_ema_200:
            direction = 'bullish'
            strength = min(adx / 40, 1.0)  # Normalize to 0-1
        elif ema_bearish and not above_ema_200:
            direction = 'bearish'
            strength = min(adx / 40, 1.0)
        else:
            direction = 'neutral'
            strength = 0.3
        
        # Confidence based on ADX
        if adx > 30:
            confidence = 0.9
        elif adx > 25:
            confidence = 0.7
        elif adx > 20:
            confidence = 0.5
        else:
            confidence = 0.3
        
        return {
            'direction': direction,
            'strength': strength,
            'confidence': confidence,
            'adx': adx,
            'ema_aligned': ema_bullish or ema_bearish
        }
