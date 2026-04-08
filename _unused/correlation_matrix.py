"""
Correlation Analysis
Calculate and track correlations between currency pairs
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import MetaTrader5 as mt5


class CorrelationAnalyzer:
    """
    Analyzes correlations between currency pairs
    Helps prevent overexposure to correlated pairs
    """
    
    def __init__(self, lookback_periods: int = 100):
        """
        Initialize correlation analyzer
        
        Args:
            lookback_periods: Number of periods for correlation calculation
        """
        self.lookback_periods = lookback_periods
        self.correlation_matrix = {}
    
    def calculate_correlations(self, symbols: List[str], timeframe: int = mt5.TIMEFRAME_H1) -> pd.DataFrame:
        """
        Calculate correlation matrix for symbols
        
        Args:
            symbols: List of symbols to analyze
            timeframe: MT5 timeframe
        
        Returns:
            Correlation matrix DataFrame
        """
        # Fetch data for all symbols
        returns_data = {}
        
        for symbol in symbols:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, self.lookback_periods)
            if rates is not None and len(rates) > 0:
                df = pd.DataFrame(rates)
                df['returns'] = df['close'].pct_change()
                returns_data[symbol] = df['returns'].dropna()
        
        # Create returns DataFrame
        returns_df = pd.DataFrame(returns_data)
        
        # Calculate correlation matrix
        corr_matrix = returns_df.corr()
        
        # Store in dict format for easy lookup
        self.correlation_matrix = {}
        for sym1 in symbols:
            for sym2 in symbols:
                if sym1 != sym2 and sym1 in corr_matrix.columns and sym2 in corr_matrix.columns:
                    self.correlation_matrix[f"{sym1}_{sym2}"] = corr_matrix.loc[sym1, sym2]
        
        return corr_matrix
    
    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """
        Get correlation between two symbols
        
        Args:
            symbol1: First symbol
            symbol2: Second symbol
        
        Returns:
            Correlation coefficient (-1 to 1)
        """
        key1 = f"{symbol1}_{symbol2}"
        key2 = f"{symbol2}_{symbol1}"
        
        if key1 in self.correlation_matrix:
            return self.correlation_matrix[key1]
        elif key2 in self.correlation_matrix:
            return self.correlation_matrix[key2]
        else:
            return 0.0
    
    def find_correlated_pairs(self, symbol: str, threshold: float = 0.7) -> List[Tuple[str, float]]:
        """
        Find pairs highly correlated with given symbol
        
        Args:
            symbol: Reference symbol
            threshold: Minimum correlation (absolute value)
        
        Returns:
            List of (symbol, correlation) tuples
        """
        correlated = []
        
        for key, corr in self.correlation_matrix.items():
            if symbol in key and abs(corr) >= threshold:
                other_symbol = key.replace(f"{symbol}_", "").replace(f"_{symbol}", "")
                if other_symbol != symbol:
                    correlated.append((other_symbol, corr))
        
        correlated.sort(key=lambda x: abs(x[1]), reverse=True)
        return correlated
    
    def check_position_correlation(self, existing_positions: List[str], 
                                   new_symbol: str, max_correlation: float = 0.8) -> Tuple[bool, str]:
        """
        Check if new position is too correlated with existing positions
        
        Args:
            existing_positions: List of symbols in current positions
            new_symbol: Symbol to check
            max_correlation: Maximum allowed correlation
        
        Returns:
            (can_add, reason)
        """
        high_correlations = []
        
        for existing in existing_positions:
            corr = abs(self.get_correlation(existing, new_symbol))
            if corr >= max_correlation:
                high_correlations.append((existing, corr))
        
        if high_correlations:
            pairs_str = ", ".join([f"{s} ({c:.2f})" for s, c in high_correlations])
            return (False, f"High correlation with: {pairs_str}")
        
        return (True, "Correlation acceptable")
    
    def print_correlation_matrix(self, symbols: List[str]):
        """Print correlation matrix"""
        corr_matrix = self.calculate_correlations(symbols)
        
        print("\n" + "="*80)
        print("CORRELATION MATRIX")
        print("="*80)
        print(corr_matrix.round(2))
        print("="*80)
        print("\nInterpretation:")
        print("  1.0  = Perfect positive correlation")
        print("  0.8+ = Strong positive correlation")
        print("  0.0  = No correlation")
        print(" -0.8- = Strong negative correlation")
        print(" -1.0  = Perfect negative correlation")
        print("="*80)
