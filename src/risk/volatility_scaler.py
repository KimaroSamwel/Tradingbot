"""
APEX FX Trading Bot - Volatility Scaler
PRD Volume II Section 10: Volatility-Based Position Sizing

Computes a portfolio-level scalar (0.40 to 1.00) applied to all position sizes
based on current realized volatility vs 60-day average.
"""

from typing import Dict, List, Tuple, Optional
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import threading


class VolatilityScaler:
    """
    Volatility Scaler - adjusts position sizes based on market volatility.
    
    VRS (Volatility Ratio Scalar) table:
    - CALM (ratio <= 0.8): scalar 1.00
    - NORMAL (0.8 < ratio <= 1.2): scalar 1.00
    - ELEVATED (1.2 < ratio <= 1.5): scalar 0.70
    - HIGH (1.5 < ratio <= 2.0): scalar 0.50
    - CRISIS (ratio > 2.0): scalar 0.40
    """
    
    VRS_TABLE = [
        {'max_ratio': 0.8, 'scalar': 1.00, 'label': 'CALM'},
        {'max_ratio': 1.2, 'scalar': 1.00, 'label': 'NORMAL'},
        {'max_ratio': 1.5, 'scalar': 0.70, 'label': 'ELEVATED'},
        {'max_ratio': 2.0, 'scalar': 0.50, 'label': 'HIGH'},
        {'max_ratio': 9999, 'scalar': 0.40, 'label': 'CRISIS'},
    ]
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize the volatility scaler.
        
        Args:
            config: Optional configuration dict
            logger: Optional logger instance
        """
        self._lock = threading.Lock()
        self._config = config or {}
        self._logger = logger
        
        # Cache for ATR values
        self._atr_cache: Dict[str, Dict] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes
    
    def compute_realized_vol_ratio(
        self, 
        symbol: str, 
        df_d1: pd.DataFrame
    ) -> float:
        """
        5-day sum of daily ATR / 60-day average daily ATR for the symbol.
        
        Args:
            symbol: Trading symbol
            df_d1: Daily OHLC data DataFrame
            
        Returns:
            Volatility ratio (current/avg)
        """
        if df_d1 is None or len(df_d1) < 60:
            return 1.0  # Default to normal if insufficient data
        
        # Calculate True Range
        high = df_d1['high']
        low = df_d1['low']
        close = df_d1['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # Calculate ATR(14)
        atr = true_range.rolling(14).mean()
        
        # Current 5-day ATR sum (most volatile period)
        current_atr = atr.tail(5).sum()
        
        # 60-day average ATR
        avg_atr = atr.tail(60).mean()
        
        if avg_atr <= 0:
            return 1.0
        
        return current_atr / avg_atr
    
    def compute_atr14(self, df: pd.DataFrame) -> float:
        """
        Calculate ATR(14) for a dataframe.
        
        Args:
            df: OHLC data
            
        Returns:
            ATR value in price units
        """
        if df is None or len(df) < 14:
            return 0.0
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = true_range.rolling(14).mean().iloc[-1]
        
        return atr if not pd.isna(atr) else 0.0
    
    def detect_correlation_spike(self, all_symbols_ratios: Dict[str, float]) -> bool:
        """
        Return True if 3+ symbols simultaneously show vol ratio > 1.3.
        
        Args:
            all_symbols_ratios: Dict mapping symbol to vol ratio
            
        Returns:
            True if correlation spike detected
        """
        spike_count = sum(1 for ratio in all_symbols_ratios.values() if ratio > 1.3)
        return bool(spike_count >= 3)
    
    def get_scalar(
        self, 
        vol_ratio: float, 
        correlation_spike: bool
    ) -> Tuple[float, str]:
        """
        Return (scalar_value, label).
        If correlation_spike, cap scalar at 0.40.
        
        Args:
            vol_ratio: Current volatility ratio
            correlation_spike: Whether correlation spike is detected
            
        Returns:
            Tuple of (scalar, label)
        """
        with self._lock:
            for tier in self.VRS_TABLE:
                if vol_ratio <= tier['max_ratio']:
                    scalar = tier['scalar']
                    label = tier['label']
                    
                    # Apply correlation spike cap
                    if correlation_spike and scalar > 0.40:
                        scalar = 0.40
                        label = 'CRISIS'
                    
                    return scalar, label
            
            # Default (shouldn't reach here)
            return 0.40, 'CRISIS'
    
    def is_xau_defensive_mode(self, xau_df_h4: pd.DataFrame) -> bool:
        """
        True if XAU/USD ATR(14) on H4 exceeds 2.5x its 20-day ATR average.
        
        Args:
            xau_df_h4: XAU/USD H4 OHLC data
            
        Returns:
            True if XAU is in defensive mode
        """
        if xau_df_h4 is None or len(xau_df_h4) < 20:
            return False
        
        # Calculate ATR(14)
        atr_14 = self.compute_atr14(xau_df_h4)
        
        # Calculate 20-day ATR average
        high = xau_df_h4['high']
        low = xau_df_h4['low']
        close = xau_df_h4['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr_20_avg = true_range.rolling(20).mean().iloc[-1]
        
        if atr_20_avg <= 0:
            return False
        
        # Check if current ATR exceeds 2.5x average
        return bool(atr_14 > (atr_20_avg * 2.5))
    
    def get_xau_defensive_sl_multiplier(self) -> float:
        """
        Return 0.70 — trailing stop distance reduced 30% in Defensive Mode.
        
        Returns:
            SL multiplier for XAU defensive mode
        """
        return 0.70
    
    def compute_all_symbol_ratios(
        self, 
        mt5_connector, 
        symbols: List[str]
    ) -> Dict[str, float]:
        """
        Compute volatility ratios for all symbols.
        
        Args:
            mt5_connector: MT5 connector instance
            symbols: List of symbols to check
            
        Returns:
            Dict mapping symbol to volatility ratio
        """
        ratios = {}
        
        for symbol in symbols:
            try:
                df_d1 = mt5_connector.get_ohlc(symbol, 'D1', 70)
                if df_d1 is not None:
                    ratio = self.compute_realized_vol_ratio(symbol, df_d1)
                    ratios[symbol] = ratio
            except Exception as e:
                if self._logger:
                    self._logger.warning('vol_ratio_error', symbol=symbol, error=str(e))
                ratios[symbol] = 1.0  # Default
        
        return ratios
    
    def get_current_state(
        self, 
        mt5_connector, 
        symbols: List[str]
    ) -> Dict:
        """
        Get current volatility scaling state for all symbols.
        
        Args:
            mt5_connector: MT5 connector instance
            symbols: List of symbols
            
        Returns:
            Dict with scalar, label, per-symbol ratios, correlation spike status
        """
        ratios = self.compute_all_symbol_ratios(mt5_connector, symbols)
        
        # Calculate average ratio
        avg_ratio = sum(ratios.values()) / len(ratios) if ratios else 1.0
        
        # Detect correlation spike
        correlation_spike = self.detect_correlation_spike(ratios)
        
        # Get scalar
        scalar, label = self.get_scalar(avg_ratio, correlation_spike)
        
        return {
            'scalar': scalar,
            'label': label,
            'avg_ratio': avg_ratio,
            'symbol_ratios': ratios,
            'correlation_spike': correlation_spike
        }


# Global instance
_vol_scaler = None


def get_volatility_scaler(config: Optional[Dict] = None, logger=None) -> VolatilityScaler:
    """Get global volatility scaler instance."""
    global _vol_scaler
    if _vol_scaler is None:
        _vol_scaler = VolatilityScaler(config, logger)
    return _vol_scaler