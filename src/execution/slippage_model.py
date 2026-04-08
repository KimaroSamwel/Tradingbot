"""
SLIPPAGE MODELING
Realistic execution cost modeling for backtesting and live trading
Accounts for spread, commission, and market impact
"""

import MetaTrader5 as mt5
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum


class OrderType(Enum):
    """Order types"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


@dataclass
class SlippageConfig:
    """Slippage modeling configuration"""
    # Spread modeling
    use_dynamic_spread: bool = True
    fixed_spread_pips: float = 1.0
    spread_multiplier: float = 1.2  # Multiply actual spread by this
    
    # Commission
    commission_per_lot: float = 7.0  # $7 per round-turn lot
    
    # Market impact (for larger orders)
    enable_market_impact: bool = True
    impact_coefficient: float = 0.1  # Slippage per $100k traded
    
    # Execution delay
    execution_delay_ms: int = 50  # 50ms execution delay
    
    # Rejection rate (for limit orders)
    limit_order_fill_rate: float = 0.85  # 85% fill rate


class SlippageModel:
    """
    Models realistic execution costs
    
    Components:
    1. **Spread** - Bid-ask spread cost (major cost in forex)
    2. **Commission** - Broker commission per trade
    3. **Market Impact** - Price movement from large orders
    4. **Execution Delay** - Price movement during execution
    5. **Partial Fills** - Orders that don't fully execute
    
    Typical Costs for EURUSD (per lot):
    - Spread: 0.5-2 pips ($5-$20)
    - Commission: $3.50-$7 per side ($7-$14 round-turn)
    - Slippage: 0-1 pip on market orders
    - Total: ~$12-$35 per round-turn lot
    """
    
    def __init__(self, config: SlippageConfig = None):
        """
        Initialize slippage model
        
        Args:
            config: Slippage configuration
        """
        self.config = config or SlippageConfig()
    
    def calculate_execution_price(self, symbol: str, order_type: OrderType,
                                  direction: str, intended_price: float,
                                  volume: float) -> Dict:
        """
        Calculate realistic execution price with slippage
        
        Args:
            symbol: Trading symbol
            order_type: Market, limit, or stop order
            direction: 'BUY' or 'SELL'
            intended_price: Intended execution price
            volume: Order size in lots
        
        Returns:
            Execution details with slippage
        """
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return {
                'executed': False,
                'reason': 'Symbol not found'
            }
        
        # 1. Calculate spread cost
        spread_cost = self._calculate_spread_cost(symbol, symbol_info, direction)
        
        # 2. Calculate commission
        commission = self._calculate_commission(volume)
        
        # 3. Calculate market impact (for large orders)
        market_impact = self._calculate_market_impact(symbol_info, volume) if self.config.enable_market_impact else 0
        
        # 4. Calculate execution delay slippage
        delay_slippage = self._calculate_delay_slippage(symbol_info, order_type)
        
        # 5. Total slippage
        total_slippage_pips = spread_cost + market_impact + delay_slippage
        
        # Convert pips to price
        point_value = symbol_info.point
        if 'JPY' in symbol:
            pip_value = point_value * 100
        else:
            pip_value = point_value * 10
        
        slippage_price = total_slippage_pips * pip_value
        
        # 6. Final execution price
        if direction == 'BUY':
            execution_price = intended_price + slippage_price
        else:
            execution_price = intended_price - slippage_price
        
        # 7. Check for rejection (limit orders)
        if order_type == OrderType.LIMIT:
            import random
            if random.random() > self.config.limit_order_fill_rate:
                return {
                    'executed': False,
                    'reason': 'Limit order not filled'
                }
        
        # Calculate total cost in account currency
        lot_value = 100000 * volume  # Standard lot = 100k units
        spread_cost_usd = (spread_cost * pip_value / point_value) * lot_value / 100000
        total_cost_usd = spread_cost_usd + commission
        
        return {
            'executed': True,
            'execution_price': execution_price,
            'intended_price': intended_price,
            'slippage_pips': total_slippage_pips,
            'slippage_price': slippage_price,
            'spread_cost_pips': spread_cost,
            'market_impact_pips': market_impact,
            'delay_slippage_pips': delay_slippage,
            'commission_usd': commission,
            'total_cost_usd': total_cost_usd,
            'cost_per_lot_usd': total_cost_usd / volume if volume > 0 else 0
        }
    
    def _calculate_spread_cost(self, symbol: str, symbol_info, direction: str) -> float:
        """Calculate spread cost in pips"""
        if self.config.use_dynamic_spread:
            # Get current spread from MT5
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                spread_points = tick.ask - tick.bid
                point_value = symbol_info.point
                
                if 'JPY' in symbol:
                    spread_pips = (spread_points / point_value) / 100
                else:
                    spread_pips = (spread_points / point_value) / 10
                
                # Apply multiplier for volatility
                spread_pips *= self.config.spread_multiplier
                return spread_pips
        
        # Use fixed spread
        return self.config.fixed_spread_pips
    
    def _calculate_commission(self, volume: float) -> float:
        """Calculate commission in USD"""
        return self.config.commission_per_lot * volume
    
    def _calculate_market_impact(self, symbol_info, volume: float) -> float:
        """
        Calculate market impact slippage
        Larger orders move the market
        
        Formula: impact = volume * 100k * impact_coefficient / 100k
        """
        notional_value = volume * 100000  # Convert lots to units
        impact_pips = (notional_value / 100000) * self.config.impact_coefficient
        
        return impact_pips
    
    def _calculate_delay_slippage(self, symbol_info, order_type: OrderType) -> float:
        """
        Calculate slippage from execution delay
        Market orders have more delay slippage than limit orders
        """
        if order_type == OrderType.MARKET:
            # Market orders: 0-0.5 pips typical slippage
            import random
            return random.uniform(0, 0.5)
        else:
            # Limit/stop orders: minimal slippage
            return 0.0
    
    def estimate_round_trip_cost(self, symbol: str, volume: float) -> Dict:
        """
        Estimate total round-trip cost (entry + exit)
        
        Args:
            symbol: Trading symbol
            volume: Lot size
        
        Returns:
            Cost breakdown
        """
        symbol_info = mt5.symbol_info(symbol)
        if symbol_info is None:
            return {'error': 'Symbol not found'}
        
        # Entry cost
        entry_result = self.calculate_execution_price(
            symbol, OrderType.MARKET, 'BUY', 1.0, volume
        )
        
        # Exit cost (same as entry for estimation)
        exit_cost = entry_result['total_cost_usd']
        
        total_round_trip = entry_result['total_cost_usd'] + exit_cost
        
        # Calculate as percentage of position size
        position_value = volume * 100000
        cost_percentage = (total_round_trip / position_value) * 100
        
        return {
            'entry_cost_usd': entry_result['total_cost_usd'],
            'exit_cost_usd': exit_cost,
            'total_round_trip_usd': total_round_trip,
            'cost_percentage': cost_percentage,
            'breakeven_pips': entry_result['slippage_pips'] * 2,  # Must move this much to break even
            'cost_per_lot': total_round_trip / volume if volume > 0 else 0
        }
    
    def print_cost_analysis(self, symbol: str, volume: float = 1.0):
        """Print detailed cost analysis"""
        costs = self.estimate_round_trip_cost(symbol, volume)
        
        if 'error' in costs:
            print(f"❌ {costs['error']}")
            return
        
        print(f"\n💰 Cost Analysis for {symbol} ({volume} lots)")
        print("="*60)
        print(f"Entry Cost:         ${costs['entry_cost_usd']:.2f}")
        print(f"Exit Cost:          ${costs['exit_cost_usd']:.2f}")
        print(f"Total Round-Trip:   ${costs['total_round_trip_usd']:.2f}")
        print(f"Cost per Lot:       ${costs['cost_per_lot']:.2f}")
        print(f"Breakeven Move:     {costs['breakeven_pips']:.1f} pips")
        print(f"Cost as % of Size:  {costs['cost_percentage']:.3f}%")
        print("="*60)


class ExecutionSimulator:
    """
    Simulates realistic order execution for backtesting
    """
    
    def __init__(self, slippage_model: SlippageModel):
        """
        Initialize execution simulator
        
        Args:
            slippage_model: Slippage model instance
        """
        self.slippage_model = slippage_model
        self.execution_history = []
    
    def simulate_execution(self, symbol: str, order_type: OrderType,
                          direction: str, price: float, volume: float) -> Dict:
        """
        Simulate order execution with realistic costs
        
        Args:
            symbol: Trading symbol
            order_type: Order type
            direction: BUY or SELL
            price: Intended price
            volume: Lot size
        
        Returns:
            Execution result
        """
        result = self.slippage_model.calculate_execution_price(
            symbol, order_type, direction, price, volume
        )
        
        if result['executed']:
            self.execution_history.append(result)
        
        return result
    
    def get_total_costs(self) -> float:
        """Get total execution costs"""
        return sum(r['total_cost_usd'] for r in self.execution_history if r['executed'])
    
    def get_average_slippage(self) -> float:
        """Get average slippage in pips"""
        slippages = [r['slippage_pips'] for r in self.execution_history if r['executed']]
        return sum(slippages) / len(slippages) if slippages else 0
