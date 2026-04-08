"""
ML Feature Engineering - Creates features that improve accuracy
CRITICAL FOR MACHINE LEARNING MODELS
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime


class FeatureEngineer:
    """
    Create comprehensive ML features from price data
    Includes price action, momentum, volatility, time-based, and correlation features
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.lookback_periods = self.config.get('lookback_periods', [5, 10, 20, 50, 100])
    
    def create_ml_features(self, df: pd.DataFrame, pair: str = None) -> pd.DataFrame:
        """
        Create all ML features
        
        Args:
            df: DataFrame with OHLCV data and indicators
            pair: Currency pair name (optional, for correlation features)
        
        Returns:
            DataFrame with ML features added
        """
        df = df.copy()
        
        # 1. PRICE ACTION FEATURES
        df = self._create_price_action_features(df)
        
        # 2. MOMENTUM FEATURES
        df = self._create_momentum_features(df)
        
        # 3. MEAN REVERSION FEATURES
        df = self._create_mean_reversion_features(df)
        
        # 4. VOLATILITY FEATURES
        df = self._create_volatility_features(df)
        
        # 5. TIME-BASED FEATURES
        df = self._create_time_features(df)
        
        # 6. MARKET MICROSTRUCTURE
        df = self._create_microstructure_features(df)
        
        # 7. PATTERN FEATURES
        df = self._create_pattern_features(df)
        
        # Drop NaN rows from feature creation
        df = df.dropna()
        
        return df
    
    def _create_price_action_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Price action features"""
        # High/Low ratio
        df['high_low_ratio'] = df['high'] / df['low']
        
        # Close position in bar (0 = low, 1 = high)
        df['close_position'] = (df['close'] - df['low']) / (df['high'] - df['low'] + 1e-10)
        
        # Bar range as % of close
        df['bar_range_pct'] = ((df['high'] - df['low']) / df['close']) * 100
        
        # Upper/Lower shadows
        df['upper_shadow'] = df['high'] - df[['open', 'close']].max(axis=1)
        df['lower_shadow'] = df[['open', 'close']].min(axis=1) - df['low']
        df['shadow_ratio'] = df['upper_shadow'] / (df['lower_shadow'] + 1e-10)
        
        # Body size
        df['body_size'] = abs(df['close'] - df['open'])
        df['body_pct'] = (df['body_size'] / (df['high'] - df['low'] + 1e-10)) * 100
        
        # Gaps
        df['gap'] = df['open'] - df['close'].shift(1)
        df['gap_pct'] = (df['gap'] / df['close'].shift(1)) * 100
        
        return df
    
    def _create_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Momentum features across multiple timeframes"""
        # Returns over different periods
        for period in self.lookback_periods:
            df[f'return_{period}'] = df['close'].pct_change(period)
            df[f'log_return_{period}'] = np.log(df['close'] / df['close'].shift(period))
        
        # Momentum strength
        df['momentum_strength'] = df['return_20'].abs() / df['return_5'].abs()
        
        # Rate of change
        for period in [5, 10, 20]:
            df[f'roc_{period}'] = ((df['close'] - df['close'].shift(period)) / 
                                   df['close'].shift(period)) * 100
        
        # Price acceleration (2nd derivative)
        df['acceleration'] = df['close'].diff().diff()
        
        # Momentum consistency
        df['momentum_consistency'] = (
            (df['return_5'] > 0).astype(int) +
            (df['return_10'] > 0).astype(int) +
            (df['return_20'] > 0).astype(int)
        ) / 3
        
        return df
    
    def _create_mean_reversion_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Mean reversion features"""
        # Distance from moving averages
        if 'ema_21' in df.columns:
            df['price_vs_ema21'] = (df['close'] / df['ema_21']) - 1
            df['price_vs_ema50'] = (df['close'] / df['ema_50']) - 1 if 'ema_50' in df.columns else 0
            df['price_vs_ema200'] = (df['close'] / df['ema_200']) - 1 if 'ema_200' in df.columns else 0
        
        # Distance from Bollinger Bands
        if 'bb_middle' in df.columns:
            df['price_vs_bb_mid'] = (df['close'] - df['bb_middle']) / (df['bb_upper'] - df['bb_lower'] + 1e-10)
            df['bb_distance_upper'] = (df['bb_upper'] - df['close']) / df['close']
            df['bb_distance_lower'] = (df['close'] - df['bb_lower']) / df['close']
        
        # Z-score (how many std devs from mean)
        for period in [20, 50]:
            mean = df['close'].rolling(period).mean()
            std = df['close'].rolling(period).std()
            df[f'zscore_{period}'] = (df['close'] - mean) / (std + 1e-10)
        
        # Overbought/Oversold based on RSI
        if 'rsi' in df.columns:
            df['rsi_oversold'] = (df['rsi'] < 30).astype(int)
            df['rsi_overbought'] = (df['rsi'] > 70).astype(int)
            df['rsi_neutral'] = ((df['rsi'] >= 40) & (df['rsi'] <= 60)).astype(int)
        
        return df
    
    def _create_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Volatility features"""
        # ATR-based features
        if 'atr' in df.columns:
            df['atr_ratio'] = df['atr'] / df['atr'].rolling(20).mean()
            df['atr_pct'] = (df['atr'] / df['close']) * 100
            
            # Volatility regime
            df['vol_regime'] = pd.cut(df['atr_ratio'], 
                                     bins=[0, 0.7, 1.3, 2.0, 10],
                                     labels=[0, 1, 2, 3])  # 0=low, 1=normal, 2=high, 3=extreme
        
        # Realized volatility
        df['realized_vol'] = df['log_return_1'].rolling(20).std() * np.sqrt(252)
        
        # Volatility of volatility
        df['vol_of_vol'] = df['realized_vol'].rolling(10).std()
        
        # Parkinson volatility (uses high/low)
        df['parkinson_vol'] = np.sqrt(
            (1 / (4 * np.log(2))) * 
            np.log(df['high'] / df['low']) ** 2
        ).rolling(20).mean()
        
        # BB width as volatility measure
        if 'bb_width' in df.columns:
            df['bb_width_ratio'] = df['bb_width'] / df['bb_width'].rolling(20).mean()
            df['bb_squeeze'] = (df['bb_width'] < df['bb_width'].rolling(20).mean() * 0.7).astype(int)
        
        return df
    
    def _create_time_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Time-based features"""
        # Extract time components
        if hasattr(df.index, 'hour'):
            df['hour'] = df.index.hour
            df['day_of_week'] = df.index.dayofweek
            df['day_of_month'] = df.index.day
            df['month'] = df.index.month
            
            # Session features
            df['is_asian'] = ((df['hour'] >= 23) | (df['hour'] < 8)).astype(int)
            df['is_london'] = ((df['hour'] >= 7) & (df['hour'] < 16)).astype(int)
            df['is_new_york'] = ((df['hour'] >= 12) & (df['hour'] < 20)).astype(int)
            df['is_overlap'] = ((df['hour'] >= 12) & (df['hour'] < 16)).astype(int)
            
            # Weekend proximity
            df['is_monday'] = (df['day_of_week'] == 0).astype(int)
            df['is_friday'] = (df['day_of_week'] == 4).astype(int)
            
            # Cyclical encoding (for ML models)
            df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
            df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
            df['day_sin'] = np.sin(2 * np.pi * df['day_of_week'] / 7)
            df['day_cos'] = np.cos(2 * np.pi * df['day_of_week'] / 7)
        else:
            # If no datetime index, create placeholder features
            df['hour'] = 12
            df['day_of_week'] = 2
            df['is_overlap'] = 1
        
        return df
    
    def _create_microstructure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Market microstructure features"""
        # Spread features (if available)
        if 'ask' in df.columns and 'bid' in df.columns:
            df['spread'] = df['ask'] - df['bid']
            df['spread_pct'] = (df['spread'] / df['close']) * 100
            df['spread_ratio'] = df['spread'] / df['spread'].rolling(20).mean()
        
        # Tick imbalance (if available)
        if 'tick_imbalance' in df.columns:
            df['tick_imbalance_norm'] = df['tick_imbalance'] / (df['volume'].rolling(20).sum() + 1)
        
        # Volume features
        if 'volume' in df.columns:
            df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
            df['volume_trend'] = df['volume'].rolling(5).mean() / df['volume'].rolling(20).mean()
            
            # Volume-weighted features
            df['vwap_distance'] = (df['close'] / df.get('vwap', df['close'])) - 1 if 'vwap' in df.columns else 0
        
        return df
    
    def _create_pattern_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Candlestick and chart pattern features"""
        # Doji detection
        df['is_doji'] = (df['body_size'] < (df['high'] - df['low']) * 0.1).astype(int)
        
        # Hammer/Shooting star
        df['is_hammer'] = (
            (df['lower_shadow'] > df['body_size'] * 2) &
            (df['upper_shadow'] < df['body_size'])
        ).astype(int)
        
        df['is_shooting_star'] = (
            (df['upper_shadow'] > df['body_size'] * 2) &
            (df['lower_shadow'] < df['body_size'])
        ).astype(int)
        
        # Engulfing pattern
        df['bullish_engulfing'] = (
            (df['close'] > df['open']) &
            (df['close'].shift(1) < df['open'].shift(1)) &
            (df['open'] < df['close'].shift(1)) &
            (df['close'] > df['open'].shift(1))
        ).astype(int)
        
        df['bearish_engulfing'] = (
            (df['close'] < df['open']) &
            (df['close'].shift(1) > df['open'].shift(1)) &
            (df['open'] > df['close'].shift(1)) &
            (df['close'] < df['open'].shift(1))
        ).astype(int)
        
        # Support/Resistance touch
        if 'pivot' in df.columns:
            threshold = df['atr'] * 0.1 if 'atr' in df.columns else df['close'] * 0.001
            df['at_support'] = (abs(df['low'] - df['s1']) < threshold).astype(int)
            df['at_resistance'] = (abs(df['high'] - df['r1']) < threshold).astype(int)
        
        return df
    
    def get_feature_list(self, df: pd.DataFrame) -> List[str]:
        """
        Get list of ML feature columns
        Excludes OHLCV and standard indicator columns
        """
        exclude_cols = ['open', 'high', 'low', 'close', 'volume', 'time', 
                       'ema_8', 'ema_21', 'ema_50', 'ema_200',
                       'rsi', 'macd', 'macd_signal', 'macd_hist',
                       'adx', 'atr', 'bb_upper', 'bb_middle', 'bb_lower']
        
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        
        return feature_cols
    
    def create_target_variable(self, df: pd.DataFrame, 
                              forward_periods: int = 10,
                              profit_threshold: float = 0.002) -> pd.DataFrame:
        """
        Create target variable for ML training
        
        Args:
            df: DataFrame with features
            forward_periods: Periods to look ahead
            profit_threshold: Minimum profit % to consider profitable (0.2%)
        
        Returns:
            DataFrame with 'target' column added
        """
        df = df.copy()
        
        # Calculate future return
        df['future_return'] = df['close'].shift(-forward_periods) / df['close'] - 1
        
        # Binary classification: 1 if profitable, 0 if not
        df['target'] = (df['future_return'] > profit_threshold).astype(int)
        
        # Multi-class classification (optional)
        df['target_multiclass'] = pd.cut(df['future_return'],
                                        bins=[-np.inf, -profit_threshold, profit_threshold, np.inf],
                                        labels=[0, 1, 2])  # 0=loss, 1=neutral, 2=profit
        
        return df
    
    def create_regime_features(self, df: pd.DataFrame, regime_data: Dict) -> pd.DataFrame:
        """
        Add regime-based features
        
        Args:
            df: DataFrame
            regime_data: Dict from MarketRegimeDetector
        """
        df = df.copy()
        
        # One-hot encode regime
        regime = regime_data.get('regime', None)
        if regime:
            regime_value = regime.value if hasattr(regime, 'value') else str(regime)
            df['regime_strong_trend'] = (regime_value == 'strong_trend').astype(int)
            df['regime_weak_trend'] = (regime_value == 'weak_trend').astype(int)
            df['regime_ranging'] = (regime_value == 'ranging').astype(int)
            df['regime_high_vol'] = (regime_value == 'high_volatility').astype(int)
            df['regime_confidence'] = regime_data.get('confidence', 0.5)
        
        return df
