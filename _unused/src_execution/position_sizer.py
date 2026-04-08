"""
Advanced Position Sizing with Kelly Criterion
Professional risk management for production trading
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple
import yaml


class KellyCriterionCalculator:
    """
    Standalone Kelly Criterion calculator
    """
    
    def __init__(self, kelly_fraction: float = 0.25):
        """
        Args:
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly, safer)
        """
        self.kelly_fraction = kelly_fraction
    
    def calculate_kelly_size(self, win_rate: float, avg_win: float, 
                            avg_loss: float) -> float:
        """
        Kelly Criterion position sizing
        
        Formula: f* = (p*b - q) / b
        where p = win_rate, b = avg_win/avg_loss, q = 1-p
        
        Args:
            win_rate: Historical win rate (0-1)
            avg_win: Average winning trade
            avg_loss: Average losing trade (positive number)
        
        Returns:
            Position size as fraction of capital (0-1)
        """
        if win_rate <= 0 or win_rate >= 1 or avg_loss <= 0 or avg_win <= 0:
            return 0.01  # Fallback to 1%
        
        loss_rate = 1 - win_rate
        odds = avg_win / avg_loss
        
        # Kelly formula
        kelly = (win_rate * odds - loss_rate) / odds
        
        # Apply fraction for safety (full Kelly is too aggressive)
        kelly_adjusted = kelly * self.kelly_fraction
        
        # Cap at reasonable limits
        return max(0.0, min(kelly_adjusted, 0.20))  # Max 20%


class AdvancedPositionSizer:
    """
    Advanced position sizing with multiple methods:
    1. Kelly Criterion (optimal growth)
    2. Volatility-adjusted (ATR-based)
    3. Fixed fractional (conservative)
    4. Risk parity (portfolio-based)
    """
    
    def __init__(self, config_path: str = 'config/risk_config.json'):
        try:
            with open(config_path, 'r') as f:
                import json
                self.config = json.load(f)
        except FileNotFoundError:
            # Use default config if file not found
            self.config = self._default_config()
        
        self.trade_history = []
        self.max_history = 100
    
    def _default_config(self) -> Dict:
        """Default risk configuration"""
        return {
            'position_sizing': {
                'base_risk_pct': 1.0,
                'default_method': 'risk_based',
                'methods': {
                    'risk_based': {'risk_per_trade_pct': 1.0}
                }
            }
        }
    
    def calculate_kelly_size(self, win_rate: float, avg_win: float, 
                            avg_loss: float, kelly_fraction: float = 0.25) -> float:
        """
        Kelly Criterion position sizing
        
        Formula: f* = (p*b - q) / b
        where p = win_rate, b = avg_win/avg_loss, q = 1-p
        
        Args:
            win_rate: Historical win rate (0-1)
            avg_win: Average winning trade
            avg_loss: Average losing trade
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
        
        Returns:
            Position size as fraction of capital (0-1)
        """
        if win_rate <= 0 or win_rate >= 1 or avg_loss <= 0:
            return 0.01  # Fallback to 1%
        
        loss_rate = 1 - win_rate
        odds = avg_win / avg_loss
        
        # Kelly formula
        kelly = (win_rate * odds - loss_rate) / odds
        
        # Apply fraction for safety (full Kelly is too aggressive)
        kelly_adjusted = kelly * kelly_fraction
        
        # Cap at reasonable limits
        return max(0.0, min(kelly_adjusted, 0.20))  # Max 20%
    
    def calculate_volatility_adjusted_size(self, 
                                          base_risk_pct: float,
                                          current_atr: float,
                                          avg_atr: float,
                                          sl_pips: float,
                                          account_balance: float,
                                          pip_value: float) -> float:
        """
        Volatility-adjusted position sizing
        
        Reduces size in high volatility, increases in low volatility
        
        Args:
            base_risk_pct: Base risk percentage (e.g., 1.0 for 1%)
            current_atr: Current ATR value
            avg_atr: Average ATR over lookback period
            sl_pips: Stop loss distance in pips
            account_balance: Account balance
            pip_value: Value per pip per lot
        
        Returns:
            Lot size
        """
        # Calculate ATR ratio
        atr_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
        
        # Adjust risk based on volatility
        if atr_ratio > 1.5:
            risk_multiplier = 0.6  # High volatility: reduce to 60%
        elif atr_ratio > 1.2:
            risk_multiplier = 0.8  # Elevated: reduce to 80%
        elif atr_ratio < 0.7:
            risk_multiplier = 1.3  # Low volatility: increase to 130%
        elif atr_ratio < 0.85:
            risk_multiplier = 1.1  # Below average: increase to 110%
        else:
            risk_multiplier = 1.0  # Normal
        
        # Calculate position size
        adjusted_risk_pct = base_risk_pct * risk_multiplier
        risk_amount = account_balance * (adjusted_risk_pct / 100)
        lot_size = risk_amount / (sl_pips * pip_value)
        
        return max(0.01, round(lot_size, 2))
    
    def calculate_fixed_fractional_size(self,
                                       risk_pct: float,
                                       sl_pips: float,
                                       account_balance: float,
                                       pip_value: float) -> float:
        """
        Fixed fractional position sizing (simple and reliable)
        
        Args:
            risk_pct: Risk percentage per trade
            sl_pips: Stop loss distance in pips
            account_balance: Account balance
            pip_value: Value per pip per lot
        
        Returns:
            Lot size
        """
        risk_amount = account_balance * (risk_pct / 100)
        lot_size = risk_amount / (sl_pips * pip_value)
        
        return max(0.01, round(lot_size, 2))
    
    def calculate_optimal_size(self,
                              account_balance: float,
                              sl_pips: float,
                              pip_value: float,
                              current_atr: float,
                              avg_atr: float,
                              method: str = 'auto') -> Tuple[float, str]:
        """
        Calculate optimal position size using best available method
        
        Args:
            account_balance: Current account balance
            sl_pips: Stop loss distance in pips
            pip_value: Value per pip per lot
            current_atr: Current ATR
            avg_atr: Average ATR
            method: 'kelly', 'volatility', 'fixed', 'auto'
        
        Returns:
            (lot_size, method_used)
        """
        # Get base risk from config, handle different config structures
        pos_config = self.config.get('position_sizing', {})
        methods = pos_config.get('methods', {})
        risk_based = methods.get('risk_based', {})
        base_risk_pct = risk_based.get('risk_per_trade_pct', pos_config.get('base_risk_pct', 1.0))
        
        # Auto-select best method
        if method == 'auto':
            if len(self.trade_history) >= 30:
                method = 'kelly'
            elif current_atr and avg_atr:
                method = 'volatility'
            else:
                method = 'fixed'
        
        # Calculate based on method
        if method == 'kelly' and len(self.trade_history) >= 10:
            # Calculate from trade history
            wins = [t for t in self.trade_history if t['profit'] > 0]
            losses = [t for t in self.trade_history if t['profit'] < 0]
            
            if wins and losses:
                win_rate = len(wins) / len(self.trade_history)
                avg_win = np.mean([t['profit'] for t in wins])
                avg_loss = np.mean([abs(t['profit']) for t in losses])
                
                kelly_fraction = self.calculate_kelly_size(win_rate, avg_win, avg_loss)
                risk_amount = account_balance * kelly_fraction
                lot_size = risk_amount / (sl_pips * pip_value)
                
                return (max(0.01, round(lot_size, 2)), 'kelly')
        
        if method == 'volatility' and current_atr and avg_atr:
            lot_size = self.calculate_volatility_adjusted_size(
                base_risk_pct, current_atr, avg_atr, 
                sl_pips, account_balance, pip_value
            )
            return (lot_size, 'volatility')
        
        # Fallback to fixed
        lot_size = self.calculate_fixed_fractional_size(
            base_risk_pct, sl_pips, account_balance, pip_value
        )
        return (lot_size, 'fixed')
    
    def add_trade_result(self, profit: float, risk: float, duration_hours: float):
        """Add trade result to history for Kelly calculation"""
        self.trade_history.append({
            'profit': profit,
            'risk': risk,
            'duration_hours': duration_hours,
            'return_pct': (profit / risk) if risk > 0 else 0
        })
        
        # Keep only recent history
        if len(self.trade_history) > self.max_history:
            self.trade_history.pop(0)
    
    def get_statistics(self) -> Dict:
        """Get current statistics for Kelly calculation"""
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0.5,
                'avg_win': 0,
                'avg_loss': 0,
                'profit_factor': 0,
                'kelly_size': 0.01
            }
        
        wins = [t for t in self.trade_history if t['profit'] > 0]
        losses = [t for t in self.trade_history if t['profit'] < 0]
        
        total_trades = len(self.trade_history)
        win_rate = len(wins) / total_trades if total_trades > 0 else 0
        avg_win = np.mean([t['profit'] for t in wins]) if wins else 0
        avg_loss = np.mean([abs(t['profit']) for t in losses]) if losses else 0
        
        total_profit = sum(t['profit'] for t in wins)
        total_loss = sum(abs(t['profit']) for t in losses)
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        kelly_size = self.calculate_kelly_size(win_rate, avg_win, avg_loss) if wins and losses else 0.01
        
        return {
            'total_trades': total_trades,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'kelly_size': kelly_size
        }
    
    def validate_position_size(self, lot_size: float, symbol: str) -> Tuple[bool, str]:
        """
        Validate position size against broker limits and risk limits
        
        Args:
            lot_size: Proposed lot size
            symbol: Trading symbol
        
        Returns:
            (is_valid, reason)
        """
        pos_config = self.config.get('position_sizing', {})
        min_lot = pos_config.get('min_lot_size', 0.01)
        max_lot = pos_config.get('max_lot_size', 100.0)
        max_risk_per_trade = pos_config.get('max_risk_per_trade', 2.0)
        
        if lot_size < min_lot:
            return (False, f"Below minimum lot size: {lot_size} < {min_lot}")
        
        if lot_size > max_lot:
            return (False, f"Exceeds maximum lot size: {lot_size} > {max_lot}")
        
        # Additional validations can be added here
        
        return (True, "Position size valid")


class RiskParity:
    """
    Risk parity position sizing across portfolio
    Ensures each position contributes equally to portfolio risk
    """
    
    def __init__(self):
        self.positions = {}
    
    def calculate_position_risk_contribution(self, 
                                            lot_size: float,
                                            sl_pips: float,
                                            pip_value: float,
                                            volatility: float) -> float:
        """
        Calculate risk contribution of a position
        
        Args:
            lot_size: Position size
            sl_pips: Stop loss distance
            pip_value: Pip value
            volatility: ATR or volatility measure
        
        Returns:
            Risk contribution in currency
        """
        position_risk = lot_size * sl_pips * pip_value
        volatility_factor = volatility / 100  # Normalize
        
        return position_risk * (1 + volatility_factor)
    
    def adjust_for_risk_parity(self,
                               proposed_size: float,
                               symbol: str,
                               sl_pips: float,
                               pip_value: float,
                               volatility: float,
                               target_portfolio_risk: float) -> float:
        """
        Adjust position size to maintain risk parity
        
        Args:
            proposed_size: Initially calculated size
            symbol: Trading symbol
            sl_pips: Stop loss distance
            pip_value: Pip value
            volatility: Current volatility
            target_portfolio_risk: Target total portfolio risk
        
        Returns:
            Adjusted lot size
        """
        # Calculate current portfolio risk
        total_current_risk = sum(
            self.calculate_position_risk_contribution(
                pos['lot_size'], pos['sl_pips'], 
                pos['pip_value'], pos['volatility']
            )
            for pos in self.positions.values()
        )
        
        # Calculate proposed risk
        proposed_risk = self.calculate_position_risk_contribution(
            proposed_size, sl_pips, pip_value, volatility
        )
        
        # If adding this position would exceed target, reduce
        if total_current_risk + proposed_risk > target_portfolio_risk:
            available_risk = target_portfolio_risk - total_current_risk
            if available_risk <= 0:
                return 0.0
            
            # Reduce proportionally
            reduction_factor = available_risk / proposed_risk
            adjusted_size = proposed_size * reduction_factor
            
            return max(0.01, round(adjusted_size, 2))
        
        return proposed_size
    
    def add_position(self, symbol: str, lot_size: float, sl_pips: float,
                    pip_value: float, volatility: float):
        """Add position to risk parity tracking"""
        self.positions[symbol] = {
            'lot_size': lot_size,
            'sl_pips': sl_pips,
            'pip_value': pip_value,
            'volatility': volatility
        }
    
    def remove_position(self, symbol: str):
        """Remove position from tracking"""
        if symbol in self.positions:
            del self.positions[symbol]
