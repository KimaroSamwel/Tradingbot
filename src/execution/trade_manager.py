"""
Trade Manager with Advanced Trailing Stops
Activates at 1:1 RR, trails at 0.5x ATR
Manages breakeven, partial exits, and position lifecycle
"""

import MetaTrader5 as mt5
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass


@dataclass
class TrailingStopConfig:
    """Configuration for trailing stop"""
    activation_ratio: float = 1.0
    trail_distance_atr_multiplier: float = 0.5
    trail_step_pips: float = 5.0
    breakeven_ratio: float = 0.5
    partial_exit_enabled: bool = True
    partial_exit_ratio: float = 0.5
    partial_exit_percent: float = 50.0


class TradeManager:
    """
    Comprehensive trade management system
    - Trailing stops (activates at 1:1 RR)
    - Breakeven management
    - Partial profit taking
    - Position lifecycle tracking
    """
    
    def __init__(self, config: TrailingStopConfig = None):
        self.config = config or TrailingStopConfig()
        self.managed_positions = {}
    
    def add_position(self, ticket: int, entry_price: float, sl: float, 
                    tp: float, lot_size: float, position_type: str):
        """Add position to management"""
        initial_risk = abs(entry_price - sl)
        
        self.managed_positions[ticket] = {
            'entry_price': entry_price,
            'original_sl': sl,
            'original_tp': tp,
            'current_sl': sl,
            'current_tp': tp,
            'lot_size': lot_size,
            'position_type': position_type,
            'initial_risk': initial_risk,
            'trailing_active': False,
            'breakeven_set': False,
            'partial_exit_done': False,
            'peak_price': entry_price,
            'last_update': datetime.now()
        }
    
    def update_position(self, ticket: int, current_price: float, atr: float) -> Dict:
        """
        Update position management (trailing, breakeven, etc.)
        
        Returns:
            Dict with actions taken
        """
        if ticket not in self.managed_positions:
            return {'status': 'not_managed'}
        
        position = mt5.positions_get(ticket=ticket)
        if not position or len(position) == 0:
            del self.managed_positions[ticket]
            return {'status': 'position_closed'}
        
        pos = position[0]
        managed = self.managed_positions[ticket]
        actions = []
        
        # Update peak price
        if managed['position_type'] == 'BUY':
            if current_price > managed['peak_price']:
                managed['peak_price'] = current_price
        else:
            if current_price < managed['peak_price']:
                managed['peak_price'] = current_price
        
        # Calculate profit
        if managed['position_type'] == 'BUY':
            profit = current_price - managed['entry_price']
        else:
            profit = managed['entry_price'] - current_price
        
        profit_in_risk = profit / managed['initial_risk']
        
        # 1. Breakeven Management (at 0.5:1)
        if not managed['breakeven_set'] and profit_in_risk >= self.config.breakeven_ratio:
            if self._move_to_breakeven(ticket, managed):
                managed['breakeven_set'] = True
                actions.append('moved_to_breakeven')
        
        # 2. Partial Exit (at 1:1)
        if (self.config.partial_exit_enabled and not managed['partial_exit_done'] 
            and profit_in_risk >= 1.0):
            if self._partial_exit(ticket, managed):
                managed['partial_exit_done'] = True
                actions.append('partial_exit')
        
        # 3. Activate Trailing Stop (at 1:1)
        if not managed['trailing_active'] and profit_in_risk >= self.config.activation_ratio:
            managed['trailing_active'] = True
            actions.append('trailing_activated')
        
        # 4. Update Trailing Stop
        if managed['trailing_active']:
            if self._update_trailing_stop(ticket, managed, current_price, atr):
                actions.append('trailing_updated')
        
        managed['last_update'] = datetime.now()
        
        return {
            'status': 'updated',
            'actions': actions,
            'profit_ratio': profit_in_risk,
            'trailing_active': managed['trailing_active']
        }
    
    def _move_to_breakeven(self, ticket: int, managed: Dict) -> bool:
        """Move stop loss to breakeven"""
        entry_price = managed['entry_price']
        
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False
        
        pos = position[0]
        
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": pos.symbol,
            "position": ticket,
            "sl": entry_price,
            "tp": pos.tp,
            "magic": pos.magic,
            "comment": "Breakeven"
        }
        
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            managed['current_sl'] = entry_price
            print(f"✅ Breakeven set: {pos.symbol} #{ticket} SL → {entry_price:.5f}")
            return True
        else:
            print(f"❌ Failed to set breakeven: {result.comment}")
            return False
    
    def _partial_exit(self, ticket: int, managed: Dict) -> bool:
        """Close partial position at profit target"""
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False
        
        pos = position[0]
        
        exit_volume = pos.volume * (self.config.partial_exit_percent / 100)
        exit_volume = max(0.01, round(exit_volume, 2))
        
        if managed['position_type'] == 'BUY':
            order_type = mt5.ORDER_TYPE_SELL
        else:
            order_type = mt5.ORDER_TYPE_BUY
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": exit_volume,
            "type": order_type,
            "position": ticket,
            "magic": pos.magic,
            "comment": "Partial Exit 50%"
        }
        
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            managed['lot_size'] -= exit_volume
            print(f"💰 Partial exit: {pos.symbol} #{ticket} closed {exit_volume} lots (50%)")
            return True
        else:
            print(f"❌ Failed partial exit: {result.comment}")
            return False
    
    def _update_trailing_stop(self, ticket: int, managed: Dict, 
                              current_price: float, atr: float) -> bool:
        """Update trailing stop loss"""
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False
        
        pos = position[0]
        trail_distance = atr * self.config.trail_distance_atr_multiplier
        
        if managed['position_type'] == 'BUY':
            new_sl = managed['peak_price'] - trail_distance
            
            if new_sl > pos.sl and new_sl < current_price:
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": pos.symbol,
                    "position": ticket,
                    "sl": new_sl,
                    "tp": pos.tp,
                    "magic": pos.magic,
                    "comment": "Trailing Stop"
                }
                
                result = mt5.order_send(request)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    managed['current_sl'] = new_sl
                    print(f"📈 Trailing updated: BUY #{ticket} SL → {new_sl:.5f} "
                          f"(Peak: {managed['peak_price']:.5f})")
                    return True
        
        else:
            new_sl = managed['peak_price'] + trail_distance
            
            if new_sl < pos.sl and new_sl > current_price:
                request = {
                    "action": mt5.TRADE_ACTION_SLTP,
                    "symbol": pos.symbol,
                    "position": ticket,
                    "sl": new_sl,
                    "tp": pos.tp,
                    "magic": pos.magic,
                    "comment": "Trailing Stop"
                }
                
                result = mt5.order_send(request)
                
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    managed['current_sl'] = new_sl
                    print(f"📉 Trailing updated: SELL #{ticket} SL → {new_sl:.5f} "
                          f"(Peak: {managed['peak_price']:.5f})")
                    return True
        
        return False
    
    def update_all_positions(self, atr_values: Dict[str, float]):
        """Update all managed positions"""
        positions = mt5.positions_get()
        if not positions:
            return
        
        for position in positions:
            if position.ticket in self.managed_positions:
                symbol = position.symbol
                if symbol in atr_values:
                    current_price = position.price_current
                    self.update_position(position.ticket, current_price, atr_values[symbol])
    
    def get_position_status(self, ticket: int) -> Optional[Dict]:
        """Get current status of managed position"""
        return self.managed_positions.get(ticket)
    
    def get_summary(self) -> Dict:
        """Get summary of all managed positions"""
        total = len(self.managed_positions)
        trailing_active = sum(1 for p in self.managed_positions.values() if p['trailing_active'])
        breakeven_set = sum(1 for p in self.managed_positions.values() if p['breakeven_set'])
        partial_exits = sum(1 for p in self.managed_positions.values() if p['partial_exit_done'])
        
        return {
            'total_managed': total,
            'trailing_active': trailing_active,
            'breakeven_set': breakeven_set,
            'partial_exits_done': partial_exits,
            'positions': self.managed_positions
        }
    
    def remove_position(self, ticket: int):
        """Remove position from management"""
        if ticket in self.managed_positions:
            del self.managed_positions[ticket]


class TimedExitManager:
    """
    Manage time-based exits
    Close positions after certain time if not hitting targets
    """
    
    def __init__(self, max_hold_hours: int = 24):
        self.max_hold_hours = max_hold_hours
        self.position_start_times = {}
    
    def add_position(self, ticket: int):
        """Track position start time"""
        self.position_start_times[ticket] = datetime.now()
    
    def check_time_exit(self, ticket: int) -> bool:
        """Check if position should be closed due to time"""
        if ticket not in self.position_start_times:
            return False
        
        start_time = self.position_start_times[ticket]
        hours_held = (datetime.now() - start_time).total_seconds() / 3600
        
        return hours_held >= self.max_hold_hours
    
    def execute_time_exit(self, ticket: int) -> bool:
        """Close position due to time limit"""
        position = mt5.positions_get(ticket=ticket)
        if not position:
            return False
        
        pos = position[0]
        
        if pos.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
        else:
            order_type = mt5.ORDER_TYPE_BUY
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": pos.symbol,
            "volume": pos.volume,
            "type": order_type,
            "position": ticket,
            "magic": pos.magic,
            "comment": "Time Exit"
        }
        
        result = mt5.order_send(request)
        
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            print(f"⏰ Time exit: {pos.symbol} #{ticket} closed after {self.max_hold_hours}h")
            del self.position_start_times[ticket]
            return True
        
        return False
