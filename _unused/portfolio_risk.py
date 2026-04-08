"""
Portfolio Risk Management
Aggregate risk across all positions and pairs
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class RiskMetrics:
    """Portfolio risk metrics"""
    total_exposure: float
    total_risk_amount: float
    risk_percentage: float
    var_95: float  # Value at Risk 95%
    expected_shortfall: float
    correlation_adjusted_risk: float
    max_loss_scenario: float


class PortfolioRiskManager:
    """
    Manages portfolio-level risk
    Aggregates risk across all positions
    """
    
    def __init__(self, account_balance: float, max_portfolio_risk_pct: float = 5.0):
        """
        Initialize portfolio risk manager
        
        Args:
            account_balance: Current account balance
            max_portfolio_risk_pct: Maximum portfolio risk %
        """
        self.account_balance = account_balance
        self.max_portfolio_risk_pct = max_portfolio_risk_pct
        self.positions = {}
    
    def add_position(self, symbol: str, entry_price: float, stop_loss: float,
                    volume: float, direction: str):
        """
        Add position to portfolio tracking
        
        Args:
            symbol: Trading symbol
            entry_price: Entry price
            stop_loss: Stop loss price
            volume: Position size in lots
            direction: 'BUY' or 'SELL'
        """
        # Calculate position risk
        if direction == 'BUY':
            risk_pips = entry_price - stop_loss
        else:
            risk_pips = stop_loss - entry_price
        
        pip_value = self._calculate_pip_value(symbol, volume)
        risk_amount = abs(risk_pips * pip_value * 10000)  # Convert to pips
        
        self.positions[symbol] = {
            'entry_price': entry_price,
            'stop_loss': stop_loss,
            'volume': volume,
            'direction': direction,
            'risk_amount': risk_amount,
            'risk_percentage': (risk_amount / self.account_balance) * 100
        }
    
    def remove_position(self, symbol: str):
        """Remove position from tracking"""
        if symbol in self.positions:
            del self.positions[symbol]
    
    def calculate_portfolio_risk(self, correlation_matrix: Optional[Dict] = None) -> RiskMetrics:
        """
        Calculate aggregate portfolio risk
        
        Args:
            correlation_matrix: Optional correlation matrix between pairs
        
        Returns:
            Portfolio risk metrics
        """
        if not self.positions:
            return RiskMetrics(
                total_exposure=0,
                total_risk_amount=0,
                risk_percentage=0,
                var_95=0,
                expected_shortfall=0,
                correlation_adjusted_risk=0,
                max_loss_scenario=0
            )
        
        # Simple sum of risks
        total_risk = sum(p['risk_amount'] for p in self.positions.values())
        risk_pct = (total_risk / self.account_balance) * 100
        
        # Calculate Value at Risk (95% confidence)
        risk_amounts = [p['risk_amount'] for p in self.positions.values()]
        var_95 = np.percentile(risk_amounts, 95) if risk_amounts else 0
        
        # Expected Shortfall (average loss beyond VaR)
        losses_beyond_var = [r for r in risk_amounts if r > var_95]
        expected_shortfall = np.mean(losses_beyond_var) if losses_beyond_var else var_95
        
        # Correlation-adjusted risk (if correlation matrix provided)
        if correlation_matrix:
            corr_adjusted = self._calculate_correlation_adjusted_risk(correlation_matrix)
        else:
            corr_adjusted = total_risk
        
        # Maximum loss scenario (all positions hit SL)
        max_loss = total_risk
        
        return RiskMetrics(
            total_exposure=sum(p['volume'] * 100000 for p in self.positions.values()),
            total_risk_amount=total_risk,
            risk_percentage=risk_pct,
            var_95=var_95,
            expected_shortfall=expected_shortfall,
            correlation_adjusted_risk=corr_adjusted,
            max_loss_scenario=max_loss
        )
    
    def can_add_position(self, new_risk_amount: float) -> tuple[bool, str]:
        """
        Check if new position can be added within risk limits
        
        Args:
            new_risk_amount: Risk amount for new position
        
        Returns:
            (can_add, reason)
        """
        current_risk = sum(p['risk_amount'] for p in self.positions.values())
        total_risk = current_risk + new_risk_amount
        total_risk_pct = (total_risk / self.account_balance) * 100
        
        if total_risk_pct > self.max_portfolio_risk_pct:
            return (False, f"Portfolio risk {total_risk_pct:.1f}% exceeds limit {self.max_portfolio_risk_pct}%")
        
        return (True, "Risk within limits")
    
    def _calculate_pip_value(self, symbol: str, volume: float) -> float:
        """Calculate pip value for symbol"""
        # Simplified - should use MT5 symbol info
        return 10 * volume  # $10 per pip per standard lot
    
    def _calculate_correlation_adjusted_risk(self, correlation_matrix: Dict) -> float:
        """
        Calculate portfolio risk adjusted for correlations
        Uses portfolio variance formula: sqrt(sum of weighted variances + covariances)
        """
        symbols = list(self.positions.keys())
        n = len(symbols)
        
        if n == 0:
            return 0
        
        # Build risk vector
        risks = np.array([self.positions[s]['risk_amount'] for s in symbols])
        
        # Build correlation matrix
        corr_matrix = np.eye(n)
        for i, sym1 in enumerate(symbols):
            for j, sym2 in enumerate(symbols):
                if i != j:
                    corr_key = f"{sym1}_{sym2}"
                    corr_matrix[i, j] = correlation_matrix.get(corr_key, 0.5)
        
        # Portfolio variance = R^T * Corr * R
        portfolio_variance = risks @ corr_matrix @ risks
        portfolio_risk = np.sqrt(portfolio_variance)
        
        return portfolio_risk
    
    def print_portfolio_summary(self):
        """Print portfolio risk summary"""
        metrics = self.calculate_portfolio_risk()
        
        print("\n" + "="*80)
        print("PORTFOLIO RISK SUMMARY")
        print("="*80)
        print(f"Account Balance:    ${self.account_balance:,.2f}")
        print(f"Open Positions:     {len(self.positions)}")
        print(f"Total Exposure:     ${metrics.total_exposure:,.2f}")
        print(f"Total Risk:         ${metrics.total_risk_amount:,.2f} ({metrics.risk_percentage:.2f}%)")
        print(f"Max Risk Allowed:   ${self.account_balance * self.max_portfolio_risk_pct / 100:,.2f} ({self.max_portfolio_risk_pct}%)")
        print(f"VaR (95%):          ${metrics.var_95:,.2f}")
        print(f"Expected Shortfall: ${metrics.expected_shortfall:,.2f}")
        print(f"Max Loss Scenario:  ${metrics.max_loss_scenario:,.2f}")
        
        if metrics.risk_percentage > self.max_portfolio_risk_pct:
            print(f"\n⚠️ WARNING: Portfolio risk exceeds limit!")
        else:
            print(f"\n✅ Portfolio risk within limits")
        
        print("="*80)
