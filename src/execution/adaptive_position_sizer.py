"""
Adaptive Position Sizing with Correlation Adjustment
Professional risk-based position sizing with multi-factor adjustments
"""

import numpy as np
import MetaTrader5 as mt5
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class PositionSize:
    lots: float
    risk_amount: float
    risk_percent: float
    adjusted_risk: float
    sl_distance_pips: float
    adjustments_applied: Dict[str, float]
    warnings: List[str]


class AdaptivePositionSizer:
    """
    Professional position sizing with dynamic adjustments
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Base risk parameters
        self.base_risk_percent = self.config.get('risk_per_trade', 1.0)
        self.max_risk_percent = self.config.get('max_risk', 2.0)
        self.min_risk_percent = self.config.get('min_risk', 0.5)
        
        # Drawdown limits
        self.max_drawdown_percent = self.config.get('max_drawdown', 20.0)
        self.max_daily_drawdown = self.config.get('max_daily_drawdown', 5.0)
        
        # Position limits
        self.max_position_size = self.config.get('max_position_size', 10.0)
        self.min_position_size = self.config.get('min_position_size', 0.01)
        
        # Correlation limits
        self.max_correlation_exposure = self.config.get('max_correlation_exposure', 5.0)
        
        # Track recent trades
        self.trade_history = []
        self.initial_balance = None
    
    def calculate_position_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_balance: float,
        confidence: float = 0.8,
        volatility_ratio: float = 1.0,
        regime_multiplier: float = 1.0,
        session_multiplier: float = 1.0,
        correlation_exposure: float = 0.0
    ) -> PositionSize:
        """
        Calculate optimal position size with all adjustments
        """
        if self.initial_balance is None:
            self.initial_balance = account_balance
        
        warnings = []
        adjustments = {}
        
        # 1. Base Risk Calculation
        base_risk = self.base_risk_percent / 100
        adjustments['base_risk'] = self.base_risk_percent
        
        # 2. Confidence Adjustment
        confidence_adj = self._adjust_for_confidence(confidence)
        base_risk *= confidence_adj
        adjustments['confidence'] = confidence_adj
        
        # 3. Drawdown Adjustment
        drawdown_adj = self._adjust_for_drawdown(account_balance)
        base_risk *= drawdown_adj
        adjustments['drawdown'] = drawdown_adj
        
        if drawdown_adj < 0.8:
            warnings.append(f"Drawdown adjustment: {drawdown_adj:.2f}")
        
        # 4. Volatility Adjustment
        volatility_adj = self._adjust_for_volatility(volatility_ratio)
        base_risk *= volatility_adj
        adjustments['volatility'] = volatility_adj
        
        if volatility_adj < 0.8:
            warnings.append(f"High volatility: size reduced to {volatility_adj:.2f}")
        
        # 5. Regime Adjustment
        base_risk *= regime_multiplier
        adjustments['regime'] = regime_multiplier
        
        # 6. Session Adjustment
        base_risk *= session_multiplier
        adjustments['session'] = session_multiplier
        
        # 7. Correlation Adjustment
        correlation_adj = self._adjust_for_correlation(correlation_exposure)
        base_risk *= correlation_adj
        adjustments['correlation'] = correlation_adj
        
        if correlation_adj < 1.0:
            warnings.append(f"Correlation limit: size reduced to {correlation_adj:.2f}")
        
        # 8. Consecutive Loss Adjustment
        consecutive_adj = self._adjust_for_consecutive_losses()
        base_risk *= consecutive_adj
        adjustments['consecutive_losses'] = consecutive_adj
        
        if consecutive_adj < 1.0:
            warnings.append(f"Consecutive losses: size reduced to {consecutive_adj:.2f}")
        
        # 9. Time-Based Adjustment (day of week, time of day)
        time_adj = self._adjust_for_time()
        base_risk *= time_adj
        adjustments['time'] = time_adj
        
        # Ensure within limits
        final_risk = max(self.min_risk_percent/100, 
                        min(base_risk, self.max_risk_percent/100))
        
        adjustments['final_risk_percent'] = final_risk * 100
        
        # Calculate position size
        risk_amount = account_balance * final_risk
        
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            warnings.append("Could not get symbol info")
            return self._create_minimal_position(warnings)
        
        # Calculate stop distance in pips
        point = symbol_info.point
        sl_distance = abs(entry_price - stop_loss)
        sl_pips = sl_distance / point
        
        # Calculate pip value
        tick_value = symbol_info.trade_tick_value
        tick_size = symbol_info.trade_tick_size
        pip_value = tick_value * (point / tick_size)
        
        # Calculate lot size
        lots = risk_amount / (sl_pips * pip_value)
        
        # Normalize to broker limits
        min_lot = symbol_info.volume_min
        max_lot = symbol_info.volume_max
        lot_step = symbol_info.volume_step
        
        lots = max(min_lot, min(lots, max_lot))
        lots = round(lots / lot_step) * lot_step
        lots = round(lots, 2)
        
        # Final validation
        if lots < min_lot:
            warnings.append(f"Position too small: {lots} < {min_lot}")
            lots = min_lot
        
        if lots > max_lot:
            warnings.append(f"Position too large: {lots} > {max_lot}")
            lots = max_lot
        
        # Additional safety checks
        max_allowed = self.max_position_size
        if lots > max_allowed:
            warnings.append(f"Exceeds max position size: {lots} > {max_allowed}")
            lots = max_allowed
        
        return PositionSize(
            lots=lots,
            risk_amount=risk_amount,
            risk_percent=final_risk * 100,
            adjusted_risk=final_risk * 100,
            sl_distance_pips=sl_pips,
            adjustments_applied=adjustments,
            warnings=warnings
        )
    
    def _adjust_for_confidence(self, confidence: float) -> float:
        """
        Adjust size based on signal confidence
        confidence: 0-1
        """
        # Linear scaling: 0.6 confidence = 0.6x size, 0.9 confidence = 0.9x size
        return max(0.5, min(confidence, 1.0))
    
    def _adjust_for_drawdown(self, current_balance: float) -> float:
        """
        Reduce size during drawdowns
        """
        if self.initial_balance is None:
            return 1.0
        
        drawdown = ((self.initial_balance - current_balance) / 
                   self.initial_balance * 100)
        
        if drawdown < 0:
            return 1.0  # In profit
        
        if drawdown < 5:
            return 1.0
        elif drawdown < 10:
            return 0.8
        elif drawdown < 15:
            return 0.6
        elif drawdown < 20:
            return 0.4
        else:
            return 0.2  # Severe drawdown
    
    def _adjust_for_volatility(self, volatility_ratio: float) -> float:
        """
        Adjust for current volatility vs average
        volatility_ratio: current_atr / average_atr
        """
        if volatility_ratio < 0.8:
            return 1.1  # Low volatility, can increase slightly
        elif volatility_ratio < 1.2:
            return 1.0  # Normal volatility
        elif volatility_ratio < 1.5:
            return 0.8  # Elevated volatility
        elif volatility_ratio < 2.0:
            return 0.6  # High volatility
        else:
            return 0.4  # Extreme volatility
    
    def _adjust_for_correlation(self, correlation_exposure: float) -> float:
        """
        Reduce size if too much correlated exposure
        correlation_exposure: total risk in correlated positions (%)
        """
        if correlation_exposure < 2.0:
            return 1.0
        elif correlation_exposure < 3.0:
            return 0.9
        elif correlation_exposure < 4.0:
            return 0.7
        elif correlation_exposure < 5.0:
            return 0.5
        else:
            return 0.3  # Too much correlation
    
    def _adjust_for_consecutive_losses(self) -> float:
        """
        Reduce size after consecutive losses
        """
        if len(self.trade_history) < 3:
            return 1.0
        
        # Check last 5 trades
        recent_trades = self.trade_history[-5:]
        consecutive_losses = 0
        
        for trade in reversed(recent_trades):
            if trade.get('profit', 0) < 0:
                consecutive_losses += 1
            else:
                break
        
        if consecutive_losses == 0:
            return 1.0
        elif consecutive_losses == 1:
            return 1.0
        elif consecutive_losses == 2:
            return 0.8
        elif consecutive_losses == 3:
            return 0.6
        elif consecutive_losses == 4:
            return 0.4
        else:
            return 0.3  # 5+ losses
    
    def _adjust_for_time(self) -> float:
        """
        Adjust based on day of week and time of day
        """
        now = datetime.now()
        
        # Friday afternoon - reduce size (weekend risk)
        if now.weekday() == 4 and now.hour >= 15:
            return 0.7
        
        # Monday morning - reduce size (weekend gap risk)
        if now.weekday() == 0 and now.hour < 10:
            return 0.8
        
        # Off-hours (22:00-06:00 GMT) - reduce size
        if now.hour >= 22 or now.hour < 6:
            return 0.6
        
        return 1.0
    
    def _create_minimal_position(self, warnings: List[str]) -> PositionSize:
        """
        Create minimal position when calculation fails
        """
        return PositionSize(
            lots=self.min_position_size,
            risk_amount=0,
            risk_percent=0,
            adjusted_risk=0,
            sl_distance_pips=0,
            adjustments_applied={},
            warnings=warnings
        )
    
    def record_trade(
        self,
        symbol: str,
        lots: float,
        entry_price: float,
        exit_price: float,
        profit: float
    ):
        """
        Record trade for future adjustments
        """
        self.trade_history.append({
            'symbol': symbol,
            'lots': lots,
            'entry': entry_price,
            'exit': exit_price,
            'profit': profit,
            'timestamp': datetime.now()
        })
        
        # Keep only last 100 trades
        if len(self.trade_history) > 100:
            self.trade_history = self.trade_history[-100:]
    
    def get_correlation_exposure(
        self,
        symbol: str,
        open_positions: List[Dict]
    ) -> float:
        """
        Calculate total exposure in correlated positions
        """
        # Simplified correlation matrix
        correlation_groups = {
            'EUR': ['EURUSD', 'EURJPY', 'EURGBP', 'EURAUD'],
            'GBP': ['GBPUSD', 'EURJPY', 'GBPJPY', 'GBPAUD'],
            'USD': ['EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD'],
            'JPY': ['USDJPY', 'EURJPY', 'GBPJPY'],
            'GOLD': ['XAUUSD', 'XAGUSD'],  # Gold and silver correlate
        }
        
        # Determine which group this symbol belongs to
        clean_symbol = symbol.replace('.', '').upper()
        symbol_groups = []
        
        for group, members in correlation_groups.items():
            if any(m in clean_symbol for m in members):
                symbol_groups.append(group)
        
        # Calculate total risk in correlated positions
        total_correlated_risk = 0.0
        
        for pos in open_positions:
            pos_symbol = pos.get('symbol', '').replace('.', '').upper()
            
            # Check if this position is in same correlation group
            for group in symbol_groups:
                if any(m in pos_symbol for m in correlation_groups[group]):
                    # Add this position's risk
                    total_correlated_risk += pos.get('risk_percent', 0)
                    break
        
        return total_correlated_risk
    
    def calculate_kelly_criterion(
        self,
        win_rate: float,
        avg_win: float,
        avg_loss: float
    ) -> float:
        """
        Calculate Kelly Criterion for position sizing
        Returns recommended risk percentage
        """
        if win_rate <= 0 or win_rate >= 1 or avg_loss <= 0:
            return self.base_risk_percent
        
        # Kelly formula: f = (p*b - q) / b
        # where p = win rate, q = loss rate, b = avg_win/avg_loss
        
        win_loss_ratio = avg_win / avg_loss
        kelly = (win_rate * win_loss_ratio - (1 - win_rate)) / win_loss_ratio
        
        # Use fractional Kelly (typically 25-50% of full Kelly)
        fractional_kelly = kelly * 0.25
        
        # Ensure within safe bounds
        recommended = max(0.5, min(fractional_kelly * 100, 2.0))
        
        return recommended
    
    def get_statistics(self) -> Dict:
        """
        Get position sizing statistics
        """
        if not self.trade_history:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'total_profit': 0
            }
        
        profits = [t['profit'] for t in self.trade_history]
        wins = [p for p in profits if p > 0]
        losses = [p for p in profits if p < 0]
        
        return {
            'total_trades': len(self.trade_history),
            'win_rate': len(wins) / len(self.trade_history) if self.trade_history else 0,
            'avg_win': np.mean(wins) if wins else 0,
            'avg_loss': abs(np.mean(losses)) if losses else 0,
            'total_profit': sum(profits),
            'largest_win': max(profits) if profits else 0,
            'largest_loss': min(profits) if profits else 0
        }
