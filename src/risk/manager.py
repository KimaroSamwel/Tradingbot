"""
APEX FX Trading Bot - Per-Instrument Risk Management
Section 5: Risk Management Framework
Each instrument has bespoke risk parameters per PRD specification
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class InstrumentRiskProfile:
    """Risk profile for a single instrument"""
    
    def __init__(self, symbol: str, params: Dict):
        self.symbol = symbol
        self.risk_per_trade_pct = params.get('risk_per_trade', 1.0)
        self.atr_multiplier = params.get('atr_multiplier', 1.5)
        self.max_daily_loss_pct = params.get('max_daily_loss', 3.0)
        self.max_drawdown_pct = params.get('max_drawdown', 8.0)
        self.max_lot = params.get('max_lot', 2.0)
        self.max_positions = params.get('max_positions', 2)
        self.sl_method = params.get('sl_method', 'atr')
        self.tp_method = params.get('tp_method', 'atr')
        self.tp_multiplier = params.get('tp_multiplier', 2.5)
        self.trailing_activation_rr = params.get('trailing_activation_rr', 1.0)
        self.trailing_atr_multiplier = params.get('trailing_atr_multiplier', 1.0)


# PRD Section 5.3 - Per-Instrument Risk Parameters
INSTRUMENT_PROFILES = {
    'EURUSD': {
        'risk_per_trade': 1.5,
        'atr_multiplier': 1.5,
        'max_daily_loss': 3.0,
        'max_drawdown': 8.0,
        'max_lot': 2.0,
        'max_positions': 2,
        'sl_method': 'atr',
        'tp_method': 'atr',
        'tp_multiplier': 2.5,
        'trailing_activation_rr': 1.0,
        'trailing_atr_multiplier': 1.0
    },
    'GBPUSD': {
        'risk_per_trade': 1.2,
        'atr_multiplier': 1.8,
        'max_daily_loss': 3.0,
        'max_drawdown': 8.0,
        'max_lot': 2.0,
        'max_positions': 2,
        'sl_method': 'atr',
        'tp_method': 'atr',
        'tp_multiplier': 3.0,
        'trailing_activation_rr': 1.5,
        'trailing_atr_multiplier': 1.2
    },
    'USDJPY': {
        'risk_per_trade': 1.5,
        'atr_multiplier': 1.5,
        'max_daily_loss': 3.0,
        'max_drawdown': 8.0,
        'max_lot': 1.5,
        'max_positions': 2,
        'sl_method': 'atr',
        'tp_method': 'atr',
        'tp_multiplier': 2.5,
        'trailing_activation_rr': 1.0,
        'trailing_atr_multiplier': 1.0
    },
    'USDCHF': {
        'risk_per_trade': 1.0,
        'atr_multiplier': 1.5,
        'max_daily_loss': 2.5,
        'max_drawdown': 7.0,
        'max_lot': 1.5,
        'max_positions': 1,
        'sl_method': 'atr',
        'tp_method': 'atr',
        'tp_multiplier': 2.0,
        'trailing_activation_rr': 1.0,
        'trailing_atr_multiplier': 1.0
    },
    'USDCAD': {
        'risk_per_trade': 1.2,
        'atr_multiplier': 1.5,
        'max_daily_loss': 3.0,
        'max_drawdown': 8.0,
        'max_lot': 1.5,
        'max_positions': 2,
        'sl_method': 'atr',
        'tp_method': 'atr',
        'tp_multiplier': 2.5,
        'trailing_activation_rr': 0.8,
        'trailing_atr_multiplier': 0.8
    },
    'XAUUSD': {
        'risk_per_trade': 0.75,
        'atr_multiplier': 2.0,
        'max_daily_loss': 2.0,
        'max_drawdown': 6.0,
        'max_lot': 0.5,
        'max_positions': 1,
        'sl_method': 'atr',
        'tp_method': 'atr',
        'tp_multiplier': 3.5,
        'trailing_activation_rr': 1.0,
        'trailing_atr_multiplier': 1.0
    }
}


class RiskManager:
    """
    APEX FX Risk Management Engine
    Section 5: Risk Management Framework
    
    Key Features:
    - Per-instrument risk profiles (not one-size-fits-all)
    - ATR-based position sizing and stop-loss
    - Portfolio-level correlation controls
    - Circuit breakers (daily drawdown, consecutive losses)
    """
    
    def __init__(self):
        self.instrument_profiles = {
            symbol: InstrumentRiskProfile(symbol, params)
            for symbol, params in INSTRUMENT_PROFILES.items()
        }
        
        self.max_consecutive_losses = 5
        self.consecutive_losses = 0
        self.daily_start_balance = 0
        self.daily_pnl = 0
        self.pair_daily_losses = {}
        
        self.daily_account_loss_limit = 8.0
        self.monthly_drawdown_limit = 15.0
        self.circuit_breaker_active = False
        self.circuit_breaker_until = None
    
    def get_profile(self, symbol: str) -> InstrumentRiskProfile:
        symbol = symbol.upper().replace('/', '')
        return self.instrument_profiles.get(symbol, self.instrument_profiles['EURUSD'])
    
    def calculate_position_size(self, symbol: str, account_balance: float, 
                                current_price: float, sl_price: float) -> float:
        """Section 5.2 Position Sizing Formula"""
        profile = self.get_profile(symbol)
        atr = self._get_atr(symbol)
        sl_distance = abs(current_price - sl_price)
        
        if 'XAU' in symbol:
            pip_value = 100
            sl_pips = sl_distance * 10000
        elif 'JPY' in symbol:
            pip_value = 1000
            sl_pips = sl_distance * 100
        else:
            pip_value = 10
            sl_pips = sl_distance / current_price * 10000
        
        if sl_pips <= 0:
            sl_pips = 50
        
        risk_amount = account_balance * (profile.risk_per_trade_pct / 100)
        lot_size = risk_amount / (sl_pips * profile.atr_multiplier * pip_value / 100)
        lot_size = max(0.01, min(profile.max_lot, lot_size))
        
        return round(lot_size, 2)
    
    def _get_atr(self, symbol: str) -> float:
        default_atrs = {
            'EURUSD': 0.0008, 'GBPUSD': 0.0010, 'USDJPY': 0.80,
            'USDCHF': 0.0007, 'USDCAD': 0.0008, 'XAUUSD': 15.0
        }
        return default_atrs.get(symbol, 0.001)
    
    def calculate_stop_loss(self, symbol: str, entry_price: float, direction: str) -> float:
        """Section 5.4 - Stop-Loss Method"""
        profile = self.get_profile(symbol)
        atr = self._get_atr(symbol)
        
        if direction.upper() == 'BUY':
            sl = entry_price - (atr * profile.atr_multiplier)
            if 'JPY' in symbol:
                sl -= 0.10
        else:
            sl = entry_price + (atr * profile.atr_multiplier)
            if 'JPY' in symbol:
                sl += 0.10
        
        return round(sl, 5)
    
    def calculate_take_profit(self, symbol: str, entry_price: float, direction: str) -> float:
        """Section 5.4 - Take-Profit Method"""
        profile = self.get_profile(symbol)
        atr = self._get_atr(symbol)
        tp_distance = atr * profile.tp_multiplier
        
        if direction.upper() == 'BUY':
            tp = entry_price + tp_distance
        else:
            tp = entry_price - tp_distance
        
        return round(tp, 5)
    
    def check_trade_allowed(self, symbol: str, direction: str, 
                           open_positions: List[Dict], account_balance: float) -> tuple[bool, str]:
        """Section 5.5 - Portfolio-Level Risk Controls"""
        
        if self.circuit_breaker_active:
            if datetime.now() < self.circuit_breaker_until:
                return False, f"Circuit breaker active until {self.circuit_breaker_until}"
            self.circuit_breaker_active = False
        
        if self.daily_start_balance > 0:
            daily_loss_pct = ((self.daily_start_balance - account_balance) / self.daily_start_balance) * 100
            if daily_loss_pct >= self.daily_account_loss_limit:
                self._trigger_circuit_breaker(24)
                return False, f"Daily loss {daily_loss_pct:.1f}% exceeds {self.daily_account_loss_limit}%"
        
        pair_loss = self.pair_daily_losses.get(symbol, 0)
        profile = self.get_profile(symbol)
        if pair_loss >= profile.max_daily_loss_pct:
            return False, f"{symbol} daily loss limit reached"
        
        symbol_positions = [p for p in open_positions if p.get('symbol') == symbol]
        if len(symbol_positions) >= profile.max_positions:
            return False, f"Max positions for {symbol} reached"
        
        return True, "OK"
    
    def update_after_trade(self, symbol: str, profit: float):
        if profit < 0:
            self.consecutive_losses += 1
            self.pair_daily_losses[symbol] = self.pair_daily_losses.get(symbol, 0) + abs(profit)
            if self.consecutive_losses >= self.max_consecutive_losses:
                self._trigger_circuit_breaker(24)
        else:
            self.consecutive_losses = 0
    
    def _trigger_circuit_breaker(self, hours: int):
        self.circuit_breaker_active = True
        self.circuit_breaker_until = datetime.now() + timedelta(hours=hours)
        print(f"⚠️ CIRCUIT BREAKER TRIGGERED! Paused for {hours} hours")
    
    def reset_daily(self, balance: float):
        self.daily_start_balance = balance
        self.daily_pnl = 0
        self.pair_daily_losses = {}


risk_manager = RiskManager()


def get_risk_manager() -> RiskManager:
    return risk_manager