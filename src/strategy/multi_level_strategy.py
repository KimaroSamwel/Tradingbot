"""
Multi-Level Strategy - Opens multiple trades at planned intervals when market moves against position

Key Features:
- Opens additional trades as price moves against initial position
- Lowers average entry price
- All trades aim to close together in profit once price reverses
- Configurable trade distance, multipliers, and max trades

Based on KimzBOT Multi-Level Strategy configuration
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class RiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    AGGRESSIVE = "aggressive"


@dataclass
class MultiLevelConfig:
    """Configuration for Multi-Level Strategy"""
    # Risk settings
    risk_level: RiskLevel = RiskLevel.MEDIUM
    drawdown_limit: float = 50.0  # Max drawdown %
    
    # Trade parameters
    trade_distance: int = 30  # Pips between levels
    take_profit: int = 12  # Pips for TP
    stop_loss: int = 0  # 0 = no SL (use drawdown limit instead)
    
    # Multipliers
    second_level_multiplier: float = 1.0  # Lot multiplier for 2nd trade
    multiplier_after_second: float = 2.0  # Lot multiplier for 3rd+ trades
    
    # Limits
    max_trades: int = 8  # Maximum number of trades in basket
    max_spread: int = 30  # Max spread in points
    max_slippage: int = 10  # Max slippage in points
    
    # Timeframe
    timeframe: str = "M15"
    
    # Entry strategy
    entry_strategy: str = "default"  # RSI + BB + Stochastic
    
    # Filters
    news_filter: bool = True
    ai_decision: bool = True


@dataclass
class TradeLevel:
    """Represents a single trade level in the basket"""
    ticket: int
    entry_price: float
    lot_size: float
    level: int
    direction: str  # 'buy' or 'sell'
    entry_time: datetime
    
    
@dataclass
class TradeBasket:
    """Manages a basket of trades for a symbol"""
    symbol: str
    direction: str
    levels: List[TradeLevel] = field(default_factory=list)
    average_price: float = 0.0
    total_lots: float = 0.0
    common_tp: float = 0.0
    
    def add_level(self, level: TradeLevel):
        self.levels.append(level)
        self._recalculate()
    
    def _recalculate(self):
        """Recalculate average price and total lots"""
        if not self.levels:
            return
        
        total_value = sum(l.entry_price * l.lot_size for l in self.levels)
        self.total_lots = sum(l.lot_size for l in self.levels)
        self.average_price = total_value / self.total_lots if self.total_lots > 0 else 0
        
        # Set common TP near average price
        pip_size = 0.01 if 'JPY' in self.symbol else 0.0001
        if self.direction == 'buy':
            self.common_tp = self.average_price + (12 * pip_size)  # 12 pips above average
        else:
            self.common_tp = self.average_price - (12 * pip_size)  # 12 pips below average


class DefaultEntryStrategy:
    """
    Default Entry Strategy using RSI, Bollinger Bands, and Stochastic
    
    Entry logic:
    - Waits for price to stretch beyond key zones
    - Confirms momentum and reversal signals across multiple indicators
    - Executes buy/sell only when all filters align
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.rsi_period = self.config.get('rsi_period', 14)
        self.rsi_oversold = self.config.get('rsi_oversold', 30)
        self.rsi_overbought = self.config.get('rsi_overbought', 70)
        self.bb_period = self.config.get('bb_period', 20)
        self.bb_std = self.config.get('bb_std', 2.0)
        self.stoch_k = self.config.get('stoch_k', 14)
        self.stoch_d = self.config.get('stoch_d', 3)
        self.stoch_oversold = self.config.get('stoch_oversold', 20)
        self.stoch_overbought = self.config.get('stoch_overbought', 80)
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate all indicators needed for entry signals"""
        import talib
        
        # RSI
        df['rsi'] = talib.RSI(df['close'], timeperiod=self.rsi_period)
        
        # Bollinger Bands
        df['bb_upper'], df['bb_middle'], df['bb_lower'] = talib.BBANDS(
            df['close'], timeperiod=self.bb_period, nbdevup=self.bb_std, nbdevdn=self.bb_std
        )
        
        # Stochastic
        df['stoch_k'], df['stoch_d'] = talib.STOCH(
            df['high'], df['low'], df['close'],
            fastk_period=self.stoch_k, slowk_period=self.stoch_d, slowd_period=self.stoch_d
        )
        
        # Price position relative to BB
        df['bb_position'] = (df['close'] - df['bb_lower']) / (df['bb_upper'] - df['bb_lower'])
        
        return df
    
    def get_entry_signal(self, df: pd.DataFrame) -> Optional[str]:
        """
        Get entry signal based on multi-indicator confirmation
        
        Returns:
            'buy', 'sell', or None
        """
        if len(df) < 50:
            return None
        
        df = self.calculate_indicators(df)
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # BUY CONDITIONS (reversal from oversold)
        buy_conditions = [
            last['rsi'] < 40,  # RSI in lower zone
            last['close'] <= last['bb_lower'] * 1.001,  # Price at or below lower BB
            last['stoch_k'] < 30,  # Stochastic oversold
            last['stoch_k'] > prev['stoch_k'],  # Stochastic turning up
        ]
        
        # SELL CONDITIONS (reversal from overbought)
        sell_conditions = [
            last['rsi'] > 60,  # RSI in upper zone
            last['close'] >= last['bb_upper'] * 0.999,  # Price at or above upper BB
            last['stoch_k'] > 70,  # Stochastic overbought
            last['stoch_k'] < prev['stoch_k'],  # Stochastic turning down
        ]
        
        buy_score = sum(buy_conditions)
        sell_score = sum(sell_conditions)
        
        # Need at least 3 out of 4 conditions
        if buy_score >= 3:
            return 'buy'
        elif sell_score >= 3:
            return 'sell'
        
        return None


class MultiLevelStrategy:
    """
    Multi-Level Strategy Implementation
    
    Opens multiple trades at planned intervals when market moves against position.
    All trades aim to close together in profit once price reverses.
    """
    
    def __init__(self, config: MultiLevelConfig = None):
        self.config = config or MultiLevelConfig()
        self.entry_strategy = DefaultEntryStrategy()
        self.baskets: Dict[str, TradeBasket] = {}  # symbol -> basket
        self.initial_balance = 0.0
        self.magic_number = 200888
        
        # Risk level lot sizes (base lot for $1000 account)
        self.risk_lots = {
            RiskLevel.LOW: 0.01,
            RiskLevel.MEDIUM: 0.02,
            RiskLevel.HIGH: 0.05,
            RiskLevel.AGGRESSIVE: 0.1
        }
    
    def initialize(self, account_balance: float):
        """Initialize strategy with account balance"""
        self.initial_balance = account_balance
    
    def get_base_lot_size(self, account_balance: float) -> float:
        """Calculate base lot size based on risk level and account size"""
        base = self.risk_lots.get(self.config.risk_level, 0.02)
        # Scale with account size (base is for $1000)
        scale = account_balance / 1000.0
        return round(base * scale, 2)
    
    def get_level_lot_size(self, base_lot: float, level: int) -> float:
        """Calculate lot size for a specific level"""
        if level == 1:
            return base_lot
        elif level == 2:
            return round(base_lot * self.config.second_level_multiplier, 2)
        else:
            # Level 3+: multiply by multiplier_after_second for each level
            multiplier = self.config.multiplier_after_second ** (level - 2)
            return round(base_lot * multiplier, 2)
    
    def check_spread(self, symbol: str) -> bool:
        """Check if spread is acceptable"""
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return False
        
        spread_points = (tick.ask - tick.bid) / mt5.symbol_info(symbol).point
        return spread_points <= self.config.max_spread
    
    def check_drawdown(self, current_balance: float) -> bool:
        """Check if drawdown limit is exceeded"""
        if self.initial_balance <= 0:
            return True
        
        drawdown_pct = ((self.initial_balance - current_balance) / self.initial_balance) * 100
        return drawdown_pct < self.config.drawdown_limit
    
    def should_open_new_level(self, symbol: str, current_price: float) -> bool:
        """Check if we should open a new level for existing basket"""
        if symbol not in self.baskets:
            return False
        
        basket = self.baskets[symbol]
        
        # Check max trades limit
        if len(basket.levels) >= self.config.max_trades:
            return False
        
        # Get last entry price
        last_level = basket.levels[-1]
        last_price = last_level.entry_price
        
        # Calculate distance in pips
        pip_size = 0.01 if 'JPY' in symbol else 0.0001
        distance_pips = abs(current_price - last_price) / pip_size
        
        # Check if price moved against us by trade_distance
        if basket.direction == 'buy':
            # For buy, price should drop by trade_distance
            if current_price < last_price and distance_pips >= self.config.trade_distance:
                return True
        else:
            # For sell, price should rise by trade_distance
            if current_price > last_price and distance_pips >= self.config.trade_distance:
                return True
        
        return False
    
    def open_trade(self, symbol: str, direction: str, lot_size: float, 
                   level: int = 1) -> Optional[int]:
        """Open a trade and return ticket number"""
        # Get symbol info
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            print(f"   ❌ Symbol {symbol} not found")
            return None
        
        # Check spread
        if not self.check_spread(symbol):
            print(f"   ❌ Spread too high for {symbol}")
            return None
        
        # Get filling mode
        filling_mode = symbol_info.filling_mode
        if filling_mode & mt5.SYMBOL_FILLING_FOK:
            filling_type = mt5.ORDER_FILLING_FOK
        elif filling_mode & mt5.SYMBOL_FILLING_IOC:
            filling_type = mt5.ORDER_FILLING_IOC
        else:
            filling_type = mt5.ORDER_FILLING_RETURN
        
        # Get current price
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return None
        
        order_type = mt5.ORDER_TYPE_BUY if direction == 'buy' else mt5.ORDER_TYPE_SELL
        price = tick.ask if direction == 'buy' else tick.bid
        
        # Prepare request (no SL/TP initially - will be managed by basket)
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot_size,
            "type": order_type,
            "price": price,
            "deviation": self.config.max_slippage,
            "magic": self.magic_number + level,
            "comment": f"ML_L{level}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling_type,
        }
        
        result = mt5.order_send(request)
        
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"   ❌ Order failed: {result.comment}")
            return None
        
        return result.order
    
    def analyze_and_trade(self, symbol: str, df: pd.DataFrame, 
                          account_balance: float) -> Optional[Dict]:
        """
        Main analysis and trading logic
        
        Returns:
            Dict with action taken or None
        """
        if self.initial_balance == 0:
            self.initialize(account_balance)
        
        # Check drawdown
        if not self.check_drawdown(account_balance):
            print(f"   ⚠️ Drawdown limit reached - no new trades")
            return {'action': 'drawdown_limit'}
        
        current_price = df.iloc[-1]['close']
        
        # Check if we have an existing basket for this symbol
        if symbol in self.baskets:
            basket = self.baskets[symbol]
            
            # Check if we should add a new level
            if self.should_open_new_level(symbol, current_price):
                level = len(basket.levels) + 1
                base_lot = self.get_base_lot_size(account_balance)
                lot_size = self.get_level_lot_size(base_lot, level)
                
                print(f"   📊 Opening Level {level} ({lot_size} lots)")
                
                ticket = self.open_trade(symbol, basket.direction, lot_size, level)
                
                if ticket:
                    trade_level = TradeLevel(
                        ticket=ticket,
                        entry_price=current_price,
                        lot_size=lot_size,
                        level=level,
                        direction=basket.direction,
                        entry_time=datetime.now()
                    )
                    basket.add_level(trade_level)
                    
                    # Update all TPs to common TP
                    self._update_basket_tp(basket)
                    
                    print(f"   ✅ Level {level} opened at {current_price:.5f}")
                    print(f"   📈 New average: {basket.average_price:.5f}")
                    print(f"   🎯 Common TP: {basket.common_tp:.5f}")
                    
                    return {
                        'action': 'add_level',
                        'level': level,
                        'ticket': ticket,
                        'average_price': basket.average_price,
                        'common_tp': basket.common_tp
                    }
            
            # Check if basket should be closed (TP hit)
            if self._check_basket_tp(basket, current_price):
                return self._close_basket(basket)
            
            return {'action': 'monitoring', 'levels': len(basket.levels)}
        
        # No existing basket - check for new entry signal
        signal = self.entry_strategy.get_entry_signal(df)
        
        if signal:
            base_lot = self.get_base_lot_size(account_balance)
            
            print(f"   🎯 Entry signal: {signal.upper()}")
            print(f"   💼 Opening Level 1 ({base_lot} lots)")
            
            ticket = self.open_trade(symbol, signal, base_lot, level=1)
            
            if ticket:
                # Create new basket
                basket = TradeBasket(symbol=symbol, direction=signal)
                trade_level = TradeLevel(
                    ticket=ticket,
                    entry_price=current_price,
                    lot_size=base_lot,
                    level=1,
                    direction=signal,
                    entry_time=datetime.now()
                )
                basket.add_level(trade_level)
                self.baskets[symbol] = basket
                
                # Set initial TP
                self._update_basket_tp(basket)
                
                print(f"   ✅ Level 1 opened at {current_price:.5f}")
                print(f"   🎯 TP: {basket.common_tp:.5f}")
                
                return {
                    'action': 'new_basket',
                    'direction': signal,
                    'ticket': ticket,
                    'entry_price': current_price,
                    'tp': basket.common_tp
                }
        
        return None
    
    def _update_basket_tp(self, basket: TradeBasket):
        """Update TP for all trades in basket to common TP"""
        for level in basket.levels:
            try:
                # Get position info
                position = mt5.positions_get(ticket=level.ticket)
                if position:
                    modify_request = {
                        "action": mt5.TRADE_ACTION_SLTP,
                        "symbol": basket.symbol,
                        "position": level.ticket,
                        "sl": 0.0,  # No SL
                        "tp": basket.common_tp,
                    }
                    mt5.order_send(modify_request)
            except Exception as e:
                pass  # Position may already be closed
    
    def _check_basket_tp(self, basket: TradeBasket, current_price: float) -> bool:
        """Check if basket TP is hit"""
        if basket.direction == 'buy':
            return current_price >= basket.common_tp
        else:
            return current_price <= basket.common_tp
    
    def _close_basket(self, basket: TradeBasket) -> Dict:
        """Close all trades in basket"""
        closed_tickets = []
        total_profit = 0.0
        
        for level in basket.levels:
            try:
                # Get position
                positions = mt5.positions_get(ticket=level.ticket)
                if positions:
                    position = positions[0]
                    
                    # Close position
                    close_type = mt5.ORDER_TYPE_SELL if basket.direction == 'buy' else mt5.ORDER_TYPE_BUY
                    tick = mt5.symbol_info_tick(basket.symbol)
                    price = tick.bid if basket.direction == 'buy' else tick.ask
                    
                    request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": basket.symbol,
                        "volume": position.volume,
                        "type": close_type,
                        "position": level.ticket,
                        "price": price,
                        "deviation": 20,
                        "magic": self.magic_number,
                        "comment": "ML_Close",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    
                    result = mt5.order_send(request)
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        closed_tickets.append(level.ticket)
                        total_profit += position.profit
            except Exception as e:
                pass
        
        # Remove basket
        del self.baskets[basket.symbol]
        
        print(f"   ✅ Basket closed - {len(closed_tickets)} trades")
        print(f"   💰 Total profit: ${total_profit:.2f}")
        
        return {
            'action': 'basket_closed',
            'trades_closed': len(closed_tickets),
            'total_profit': total_profit
        }
    
    def get_basket_status(self, symbol: str) -> Optional[Dict]:
        """Get status of basket for a symbol"""
        if symbol not in self.baskets:
            return None
        
        basket = self.baskets[symbol]
        
        # Calculate current P&L
        total_pnl = 0.0
        for level in basket.levels:
            positions = mt5.positions_get(ticket=level.ticket)
            if positions:
                total_pnl += positions[0].profit
        
        return {
            'symbol': symbol,
            'direction': basket.direction,
            'levels': len(basket.levels),
            'total_lots': basket.total_lots,
            'average_price': basket.average_price,
            'common_tp': basket.common_tp,
            'current_pnl': total_pnl
        }


# Risk level presets
RISK_PRESETS = {
    RiskLevel.LOW: MultiLevelConfig(
        risk_level=RiskLevel.LOW,
        drawdown_limit=30.0,
        trade_distance=40,
        take_profit=10,
        max_trades=5,
        second_level_multiplier=1.0,
        multiplier_after_second=1.5
    ),
    RiskLevel.MEDIUM: MultiLevelConfig(
        risk_level=RiskLevel.MEDIUM,
        drawdown_limit=50.0,
        trade_distance=30,
        take_profit=12,
        max_trades=8,
        second_level_multiplier=1.0,
        multiplier_after_second=2.0
    ),
    RiskLevel.HIGH: MultiLevelConfig(
        risk_level=RiskLevel.HIGH,
        drawdown_limit=70.0,
        trade_distance=25,
        take_profit=15,
        max_trades=10,
        second_level_multiplier=1.5,
        multiplier_after_second=2.0
    ),
    RiskLevel.AGGRESSIVE: MultiLevelConfig(
        risk_level=RiskLevel.AGGRESSIVE,
        drawdown_limit=100.0,
        trade_distance=20,
        take_profit=20,
        max_trades=15,
        second_level_multiplier=2.0,
        multiplier_after_second=2.5
    )
}
