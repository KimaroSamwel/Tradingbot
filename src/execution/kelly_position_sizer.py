"""
KELLY CRITERION POSITION SIZER
Advanced position sizing using Kelly Criterion with multiple adjustments

Features:
- Kelly Criterion calculation from win rate and R:R
- Conservative Kelly (fractional Kelly)
- Volatility adjustments
- Correlation adjustments
- Account size adjustments
- Strategy-specific sizing
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class PositionSizeResult:
    """Position sizing result"""
    risk_percent: float  # Final risk percentage
    lot_size: float  # Calculated lot size
    position_value: float  # Position value in account currency
    kelly_fraction: float  # Base Kelly fraction
    adjustments: Dict  # All adjustment factors applied


class KellyPositionSizer:
    """
    Advanced position sizing using Kelly Criterion
    """
    
    def __init__(self, account_balance: float,
                 use_conservative_kelly: bool = True,
                 kelly_fraction: float = 0.125):
        """
        Initialize Kelly position sizer with REALISTIC limits
        
        Args:
            account_balance: Current account balance
            use_conservative_kelly: Use fractional Kelly (default True)
            kelly_fraction: Fraction of Kelly to use (default 0.125 = 1/8 Kelly for retail)
        """
        self.account_balance = account_balance
        self.use_conservative_kelly = use_conservative_kelly
        self.kelly_fraction = kelly_fraction  # 1/8 Kelly is ultra-conservative for retail
        
        # CRITICAL: Store callback to get live equity for real-time position sizing
        self.get_live_equity_callback = None
        
        # Strategy performance tracking
        self.strategy_performance = {}
        
        # CORRECTED: Realistic risk limits for retail trading
        self.min_risk_pct = 0.002  # 0.2% minimum
        self.max_risk_pct = 0.020  # 2% maximum (absolute hard limit)
        self.default_risk_pct = 0.005  # 0.5% default (safe for most accounts)
        
        # Adjustment factors
        self.volatility_adjustment_enabled = True
        self.correlation_adjustment_enabled = True
        self.account_size_adjustment_enabled = True
        
    def calculate_kelly_fraction(self, win_rate: float,
                                 win_loss_ratio: float) -> float:
        """
        Calculate Kelly Criterion fraction
        
        Formula: f* = (bp - q) / b
        where:
        - b = win/loss ratio (average win / average loss)
        - p = probability of winning
        - q = probability of losing (1 - p)
        
        Args:
            win_rate: Win rate percentage (0-100)
            win_loss_ratio: Average win / average loss ratio
            
        Returns:
            Kelly fraction (0-1)
        """
        if win_rate <= 0 or win_rate >= 100:
            return self.min_risk_pct
        
        if win_loss_ratio <= 0:
            return self.min_risk_pct
        
        # Convert win rate to probability
        p = win_rate / 100.0
        q = 1 - p
        b = win_loss_ratio
        
        # Kelly formula
        kelly = (b * p - q) / b
        
        # CRITICAL FIX: Kelly can be negative (losing strategy) or > 1 (over-leverage)
        # For retail trading, even full Kelly is too aggressive
        if kelly <= 0:
            return self.min_risk_pct  # Don't trade negative expectancy
        
        # Apply fractional Kelly (1/8 Kelly for ultra-conservative retail trading)
        # This prevents account blow-ups from variance
        if self.use_conservative_kelly:
            kelly *= self.kelly_fraction  # Reduce to 1/8 or 1/4 of full Kelly
        
        # HARD LIMITS: Even fractional Kelly can be too high
        # Maximum 2% risk per trade for retail accounts
        kelly = max(self.min_risk_pct, min(kelly, self.max_risk_pct))
        
        return kelly
    
    def calculate_position_size(self, symbol: str,
                               strategy: str,
                               stop_loss_pips: float,
                               entry_price: float,
                               market_volatility: float = 0.5,
                               open_positions: Optional[Dict] = None) -> PositionSizeResult:
        """
        Calculate optimal position size with all adjustments
        
        Args:
            symbol: Trading symbol
            strategy: Strategy name
            stop_loss_pips: Stop loss in pips
            entry_price: Entry price
            market_volatility: Current market volatility (0-1)
            open_positions: Currently open positions for correlation calc
            
        Returns:
            PositionSizeResult with all calculations
        """
        # CRITICAL FIX #19: Use live equity, not stale account_balance
        initial_balance = self.account_balance
        if self.get_live_equity_callback is not None:
            current_equity = self.get_live_equity_callback()
            if current_equity > 0:
                self.account_balance = current_equity
        
        # FIX #36: Log position sizing inputs for transparency
        import logging
        logger = logging.getLogger('SNIPER_PRO_2024')
        logger.debug(
            f"[POSITION_SIZING] {symbol} | Strategy: {strategy} | "
            f"Account Balance: ${self.account_balance:.2f} (was ${initial_balance:.2f}) | "
            f"Stop Loss: {stop_loss_pips:.2f} pips | Entry: {entry_price:.5f} | "
            f"Volatility: {market_volatility:.2f}"
        )
        
        # Get strategy performance
        # FIX: Default 1:1 ratio is more conservative than 2:1
        strategy_perf = self.strategy_performance.get(strategy, {
            'win_rate': 50,
            'avg_win': 75,
            'avg_loss': 75,
            'trades': 0
        })
        
        win_rate = strategy_perf.get('win_rate', 50)
        avg_win = strategy_perf.get('avg_win', 75)
        avg_loss = strategy_perf.get('avg_loss', 75)
        win_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 1.0
        
        # 1. Calculate base Kelly fraction
        base_kelly = self.calculate_kelly_fraction(win_rate, win_loss_ratio)
        
        # 2. Apply volatility adjustment
        volatility_multiplier = self._calculate_volatility_adjustment(market_volatility)
        
        # 3. Apply correlation adjustment
        correlation_adjustment = self._calculate_correlation_adjustment(
            symbol, open_positions
        )
        
        # 4. Apply account size adjustment
        account_size_adjustment = self._calculate_account_size_adjustment()
        
        # 5. Apply instrument-specific adjustment
        instrument_adjustment = self._calculate_instrument_adjustment(symbol)
        
        # 6. Apply strategy confidence adjustment
        strategy_confidence = self._calculate_strategy_confidence(strategy_perf)
        
        # Combine all adjustments
        final_risk_pct = (
            base_kelly *
            volatility_multiplier *
            correlation_adjustment *
            account_size_adjustment *
            instrument_adjustment *
            strategy_confidence
        )
        
        # Apply hard limits
        final_risk_pct = max(self.min_risk_pct, min(final_risk_pct, self.max_risk_pct))
        
        # Calculate lot size
        lot_size = self._calculate_lot_size(
            symbol, final_risk_pct, stop_loss_pips, entry_price
        )
        
        # EMERGENCY FIX: Absolute max lot size cap for small accounts
        if self.account_balance < 500:
            emergency_max_lot = 0.02  # Hard cap for very small accounts
            if lot_size > emergency_max_lot:
                logger.warning(
                    f"[POSITION_SIZING] EMERGENCY CAP: {symbol} lot size {lot_size:.2f} "
                    f"reduced to {emergency_max_lot:.2f} for account ${self.account_balance:.2f}"
                )
                lot_size = emergency_max_lot
        elif self.account_balance < 1000:
            emergency_max_lot = 0.05
            if lot_size > emergency_max_lot:
                logger.warning(
                    f"[POSITION_SIZING] EMERGENCY CAP: {symbol} lot size {lot_size:.2f} "
                    f"reduced to {emergency_max_lot:.2f} for account ${self.account_balance:.2f}"
                )
                lot_size = emergency_max_lot
        
        # Calculate position value
        position_value = self.account_balance * final_risk_pct
        
        # FIX #36: Log final position sizing results
        logger.debug(
            f"[POSITION_SIZING] {symbol} RESULT | "
            f"Lot Size: {lot_size:.2f} | Risk %: {final_risk_pct*100:.2f}% | "
            f"Position Value: ${position_value:.2f} | "
            f"Adjustments: Kelly={base_kelly:.4f}, Vol={volatility_multiplier:.2f}, "
            f"Corr={correlation_adjustment:.2f}, AcctSize={account_size_adjustment:.2f}, "
            f"Instrument={instrument_adjustment:.2f}, Strategy={strategy_confidence:.2f}"
        )
        
        return PositionSizeResult(
            risk_percent=final_risk_pct * 100,  # Convert to percentage
            lot_size=lot_size,
            position_value=position_value,
            kelly_fraction=base_kelly,
            adjustments={
                'base_kelly': base_kelly,
                'volatility_multiplier': volatility_multiplier,
                'correlation_adjustment': correlation_adjustment,
                'account_size_adjustment': account_size_adjustment,
                'instrument_adjustment': instrument_adjustment,
                'strategy_confidence': strategy_confidence,
                'final_risk_pct': final_risk_pct * 100
            }
        )
    
    def _calculate_volatility_adjustment(self, volatility: float) -> float:
        """
        Adjust position size based on market volatility
        
        Args:
            volatility: Volatility score (0-1)
            
        Returns:
            Multiplier (0.5 to 1.5)
        """
        if not self.volatility_adjustment_enabled:
            return 1.0
        
        # High volatility = reduce size
        # Low volatility = increase size (slightly)
        
        if volatility > 0.8:  # Extreme high volatility
            return 0.5
        elif volatility > 0.6:  # High volatility
            return 0.7
        elif volatility < 0.3:  # Low volatility
            return 1.2
        elif volatility < 0.2:  # Very low volatility
            return 1.3
        else:  # Normal volatility
            return 1.0
    
    def _calculate_correlation_adjustment(self, symbol: str,
                                         open_positions: Optional[Dict]) -> float:
        """
        Adjust position size based on correlation with open positions
        
        Args:
            symbol: New position symbol
            open_positions: Dictionary of open positions
            
        Returns:
            Multiplier (0.5 to 1.0)
        """
        if not self.correlation_adjustment_enabled or not open_positions:
            return 1.0
        
        # Correlation matrix (simplified)
        correlations = {
            ('EURUSD', 'GBPUSD'): 0.75,
            ('EURUSD', 'USDCHF'): -0.85,
            ('GBPUSD', 'EURGBP'): -0.70,
            ('XAUUSD', 'DXY'): -0.80,
            ('XAUUSD', 'EURUSD'): 0.60,
            ('USDJPY', 'AUDUSD'): -0.45,
        }
        
        total_correlation = 0
        position_count = 0
        
        for open_symbol, position_data in open_positions.items():
            # Get correlation
            corr = correlations.get((symbol, open_symbol), 
                   correlations.get((open_symbol, symbol), 0))
            
            # Weight by position size
            position_weight = position_data.get('size', 1)
            total_correlation += abs(corr) * position_weight
            position_count += position_weight
        
        if position_count == 0:
            return 1.0
        
        avg_correlation = total_correlation / position_count
        
        # High correlation = reduce size significantly
        if avg_correlation > 0.7:
            return 0.5
        elif avg_correlation > 0.5:
            return 0.7
        elif avg_correlation > 0.3:
            return 0.85
        else:
            return 1.0
    
    def _calculate_account_size_adjustment(self) -> float:
        """
        Adjust position size based on account size
        Smaller accounts need smaller position sizes (risk of ruin)
        
        Returns:
            Multiplier (0.5 to 1.0)
        """
        if not self.account_size_adjustment_enabled:
            return 1.0
        
        # Account size tiers
        if self.account_balance < 1000:  # Very small account
            return 0.5
        elif self.account_balance < 5000:  # Small account
            return 0.7
        elif self.account_balance < 10000:  # Medium account
            return 0.85
        else:  # Large account
            return 1.0
    
    def _calculate_instrument_adjustment(self, symbol: str) -> float:
        """
        Adjust position size for instrument-specific characteristics
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Multiplier (0.5 to 1.0)
        """
        # Metals have higher volatility - reduce size
        if 'XAU' in symbol or 'XAG' in symbol:
            return 0.7
        
        # Exotic pairs have wider spreads - reduce size
        if any(curr in symbol for curr in ['ZAR', 'TRY', 'MXN', 'BRL']):
            return 0.6
        
        # Major pairs - full size
        if any(pair in symbol for pair in ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF']):
            return 1.0
        
        # Minor pairs - slight reduction
        return 0.9
    
    def _calculate_strategy_confidence(self, strategy_perf: Dict) -> float:
        """
        Adjust based on strategy performance confidence
        
        Args:
            strategy_perf: Strategy performance metrics
            
        Returns:
            Multiplier (0.5 to 1.2)
        """
        trades = strategy_perf.get('trades', 0)
        win_rate = strategy_perf.get('win_rate', 50)
        
        # Not enough data - be conservative
        if trades < 10:
            return 0.7
        elif trades < 30:
            return 0.85
        
        # Good performance - increase slightly
        if win_rate > 60 and trades >= 30:
            return 1.2
        elif win_rate > 55:
            return 1.1
        elif win_rate > 50:
            return 1.0
        elif win_rate > 40:
            return 0.9
        else:  # Poor performance
            return 0.6
    
    def _calculate_lot_size(self, symbol: str,
                           risk_pct: float,
                           stop_loss_pips: float,
                           entry_price: float) -> float:
        """
        Calculate actual lot size from risk percentage
        CORRECTED: Proper pip value calculation for Gold and Forex
        
        Args:
            symbol: Trading symbol
            risk_pct: Risk percentage (0-1)
            stop_loss_pips: Stop loss in pips
            entry_price: Entry price
            
        Returns:
            Lot size (in mini lots, 0.01 = 1 mini lot)
        """
        # Risk amount in account currency
        risk_amount = self.account_balance * risk_pct
        
        # Get instrument specifications
        instrument_config = self._get_instrument_config(symbol, entry_price)
        pip_value_per_lot = instrument_config['pip_value_per_lot']
        
        # CORRECTED CALCULATION:
        # risk_amount = lot_size * stop_loss_pips * pip_value_per_lot
        # lot_size = risk_amount / (stop_loss_pips * pip_value_per_lot)
        
        if stop_loss_pips <= 0:
            return instrument_config['min_lot']
        
        lot_size = risk_amount / (stop_loss_pips * pip_value_per_lot)
        
        # Round to allowed lot size
        min_lot = instrument_config.get('min_lot', 0.01)
        max_lot = instrument_config.get('max_lot', 100.0)
        lot_step = instrument_config.get('lot_step', 0.01)
        
        lot_size = max(min_lot, min(max_lot, round(lot_size / lot_step) * lot_step))
        
        return lot_size
    
    def _get_instrument_config(self, symbol: str, entry_price: float = 0) -> Dict:
        """
        Get instrument-specific configuration with CORRECTED pip values
        
        CRITICAL FIX: Gold pip value calculation was wrong by factor of 100!
        For Gold (XAUUSD):
        - 1 standard lot = 100 oz
        - 1 mini lot (0.01) = 1 oz  
        - 1 pip (0.01 move) = $1 per mini lot at current prices (~$2600)
        - NOT $0.10 as previously calculated!
        
        For Forex:
        - 1 mini lot (0.01) = 1,000 units
        - 1 pip (0.0001) = $0.10 per mini lot for XXX/USD pairs
        """
        
        # CRITICAL FIX: All pip values must be PER STANDARD LOT (1.0 lot)
        # Formula: lot_size = risk_amount / (stop_loss_pips * pip_value_per_lot)
        # If pip_value is per micro lot (0.01), lot sizes will be 100x too large!
        #
        # Reference pip values per STANDARD LOT:
        #   EURUSD: 1 lot = 100,000 units, 1 pip = 0.0001 → $10.00/pip
        #   XAUUSD: 1 lot = 100 oz, 1 pip = 0.01 → $1.00/pip
        #   USDJPY: 1 lot = 100,000 units, 1 pip = 0.01 → ~$6.50/pip (rate-dependent)
        
        config = {
            'pip_value_per_lot': 10.0,  # $10.00 per pip per 1.0 lot (STANDARD lot)
            'pip_size': 0.0001,
            'min_lot': 0.01,
            'lot_step': 0.01,
            'max_lot': 100.0
        }
        
        # Gold (XAUUSD)
        if 'XAU' in symbol:
            # 1 standard lot = 100 oz, 1 pip = $0.01 move
            # Pip value per lot = 100 oz × $0.01 = $1.00
            config.update({
                'pip_value_per_lot': 1.0,  # $1.00 per pip per 1.0 lot
                'pip_size': 0.01,
                'min_lot': 0.01,
                'lot_step': 0.01,
                'max_lot': 50.0
            })
        elif 'XAG' in symbol:
            # Silver: 1 lot = 5000 oz, 1 pip = 0.001
            # Pip value per lot = 5000 × 0.001 = $5.00
            config.update({
                'pip_value_per_lot': 5.0,  # $5.00 per pip per 1.0 lot
                'pip_size': 0.001,
                'min_lot': 0.01,
                'lot_step': 0.01,
                'max_lot': 50.0
            })
        
        # JPY pairs (USD/JPY, EUR/JPY, etc.)
        elif 'JPY' in symbol:
            # 1 lot = 100,000 units, 1 pip = 0.01
            # Pip value ≈ $6.50-$10.00 depending on rate (use conservative $6.50)
            config.update({
                'pip_value_per_lot': 6.50,  # Conservative estimate per 1.0 lot
                'pip_size': 0.01,
            })
        
        # Synthetic Indices (Volatility/Crash/Boom)
        elif 'INDEX' in symbol.upper() or 'VOLATILITY' in symbol.upper() or \
             'CRASH' in symbol.upper() or 'BOOM' in symbol.upper():
            # Synthetic indices vary by broker. Use entry_price to estimate.
            # Typical: 1 lot contract, pip value ≈ price * 0.002 per standard lot
            est_pip_value = max(0.50, abs(float(entry_price or 0.0)) * 0.002)
            config.update({
                'pip_value_per_lot': est_pip_value,
                'pip_size': 0.01,
                'min_lot': 0.01,
                'lot_step': 0.01,
                'max_lot': 10.0,  # Conservative max for synthetics
            })
        
        # USD/XXX pairs (pip value varies with exchange rate)
        elif symbol.startswith('USD'):
            config.update({
                'pip_value_per_lot': 10.0,  # ~$10 per pip per 1.0 lot (approximate)
            })
        
        return config
    
    def update_strategy_performance(self, strategy: str, trade_result: Dict):
        """
        Update strategy performance metrics
        
        Args:
            strategy: Strategy name
            trade_result: Trade result dictionary
        """
        if strategy not in self.strategy_performance:
            self.strategy_performance[strategy] = {
                'trades': 0,
                'wins': 0,
                'losses': 0,
                'total_pnl': 0,
                'total_win': 0,
                'total_loss': 0,
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0
            }
        
        perf = self.strategy_performance[strategy]
        perf['trades'] += 1
        perf['total_pnl'] += trade_result['pnl']
        
        if trade_result['pnl'] > 0:
            perf['wins'] += 1
            perf['total_win'] += trade_result['pnl']
            perf['avg_win'] = perf['total_win'] / perf['wins']
        else:
            perf['losses'] += 1
            perf['total_loss'] += abs(trade_result['pnl'])
            perf['avg_loss'] = perf['total_loss'] / perf['losses']
        
        perf['win_rate'] = (perf['wins'] / perf['trades']) * 100
    
    def get_recommended_risk(self, strategy: str) -> float:
        """
        Get recommended risk percentage for strategy
        
        Args:
            strategy: Strategy name
            
        Returns:
            Recommended risk percentage (0-100)
        """
        perf = self.strategy_performance.get(strategy)
        
        if not perf or perf['trades'] < 10:
            return 1.0  # Default conservative
        
        # Calculate Kelly
        kelly = self.calculate_kelly_fraction(
            perf['win_rate'],
            perf['avg_win'] / perf['avg_loss'] if perf['avg_loss'] > 0 else 1.5
        )
        
        # Apply conservative multiplier
        recommended = kelly * self.kelly_fraction
        
        # Apply limits
        recommended = max(self.min_risk_pct, min(recommended, self.max_risk_pct))
        
        return recommended * 100  # Convert to percentage
    
    def print_position_size_report(self, result: PositionSizeResult):
        """Print detailed position sizing report"""
        print("\n" + "="*80)
        print("POSITION SIZE CALCULATION")
        print("="*80)
        print(f"Final Risk: {result.risk_percent:.2f}%")
        print(f"Lot Size: {result.lot_size:.2f}")
        print(f"Position Value: ${result.position_value:.2f}")
        print(f"\nBase Kelly Fraction: {result.kelly_fraction:.3f}")
        print(f"\nAdjustments Applied:")
        for key, value in result.adjustments.items():
            if key != 'final_risk_pct':
                print(f"  {key:30s}: {value:.3f}")
        print("="*80 + "\n")
