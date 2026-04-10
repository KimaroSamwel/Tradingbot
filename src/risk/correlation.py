"""
APEX FX Trading Bot - Correlation Manager
Section 5.5: Portfolio-Level Risk Controls - Correlation Controls
Manages cross-pair exposure based on correlation rules
"""

from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class TradeDirection(Enum):
    BUY = "BUY"
    SELL = "SELL"
    NONE = "NONE"


@dataclass
class Position:
    """Open position information"""
    symbol: str
    direction: TradeDirection
    lots: float
    entry_price: float
    risk_pct: float
    opened_at: datetime


class CorrelationManager:
    """
    PRD Section 5.5 Correlation Controls:
    - EUR/USD + USD/CHF: Cannot hold same direction (inverse correlation)
    - EUR/USD + GBP/USD: Max combined exposure = 2.5% of account
    - USD/CAD + XAU/USD: Total risk capped at 1.5% when both spiking
    """
    
    def __init__(self, account_balance: float = 10000):
        self.account_balance = account_balance
        self.positions: Dict[str, Position] = {}
        
        self.max_combined_eurusd_gbpusd = 2.5  # 2.5% of account
        self.max_combined_usdcad_xau = 1.5  # 1.5% when both commodity-correlated
        
        self.correlation_rules = {
            ('EURUSD', 'USDCHF'): {
                'type': 'inverse',
                'coefficient': -0.85,
                'allowed_same_direction': False
            },
            ('EURUSD', 'GBPUSD'): {
                'type': 'positive',
                'coefficient': 0.7,
                'max_combined_risk_pct': 2.5
            },
            ('USDCAD', 'XAUUSD'): {
                'type': 'commodity_correlation',
                'coefficient': 0.3,
                'max_combined_risk_pct': 1.5,
                'spike_threshold': 0.5  # ATR ratio for spike detection
            }
        }
    
    def add_position(self, position: Position) -> bool:
        """Add a new position, returns True if allowed"""
        if not self._validate_new_position(position):
            return False
        
        self.positions[position.symbol] = position
        return True
    
    def remove_position(self, symbol: str) -> bool:
        """Remove a closed position"""
        if symbol in self.positions:
            del self.positions[symbol]
            return True
        return False
    
    def _validate_new_position(self, new_pos: Position) -> bool:
        """Validate new position against correlation rules"""
        
        for (sym1, sym2), rule in self.correlation_rules.items():
            if new_pos.symbol not in [sym1, sym2]:
                continue
            
            other_symbol = sym2 if new_pos.symbol == sym1 else sym1
            
            if other_symbol not in self.positions:
                continue
            
            other_pos = self.positions[other_symbol]
            
            if rule['type'] == 'inverse':
                if not self._check_inverse_correlation(new_pos, other_pos, rule):
                    return False
            
            elif rule['type'] == 'positive':
                if not self._check_positive_correlation(new_pos, other_pos, rule):
                    return False
            
            elif rule['type'] == 'commodity_correlation':
                if not self._check_commodity_correlation(new_pos, other_pos, rule):
                    return False
        
        return True
    
    def _check_inverse_correlation(self, new_pos: Position, other_pos: Position, rule: Dict) -> bool:
        """Check inverse correlation rule (EUR/USD + USD/CHF)"""
        if not rule.get('allowed_same_direction', True):
            if new_pos.direction == other_pos.direction:
                return False
        return True
    
    def _check_positive_correlation(self, new_pos: Position, other_pos: Position, rule: Dict) -> bool:
        """Check positive correlation rule (EUR/USD + GBP/USD)"""
        max_combined = rule.get('max_combined_risk_pct', 2.5)
        
        combined_risk = new_pos.risk_pct + other_pos.risk_pct
        
        if combined_risk > max_combined:
            if new_pos.risk_pct > other_pos.risk_pct:
                new_pos.risk_pct = max(0, max_combined - other_pos.risk_pct)
                combined_risk = new_pos.risk_pct + other_pos.risk_pct
            
            if combined_risk > max_combined:
                return False
        
        return True
    
    def _check_commodity_correlation(self, new_pos: Position, other_pos: Position, rule: Dict) -> bool:
        """Check commodity correlation rule (USD/CAD + XAU/USD)"""
        max_combined = rule.get('max_combined_risk_pct', 1.5)
        
        combined_risk = new_pos.risk_pct + other_pos.risk_pct
        
        if combined_risk > max_combined:
            return False
        
        return True
    
    def can_open_position(self, symbol: str, direction: TradeDirection, risk_pct: float) -> Tuple[bool, str]:
        """Check if a new position can be opened"""
        
        if symbol in self.positions:
            return False, f"Position already open for {symbol}"
        
        temp_pos = Position(
            symbol=symbol,
            direction=direction,
            lots=0,
            entry_price=0,
            risk_pct=risk_pct,
            opened_at=datetime.now()
        )
        
        if self._validate_new_position(temp_pos):
            return True, "Allowed"
        
        return False, "Blocked by correlation rule"
    
    def get_blocked_pairs(self, symbol: str) -> List[str]:
        """Get list of pairs blocked by correlation with given symbol"""
        blocked = []
        
        for (sym1, sym2), rule in self.correlation_rules.items():
            if symbol not in [sym1, sym2]:
                continue
            
            other_symbol = sym2 if symbol == sym1 else sym1
            
            if rule['type'] == 'inverse':
                if symbol in self.positions:
                    if self.positions[symbol].direction != TradeDirection.NONE:
                        blocked.append(other_symbol)
        
        return blocked
    
    def get_current_exposure(self, symbol1: str, symbol2: str) -> float:
        """Get combined risk exposure between two symbols"""
        exposure = 0
        
        if symbol1 in self.positions:
            exposure += self.positions[symbol1].risk_pct
        if symbol2 in self.positions:
            exposure += self.positions[symbol2].risk_pct
        
        return exposure
    
    def reset(self):
        """Reset all positions (e.g., after daily reset)"""
        self.positions = {}
    
    def get_status(self) -> Dict:
        """Get correlation manager status"""
        return {
            'active_positions': len(self.positions),
            'positions': {
                sym: {
                    'direction': pos.direction.value,
                    'risk_pct': pos.risk_pct
                }
                for sym, pos in self.positions.items()
            },
            'eurusd_gbpusd_exposure': self.get_current_exposure('EURUSD', 'GBPUSD'),
            'usdcad_xau_exposure': self.get_current_exposure('USDCAD', 'XAUUSD')
        }


_correlation_manager = None


def get_correlation_manager(account_balance: float = 10000) -> CorrelationManager:
    """Get global correlation manager instance"""
    global _correlation_manager
    if _correlation_manager is None:
        _correlation_manager = CorrelationManager(account_balance)
    return _correlation_manager