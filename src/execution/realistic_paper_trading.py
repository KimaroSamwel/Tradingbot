"""
REALISTIC PAPER TRADING SIMULATOR
Simulates realistic trading conditions including spread, slippage, and rejections

Features:
- Dynamic spread simulation
- Realistic slippage modeling
- Order fill probability
- Execution delays
- Commission calculation
"""

import random
import time
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class OrderStatus(Enum):
    """Order execution status"""
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    PARTIAL_FILL = "PARTIAL_FILL"
    SLIPPED = "SLIPPED"


@dataclass
class ExecutionResult:
    """Result of order execution"""
    status: OrderStatus
    requested_price: float
    filled_price: Optional[float]
    lot_size_requested: float
    lot_size_filled: float
    spread_paid: float
    slippage: float
    commission: float
    execution_time_ms: int
    rejection_reason: Optional[str] = None


class RealisticPaperTrading:
    """
    Realistic paper trading simulator
    CRITICAL: Simulates real market conditions to match live trading
    """
    
    def __init__(self):
        """Initialize realistic simulator with market-based parameters"""
        
        # Spread simulation (pips)
        self.spread_ranges = {
            'EURUSD': {'min': 0.5, 'max': 2.5, 'avg': 1.2, 'news_multiplier': 3.0},
            'GBPUSD': {'min': 0.8, 'max': 3.5, 'avg': 1.8, 'news_multiplier': 4.0},
            'USDJPY': {'min': 0.5, 'max': 2.0, 'avg': 1.0, 'news_multiplier': 3.0},
            'AUDUSD': {'min': 0.6, 'max': 2.2, 'avg': 1.3, 'news_multiplier': 3.5},
            'XAUUSD': {'min': 0.15, 'max': 1.20, 'avg': 0.40, 'news_multiplier': 5.0},
            'XAGUSD': {'min': 0.02, 'max': 0.08, 'avg': 0.04, 'news_multiplier': 4.0},
        }
        
        # Slippage simulation (pips)
        # Normal distribution: mean=0, std varies by market condition
        self.slippage_std = {
            'normal': 0.3,        # Normal conditions
            'volatile': 0.8,      # High volatility
            'news': 1.5,          # News events
            'illiquid': 1.2       # Low liquidity periods
        }
        
        # Fill probability
        self.base_fill_probability = 0.95  # 95% base chance
        
        # Execution delay (milliseconds)
        self.execution_delay_range = (50, 300)  # 50-300ms
        
        # Commission (per lot per side)
        self.commission_per_lot = {
            'EURUSD': 3.50,
            'GBPUSD': 3.50,
            'USDJPY': 3.50,
            'AUDUSD': 3.50,
            'XAUUSD': 5.00,  # Higher for metals
            'XAGUSD': 5.00,
            'default': 3.50
        }
        
        # Market conditions
        self.is_news_event = False
        self.market_condition = 'normal'
        
    def set_market_conditions(self, condition: str = 'normal', 
                             is_news: bool = False):
        """
        Set current market conditions
        
        Args:
            condition: 'normal', 'volatile', 'illiquid'
            is_news: True if during news event
        """
        self.market_condition = condition
        self.is_news_event = is_news
    
    def execute_order(self, symbol: str, order_type: str,
                     requested_price: float, lot_size: float,
                     current_time: datetime) -> ExecutionResult:
        """
        Execute order with realistic simulation
        
        Args:
            symbol: Trading symbol
            order_type: 'BUY' or 'SELL'
            requested_price: Price at which order was placed
            lot_size: Requested lot size
            current_time: Current time
            
        Returns:
            ExecutionResult with all details
        """
        # 1. Simulate execution delay
        delay_ms = random.randint(*self.execution_delay_range)
        time.sleep(delay_ms / 1000.0)  # Convert to seconds
        
        # 2. Check fill probability
        fill_prob = self._calculate_fill_probability(symbol, lot_size)
        
        if random.random() > fill_prob:
            # Order rejected
            return ExecutionResult(
                status=OrderStatus.REJECTED,
                requested_price=requested_price,
                filled_price=None,
                lot_size_requested=lot_size,
                lot_size_filled=0.0,
                spread_paid=0.0,
                slippage=0.0,
                commission=0.0,
                execution_time_ms=delay_ms,
                rejection_reason=self._get_rejection_reason()
            )
        
        # 3. Calculate spread
        spread = self._simulate_spread(symbol)
        
        # 4. Calculate slippage
        slippage = self._simulate_slippage(symbol)
        
        # 5. Calculate filled price
        if order_type == 'BUY':
            # Buy at ask (higher price)
            filled_price = requested_price + spread + slippage
        else:  # SELL
            # Sell at bid (lower price)
            filled_price = requested_price - spread + slippage  # Slippage can be positive or negative
        
        # 6. Check for partial fill
        filled_lot_size = lot_size
        status = OrderStatus.FILLED
        
        if lot_size > 10.0 and random.random() < 0.1:  # 10% chance for large orders
            filled_lot_size = lot_size * random.uniform(0.7, 0.95)
            status = OrderStatus.PARTIAL_FILL
        
        # 7. Calculate commission
        commission = self._calculate_commission(symbol, filled_lot_size)
        
        # 8. Mark if slippage was significant
        if abs(slippage) > 1.0:  # More than 1 pip slippage
            status = OrderStatus.SLIPPED
        
        return ExecutionResult(
            status=status,
            requested_price=requested_price,
            filled_price=filled_price,
            lot_size_requested=lot_size,
            lot_size_filled=filled_lot_size,
            spread_paid=spread,
            slippage=slippage,
            commission=commission,
            execution_time_ms=delay_ms
        )
    
    def _simulate_spread(self, symbol: str) -> float:
        """
        Simulate realistic spread
        
        Returns:
            Spread in pips (for symbol's pip size)
        """
        spread_config = self.spread_ranges.get(symbol, self.spread_ranges['EURUSD'])
        
        # Base spread (normal distribution within min-max)
        spread = random.uniform(spread_config['min'], spread_config['max'])
        
        # Adjust for market conditions
        if self.is_news_event:
            spread *= spread_config['news_multiplier']
        elif self.market_condition == 'volatile':
            spread *= 1.5
        elif self.market_condition == 'illiquid':
            spread *= 2.0
        
        # Convert to price units
        if 'XAU' in symbol or 'XAG' in symbol:
            # Metals: pip = 0.01
            spread_price = spread * 0.01
        elif 'JPY' in symbol:
            # JPY: pip = 0.01
            spread_price = spread * 0.01
        else:
            # Forex: pip = 0.0001
            spread_price = spread * 0.0001
        
        return spread_price
    
    def _simulate_slippage(self, symbol: str) -> float:
        """
        Simulate realistic slippage (positive or negative)
        
        Returns:
            Slippage in price units (can be positive or negative)
        """
        # Determine slippage standard deviation based on conditions
        if self.is_news_event:
            std = self.slippage_std['news']
        elif self.market_condition == 'volatile':
            std = self.slippage_std['volatile']
        elif self.market_condition == 'illiquid':
            std = self.slippage_std['illiquid']
        else:
            std = self.slippage_std['normal']
        
        # Slippage is normally distributed around 0
        slippage_pips = random.gauss(0, std)
        
        # Convert to price units
        if 'XAU' in symbol or 'XAG' in symbol:
            slippage_price = slippage_pips * 0.01
        elif 'JPY' in symbol:
            slippage_price = slippage_pips * 0.01
        else:
            slippage_price = slippage_pips * 0.0001
        
        return slippage_price
    
    def _calculate_fill_probability(self, symbol: str, lot_size: float) -> float:
        """
        Calculate probability of order being filled
        
        Large orders have lower fill probability
        """
        base_prob = self.base_fill_probability
        
        # Reduce probability for large orders
        if lot_size > 10.0:
            base_prob *= 0.85
        elif lot_size > 5.0:
            base_prob *= 0.95
        
        # Reduce during news
        if self.is_news_event:
            base_prob *= 0.80
        
        # Reduce during illiquid periods
        if self.market_condition == 'illiquid':
            base_prob *= 0.85
        
        return base_prob
    
    def _calculate_commission(self, symbol: str, lot_size: float) -> float:
        """
        Calculate commission for trade
        
        Args:
            symbol: Trading symbol
            lot_size: Lot size traded
            
        Returns:
            Commission amount in USD
        """
        commission_rate = self.commission_per_lot.get(
            symbol, 
            self.commission_per_lot['default']
        )
        
        return commission_rate * lot_size
    
    def _get_rejection_reason(self) -> str:
        """Get random rejection reason"""
        reasons = [
            "Insufficient liquidity",
            "Price moved away",
            "Market closed",
            "Order timeout",
            "Maximum position size exceeded",
            "Margin requirement not met"
        ]
        return random.choice(reasons)
    
    def calculate_realistic_pnl(self, entry_result: ExecutionResult,
                               exit_result: ExecutionResult,
                               direction: str,
                               symbol: str) -> Dict:
        """
        Calculate realistic P&L including all costs
        
        Args:
            entry_result: Entry execution result
            exit_result: Exit execution result
            direction: 'BUY' or 'SELL'
            symbol: Trading symbol
            
        Returns:
            Dictionary with P&L breakdown
        """
        if not entry_result.filled_price or not exit_result.filled_price:
            return {
                'gross_pnl': 0,
                'net_pnl': 0,
                'spread_cost': 0,
                'slippage_cost': 0,
                'commission_cost': 0,
                'total_cost': 0
            }
        
        # Calculate gross P&L
        lot_size = min(entry_result.lot_size_filled, exit_result.lot_size_filled)
        
        if direction == 'BUY':
            price_diff = exit_result.filled_price - entry_result.filled_price
        else:  # SELL
            price_diff = entry_result.filled_price - exit_result.filled_price
        
        # Calculate pip value
        if 'XAU' in symbol:
            pip_value_per_lot = 1.0  # $1 per pip per 0.01 lot
        elif 'XAG' in symbol:
            pip_value_per_lot = 0.50
        elif 'JPY' in symbol:
            pip_value_per_lot = 0.10
        else:
            pip_value_per_lot = 0.10
        
        # Convert price difference to pips
        if 'XAU' in symbol or 'XAG' in symbol or 'JPY' in symbol:
            pips = price_diff / 0.01
        else:
            pips = price_diff / 0.0001
        
        gross_pnl = pips * pip_value_per_lot * lot_size
        
        # Calculate costs
        spread_cost = (entry_result.spread_paid + exit_result.spread_paid) * pip_value_per_lot * lot_size
        slippage_cost = (entry_result.slippage + exit_result.slippage) * pip_value_per_lot * lot_size
        commission_cost = entry_result.commission + exit_result.commission
        
        total_cost = spread_cost + abs(slippage_cost) + commission_cost
        net_pnl = gross_pnl - total_cost
        
        return {
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'spread_cost': spread_cost,
            'slippage_cost': slippage_cost,
            'commission_cost': commission_cost,
            'total_cost': total_cost,
            'pips': pips,
            'lot_size': lot_size
        }
    
    def get_execution_summary(self, result: ExecutionResult) -> str:
        """Get human-readable execution summary"""
        if result.status == OrderStatus.REJECTED:
            return f"❌ ORDER REJECTED: {result.rejection_reason}"
        
        status_emoji = {
            OrderStatus.FILLED: "✓",
            OrderStatus.PARTIAL_FILL: "⚠",
            OrderStatus.SLIPPED: "⚠"
        }
        
        emoji = status_emoji.get(result.status, "•")
        
        summary = f"{emoji} {result.status.value}\n"
        summary += f"  Requested: {result.requested_price:.5f} | Filled: {result.filled_price:.5f}\n"
        summary += f"  Spread: {result.spread_paid*10000:.1f} pips | "
        summary += f"Slippage: {result.slippage*10000:.1f} pips | "
        summary += f"Commission: ${result.commission:.2f}\n"
        summary += f"  Lot: {result.lot_size_filled:.2f}/{result.lot_size_requested:.2f} | "
        summary += f"Time: {result.execution_time_ms}ms"
        
        return summary
