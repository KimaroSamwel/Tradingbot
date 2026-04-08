"""
APEX FX Trading Bot - Risk Management
Position sizing, drawdown limits, max positions, correlation limits
"""

import MetaTrader5 as mt5
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import json
from pathlib import Path


class RiskManager:
    """Risk management system"""
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        
        # Risk Parameters (from config)
        self.max_risk_per_trade = self.config.get('max_risk_per_trade', 1.0)  # % of account
        self.max_daily_loss = self.config.get('max_daily_loss', 2.0)  # % of account
        self.max_concurrent_positions = self.config.get('max_concurrent_positions', 3)
        self.max_correlation = self.config.get('max_correlation', 0.7)  # Max correlation between positions
        
        # Account tracking
        self.daily_start_balance = 0
        self.daily_trades = []
        self.peak_equity = 0
        self.consecutive_losses = 0
        
        # Circuit breaker
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None
        
    def check_trade_allowed(self, account_balance: float, open_positions: List[Dict]) -> tuple[bool, str]:
        """Check if new trade is allowed"""
        
        # Check circuit breaker
        if self.circuit_breaker_active:
            if datetime.now() < self.circuit_breaker_until:
                return False, f"Circuit breaker active until {self.circuit_breaker_until.strftime('%H:%M')}"
            else:
                self.circuit_breaker_active = False
                self.consecutive_losses = 0
        
        # Check max positions
        if len(open_positions) >= self.max_concurrent_positions:
            return False, f"Max {self.max_concurrent_positions} positions reached"
        
        # Check daily loss limit
        if self.daily_start_balance > 0:
            daily_loss_pct = ((self.daily_start_balance - account_balance) / self.daily_start_balance) * 100
            if daily_loss_pct >= self.max_daily_loss:
                self._trigger_circuit_breaker(24)
                return False, f"Daily loss limit {self.max_daily_loss}% reached"
        
        # Check margin
        acc = mt5.account_info()
        if acc and acc.margin_level < 150:
            return False, f"Margin level low ({acc.margin_level:.0f}%)"
        
        if acc and acc.margin_free < 50:
            return False, f"Low free margin (${acc.margin_free:.2f})"
        
        return True, "OK"
    
    def calculate_position_size(self, symbol: str, account_balance: float, 
                                entry_price: float, sl_price: float) -> float:
        """Calculate position size based on risk"""
        
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            return 0.01
        
        # Calculate pip value
        point = symbol_info.point
        digits = symbol_info.digits
        
        # SL distance in price
        sl_distance = abs(entry_price - sl_price)
        
        # Convert to pips
        if 'JPY' in symbol:
            sl_pips = sl_distance * 100  # JPY pairs
        else:
            sl_pips = sl_distance / point / 10  # Other pairs
        
        if sl_pips <= 0:
            sl_pips = 100  # Default to 100 pips if calculation fails
        
        # Risk amount in dollars
        risk_amount = account_balance * (self.max_risk_per_trade / 100)
        
        # Pip value per lot
        if 'XAU' in symbol:
            pip_value = 100  # $100 per pip for gold
        elif 'JPY' in symbol:
            pip_value = 1000  # JPY pairs
        else:
            pip_value = 10  # Standard Forex
        
        # Calculate lot size
        lot_size = risk_amount / (sl_pips * pip_value)
        
        # Apply limits
        min_lot = symbol_info.volume_min
        max_lot = symbol_info.volume_max
        
        lot_size = max(min_lot, min(max_lot, lot_size))
        
        return round(lot_size, 2)
    
    def calculate_risk_reward(self, entry: float, sl: float, tp: float, direction: str) -> float:
        """Calculate risk-reward ratio"""
        
        if direction.upper() == 'BUY':
            risk = entry - sl
            reward = tp - entry
        else:
            risk = sl - entry
            reward = entry - tp
        
        if risk <= 0:
            return 0
            
        return round(reward / risk, 2)
    
    def validate_stop_loss(self, entry: float, sl: float, direction: str) -> tuple[bool, str]:
        """Validate stop loss"""
        
        if sl <= 0:
            return False, "Invalid SL price"
        
        # Minimum distance (based on symbol)
        # This would be symbol-specific in production
        
        return True, "OK"
    
    def check_correlation(self, positions: List[Dict], new_symbol: str) -> tuple[bool, str]:
        """Check correlation with existing positions"""
        
        # Define correlation groups
        correlations = {
            'EURUSD': ['GBPUSD', 'USDCHF', 'AUDUSD'],
            'GBPUSD': ['EURUSD', 'USDCHF'],
            'USDJPY': ['USDCHF', 'USDCAD'],
            'XAUUSD': ['XAGUSD'],
        }
        
        new_corrs = correlations.get(new_symbol, [])
        
        for pos in positions:
            if pos.get('symbol') in new_corrs:
                return False, f"Correlation conflict with {pos['symbol']}"
        
        return True, "OK"
    
    def update_consecutive_losses(self, profit: float):
        """Update consecutive losses counter"""
        if profit < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 3:
                self._trigger_circuit_breaker(4)
        else:
            self.consecutive_losses = 0
    
    def _trigger_circuit_breaker(self, hours: int):
        """Trigger circuit breaker"""
        self.circuit_breaker_active = True
        self.circuit_breaker_until = datetime.now() + timedelta(hours=hours)
        print(f"⚠️ CIRCUIT BREAKER TRIGGERED! Paused for {hours} hours")
    
    def start_daily_tracking(self, balance: float):
        """Initialize daily tracking"""
        if self.daily_start_balance == 0:
            self.daily_start_balance = balance
            self.daily_trades = []
    
    def get_risk_metrics(self, account_balance: float, open_positions: List[Dict]) -> Dict[str, Any]:
        """Get current risk metrics"""
        
        current_equity = account_balance
        
        # Daily loss
        daily_loss_pct = 0
        if self.daily_start_balance > 0:
            daily_loss_pct = ((self.daily_start_balance - current_equity) / self.daily_start_balance) * 100
        
        # Drawdown
        drawdown_pct = 0
        if self.peak_equity > 0:
            drawdown_pct = ((self.peak_equity - current_equity) / self.peak_equity) * 100
        
        # Exposure
        total_exposure = sum(p.get('volume', 0) * p.get('current', 0) for p in open_positions)
        exposure_pct = (total_exposure / account_balance * 100) if account_balance > 0 else 0
        
        return {
            'daily_loss_pct': round(daily_loss_pct, 2),
            'drawdown_pct': round(drawdown_pct, 2),
            'exposure_pct': round(exposure_pct, 2),
            'positions_count': len(open_positions),
            'max_positions': self.max_concurrent_positions,
            'consecutive_losses': self.consecutive_losses,
            'circuit_breaker_active': self.circuit_breaker_active,
            'risk_per_trade_pct': self.max_risk_per_trade,
            'daily_loss_limit_pct': self.max_daily_loss
        }


# Global instance
risk_manager = RiskManager()


def get_risk_manager() -> RiskManager:
    """Get global risk manager instance"""
    return risk_manager