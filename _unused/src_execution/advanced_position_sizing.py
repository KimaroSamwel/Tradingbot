"""
ADVANCED POSITION SIZING MODELS
Implements professional position sizing beyond Kelly Criterion

Models:
1. Optimal F (Ralph Vince) - Maximum geometric growth
2. Fixed Ratio (Ryan Jones) - Delta-based scaling
3. Percent Volatility - ATR-adjusted sizing
4. Secure F - Conservative Optimal F variant

References:
- "Portfolio Management Formulas" by Ralph Vince
- "The Trading Game" by Ryan Jones
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class AdvancedPositionResult:
    """Advanced position sizing result"""
    method: str
    risk_percent: float
    lot_size: float
    position_value: float
    rationale: str
    confidence: float  # 0-100


class OptimalFCalculator:
    """
    Optimal F Position Sizing (Ralph Vince)
    Finds the fraction that maximizes geometric growth
    """
    
    def __init__(self):
        self.trade_history: List[float] = []
        
    def calculate_optimal_f(self, trade_results: List[float], 
                           largest_loss: float) -> float:
        """
        Calculate Optimal F using Ralph Vince's method
        
        Args:
            trade_results: List of trade P&L values
            largest_loss: Largest historical loss (positive number)
            
        Returns:
            Optimal F fraction (0-1)
        """
        if not trade_results or largest_loss <= 0:
            return 0.0
            
        # Normalize trades by largest loss
        normalized_trades = [t / largest_loss for t in trade_results]
        
        # Find F that maximizes TWR (Terminal Wealth Relative)
        best_f = 0.0
        best_twr = 0.0
        
        # Test F values from 0.01 to 0.99
        for f in np.arange(0.01, 1.0, 0.01):
            twr = 1.0
            
            for trade in normalized_trades:
                # HPR = 1 + (f * normalized_trade)
                hpr = 1.0 + (f * trade)
                
                if hpr <= 0:  # Ruin
                    twr = 0
                    break
                    
                twr *= hpr
            
            if twr > best_twr:
                best_twr = twr
                best_f = f
                
        return best_f
    
    def calculate_secure_f(self, optimal_f: float, 
                          safety_factor: float = 0.5) -> float:
        """
        Calculate Secure F (conservative Optimal F)
        
        Args:
            optimal_f: Calculated Optimal F
            safety_factor: Reduction factor (default 0.5 = half Kelly)
            
        Returns:
            Secure F value
        """
        return optimal_f * safety_factor
    
    def get_position_size(self, account_balance: float,
                         trade_results: List[float],
                         largest_loss: float,
                         use_secure: bool = True) -> float:
        """
        Get position size based on Optimal F
        
        Args:
            account_balance: Current account balance
            trade_results: Historical trade results
            largest_loss: Largest loss amount
            use_secure: Use Secure F instead of full Optimal F
            
        Returns:
            Risk amount in account currency
        """
        if len(trade_results) < 10:  # Need minimum sample
            return account_balance * 0.01  # Default 1%
            
        optimal_f = self.calculate_optimal_f(trade_results, largest_loss)
        
        if use_secure:
            f = self.calculate_secure_f(optimal_f, 0.5)
        else:
            f = optimal_f
            
        # Convert F to risk amount
        risk_amount = account_balance * f
        
        # Cap at 5% for safety
        max_risk = account_balance * 0.05
        return min(risk_amount, max_risk)


class FixedRatioSizing:
    """
    Fixed Ratio Position Sizing (Ryan Jones)
    Scales position size based on profit/loss deltas
    """
    
    def __init__(self, initial_balance: float, delta: float = 5000):
        """
        Initialize Fixed Ratio sizing
        
        Args:
            initial_balance: Starting account balance
            delta: Profit increment to increase position (default $5000)
        """
        self.initial_balance = initial_balance
        self.delta = delta
        self.current_contracts = 1
        
    def calculate_contracts(self, current_balance: float) -> int:
        """
        Calculate number of contracts based on Fixed Ratio
        
        Formula: contracts = 0.5 * (-1 + sqrt(1 + 8*profit/delta))
        
        Args:
            current_balance: Current account balance
            
        Returns:
            Number of contracts to trade
        """
        profit = current_balance - self.initial_balance
        
        if profit <= 0:
            return 1  # Minimum 1 contract
            
        # Fixed Ratio formula
        contracts = 0.5 * (-1 + np.sqrt(1 + (8 * profit / self.delta)))
        
        return max(1, int(contracts))
    
    def get_risk_percent(self, current_balance: float,
                        contract_value: float) -> float:
        """
        Get risk percentage based on contract count
        
        Args:
            current_balance: Current balance
            contract_value: Value per contract
            
        Returns:
            Risk as percentage of account
        """
        contracts = self.calculate_contracts(current_balance)
        total_risk = contracts * contract_value
        
        return (total_risk / current_balance) * 100


class PercentVolatilitySizing:
    """
    Percent Volatility Position Sizing
    Adjusts position based on instrument volatility
    """
    
    def __init__(self, target_volatility: float = 2.0):
        """
        Args:
            target_volatility: Target portfolio volatility (%)
        """
        self.target_volatility = target_volatility
        
    def calculate_position_size(self, account_balance: float,
                                atr: float, 
                                price: float,
                                pip_value: float) -> Tuple[float, float]:
        """
        Calculate position size based on volatility
        
        Args:
            account_balance: Current balance
            atr: Average True Range
            price: Current price
            pip_value: Value per pip
            
        Returns:
            (risk_percent, lot_size)
        """
        # Calculate instrument volatility
        volatility_pct = (atr / price) * 100
        
        # Adjust position to normalize volatility
        if volatility_pct > 0:
            volatility_adjustment = self.target_volatility / volatility_pct
        else:
            volatility_adjustment = 1.0
            
        # Base risk adjusted for volatility
        base_risk = 0.01  # 1%
        adjusted_risk = base_risk * volatility_adjustment
        
        # Cap between 0.2% and 3%
        adjusted_risk = max(0.002, min(0.03, adjusted_risk))
        
        # Calculate lot size
        risk_amount = account_balance * adjusted_risk
        lot_size = risk_amount / (atr * pip_value)
        
        return adjusted_risk, lot_size


class AdvancedPositionSizer:
    """
    Master class coordinating all advanced position sizing methods
    """
    
    def __init__(self, account_balance: float, config: Dict = None):
        self.account_balance = account_balance
        self.config = config or {}
        
        # Initialize sub-calculators
        self.optimal_f = OptimalFCalculator()
        self.fixed_ratio = FixedRatioSizing(
            account_balance, 
            delta=self.config.get('fixed_ratio_delta', 5000)
        )
        self.percent_vol = PercentVolatilitySizing(
            target_volatility=self.config.get('target_volatility', 2.0)
        )
        
        # Performance tracking
        self.trade_history: List[float] = []
        self.largest_loss = 0.0
        
    def update_trade_history(self, pnl: float):
        """
        Update trade history with new result
        
        Args:
            pnl: Profit/loss from trade
        """
        self.trade_history.append(pnl)
        
        if pnl < 0:
            self.largest_loss = max(self.largest_loss, abs(pnl))
            
    def calculate_optimal_f_size(self) -> Optional[AdvancedPositionResult]:
        """Calculate position using Optimal F"""
        if len(self.trade_history) < 10:
            return None
            
        risk_amount = self.optimal_f.get_position_size(
            self.account_balance,
            self.trade_history,
            self.largest_loss,
            use_secure=True  # Use Secure F (50% of Optimal F)
        )
        
        risk_pct = (risk_amount / self.account_balance) * 100
        
        return AdvancedPositionResult(
            method="Optimal F (Secure)",
            risk_percent=risk_pct,
            lot_size=0.0,  # Calculated later
            position_value=risk_amount,
            rationale=f"Maximizes geometric growth based on {len(self.trade_history)} trades",
            confidence=min(len(self.trade_history) / 30 * 100, 100)
        )
    
    def calculate_fixed_ratio_size(self, contract_value: float) -> AdvancedPositionResult:
        """Calculate position using Fixed Ratio"""
        risk_pct = self.fixed_ratio.get_risk_percent(
            self.account_balance,
            contract_value
        )
        
        contracts = self.fixed_ratio.calculate_contracts(self.account_balance)
        
        return AdvancedPositionResult(
            method="Fixed Ratio",
            risk_percent=risk_pct,
            lot_size=float(contracts),
            position_value=contracts * contract_value,
            rationale=f"Scales with profit: {contracts} contracts at ${self.fixed_ratio.delta} delta",
            confidence=85.0
        )
    
    def calculate_percent_volatility_size(self, atr: float, 
                                         price: float,
                                         pip_value: float) -> AdvancedPositionResult:
        """Calculate position using Percent Volatility"""
        risk_pct, lot_size = self.percent_vol.calculate_position_size(
            self.account_balance,
            atr,
            price,
            pip_value
        )
        
        return AdvancedPositionResult(
            method="Percent Volatility",
            risk_percent=risk_pct * 100,
            lot_size=lot_size,
            position_value=self.account_balance * risk_pct,
            rationale=f"Normalized to {self.percent_vol.target_volatility}% portfolio volatility",
            confidence=90.0
        )
    
    def get_recommended_size(self, method: str = "optimal_f",
                           **kwargs) -> Optional[AdvancedPositionResult]:
        """
        Get recommended position size based on selected method
        
        Args:
            method: 'optimal_f', 'fixed_ratio', 'percent_volatility'
            **kwargs: Method-specific parameters
            
        Returns:
            Position sizing result
        """
        if method == "optimal_f":
            return self.calculate_optimal_f_size()
            
        elif method == "fixed_ratio":
            contract_value = kwargs.get('contract_value', 100)
            return self.calculate_fixed_ratio_size(contract_value)
            
        elif method == "percent_volatility":
            atr = kwargs.get('atr', 0.001)
            price = kwargs.get('price', 1.0)
            pip_value = kwargs.get('pip_value', 10.0)
            return self.calculate_percent_volatility_size(atr, price, pip_value)
            
        return None
    
    def compare_methods(self, atr: float, price: float, 
                       pip_value: float) -> List[AdvancedPositionResult]:
        """
        Compare all sizing methods
        
        Returns:
            List of results from all methods
        """
        results = []
        
        # Optimal F (if enough data)
        opt_f = self.calculate_optimal_f_size()
        if opt_f:
            results.append(opt_f)
            
        # Fixed Ratio
        contract_value = 100  # Standard contract
        results.append(self.calculate_fixed_ratio_size(contract_value))
        
        # Percent Volatility
        results.append(self.calculate_percent_volatility_size(
            atr, price, pip_value
        ))
        
        return results
