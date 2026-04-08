"""
CORRELATION PORTFOLIO MANAGER
Portfolio-level risk management with correlation analysis

Features:
- Position correlation tracking
- Sector concentration limits
- Value at Risk (VaR) calculation
- Correlation-adjusted position sizing
- Portfolio diversification scoring
- Hedging opportunity detection
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PortfolioPosition:
    """Portfolio position representation"""
    symbol: str
    direction: str  # BUY or SELL
    entry_price: float
    current_price: float
    lot_size: float
    entry_time: datetime
    stop_loss: float
    take_profit: float
    unrealized_pnl: float
    sector: str  # FOREX_MAJOR, FOREX_MINOR, METALS, etc.


@dataclass
class CorrelationAnalysis:
    """Correlation analysis result"""
    symbol_pair: Tuple[str, str]
    correlation: float  # -1 to +1
    period: int  # lookback period
    significant: bool  # correlation > threshold


@dataclass
class PortfolioRisk:
    """Portfolio risk metrics"""
    total_positions: int
    total_exposure: float
    portfolio_var: float  # Value at Risk
    max_drawdown: float
    correlation_score: float  # 0-100 (higher = more correlated)
    diversification_score: float  # 0-100 (higher = more diversified)
    sector_concentration: Dict[str, float]


class CorrelationPortfolioManager:
    """
    Manages portfolio-level risk with correlation analysis
    Inspired by Forex Fury's multi-pair correlation trading
    """
    
    def __init__(self, max_positions: int = 5,
                 max_correlation: float = 0.7,
                 max_sector_concentration: float = 0.6,
                 max_positions_per_symbol: int = 1):
        """
        Initialize portfolio manager
        
        Args:
            max_positions: Maximum concurrent positions
            max_correlation: Maximum correlation between positions
            max_sector_concentration: Maximum % in one sector
            max_positions_per_symbol: Maximum positions per symbol (pyramiding)
        """
        self.max_positions = max_positions
        self.max_correlation = max_correlation
        self.max_sector_concentration = max_sector_concentration
        self.max_positions_per_symbol = max(1, max_positions_per_symbol)
        
        # Active positions: {symbol: [list of PortfolioPosition]}
        self.positions: Dict[str, List[PortfolioPosition]] = {}
        
        # Correlation matrix (pre-defined for major pairs/metals)
        self.correlation_matrix = self._initialize_correlation_matrix()
        
        # Historical correlation data
        self.correlation_history = []
        
    def _initialize_correlation_matrix(self) -> Dict[Tuple[str, str], float]:
        """
        Initialize correlation matrix for major instruments
        Based on historical correlation data
        """
        correlations = {
            # Forex majors correlations
            ('EURUSD', 'GBPUSD'): 0.75,
            ('EURUSD', 'AUDUSD'): 0.68,
            ('EURUSD', 'NZDUSD'): 0.65,
            ('EURUSD', 'USDCHF'): -0.85,
            ('EURUSD', 'USDJPY'): -0.45,
            ('GBPUSD', 'AUDUSD'): 0.62,
            ('GBPUSD', 'NZDUSD'): 0.58,
            ('GBPUSD', 'USDCHF'): -0.78,
            ('GBPUSD', 'EURGBP'): -0.70,
            ('AUDUSD', 'NZDUSD'): 0.88,  # High correlation
            ('AUDUSD', 'USDJPY'): -0.42,
            ('USDJPY', 'USDCHF'): 0.52,
            
            # Gold correlations
            ('XAUUSD', 'EURUSD'): 0.60,
            ('XAUUSD', 'GBPUSD'): 0.55,
            ('XAUUSD', 'DXY'): -0.80,  # Dollar index
            ('XAUUSD', 'USDJPY'): -0.48,
            
            # Oil correlations (if traded)
            ('USOIL', 'CADJPY'): 0.65,
            ('USOIL', 'USDCAD'): -0.72,
        }
        
        # Add reverse pairs
        reversed_correlations = {}
        for (sym1, sym2), corr in correlations.items():
            reversed_correlations[(sym2, sym1)] = corr
        
        correlations.update(reversed_correlations)
        
        return correlations
    
    def _total_position_count(self) -> int:
        """Count total positions across all symbols."""
        return sum(len(pos_list) for pos_list in self.positions.values())

    def can_open_position(self, symbol: str, direction: str,
                         lot_size: float, sector: str) -> Tuple[bool, Optional[str]]:
        """
        Check if new position can be opened
        
        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            lot_size: Position size
            sector: Instrument sector
            
        Returns:
            (allowed, reason_if_not_allowed)
        """
        # Check 1: Maximum total positions
        if self._total_position_count() >= self.max_positions:
            return False, f"Maximum {self.max_positions} positions reached"
        
        # Check 2: Per-symbol position limit (pyramiding support)
        symbol_positions = self.positions.get(symbol, [])
        if len(symbol_positions) >= self.max_positions_per_symbol:
            return False, f"Max {self.max_positions_per_symbol} positions in {symbol} reached"
        
        # Check 3: Correlation with existing positions (skip same-symbol — pyramiding allowed)
        for existing_symbol, pos_list in self.positions.items():
            if existing_symbol == symbol:
                continue  # Same symbol pyramiding is handled by per-symbol limit above
            for position in pos_list:
                corr = self.get_correlation(symbol, existing_symbol)

                # Convert pair correlation into directional exposure correlation.
                # Opposite directions on positively correlated pairs reduce risk,
                # while opposite directions on negatively correlated pairs can increase it.
                directional_corr = corr if direction == position.direction else -corr

                if directional_corr > self.max_correlation:
                    return False, (
                        f"High directional correlation ({directional_corr:.2f}) with "
                        f"{existing_symbol}"
                    )
                break  # Only need to check correlation once per symbol
        
        # Check 4: Sector concentration
        sector_exposure = self._calculate_sector_exposure()
        current_sector_pct = sector_exposure.get(sector, 0)
        
        if current_sector_pct >= self.max_sector_concentration:
            return False, f"Sector concentration limit: {sector} at {current_sector_pct:.1%}"
        
        # Check 5: Portfolio VaR limit (simplified)
        # This would calculate expected portfolio VaR with new position
        # For now, simplified check
        
        return True, None
    
    def get_correlation(self, symbol1: str, symbol2: str) -> float:
        """Get correlation between two symbols"""
        if symbol1 == symbol2:
            return 1.0
        
        # Check pre-defined matrix
        corr = self.correlation_matrix.get((symbol1, symbol2))
        if corr is not None:
            return corr
        
        # Default to low correlation if not in matrix
        return 0.0
    
    def add_position(self, position: PortfolioPosition):
        """Add new position to portfolio (supports multiple per symbol)."""
        if position.symbol not in self.positions:
            self.positions[position.symbol] = []
        self.positions[position.symbol].append(position)
    
    def remove_position(self, symbol: str, ticket: Optional[int] = None):
        """Remove position from portfolio. If ticket given, remove that specific one; else remove all for symbol."""
        if symbol in self.positions:
            if ticket is not None:
                self.positions[symbol] = [
                    p for p in self.positions[symbol]
                    if getattr(p, 'ticket', None) != ticket
                ]
            else:
                self.positions[symbol] = []
            # Clean up empty lists
            if not self.positions[symbol]:
                del self.positions[symbol]
    
    def update_position_price(self, symbol: str, current_price: float):
        """Update current price for all positions of a symbol."""
        if symbol in self.positions:
            for position in self.positions[symbol]:
                position.current_price = current_price
                
                # Calculate unrealized PnL
                # FIX: Gold uses 100 oz per lot, not 100000 units
                if 'XAU' in symbol or 'XAG' in symbol:
                    # Precious metals: 1 lot = 100 oz
                    contract_size = 100
                else:
                    # Forex: 1 standard lot = 100000 units
                    contract_size = 100000
                
                if position.direction == 'BUY':
                    position.unrealized_pnl = (current_price - position.entry_price) * position.lot_size * contract_size
                else:
                    position.unrealized_pnl = (position.entry_price - current_price) * position.lot_size * contract_size
    
    def calculate_portfolio_risk(self, account_balance: float) -> PortfolioRisk:
        """
        Calculate comprehensive portfolio risk metrics
        
        Args:
            account_balance: Current account balance
            
        Returns:
            PortfolioRisk with all metrics
        """
        if not self.positions:
            return PortfolioRisk(
                total_positions=0,
                total_exposure=0,
                portfolio_var=0,
                max_drawdown=0,
                correlation_score=0,
                diversification_score=100,
                sector_concentration={}
            )
        
        # Flatten all positions into a single list
        all_positions = [p for pos_list in self.positions.values() for p in pos_list]
        if not all_positions:
            return PortfolioRisk(
                total_positions=0, total_exposure=0, portfolio_var=0,
                max_drawdown=0, correlation_score=0, diversification_score=100,
                sector_concentration={}
            )
        
        # Total exposure (notional value)
        total_exposure = sum(p.lot_size * p.current_price * 100000 for p in all_positions)
        
        # Portfolio VaR (simplified Value at Risk)
        portfolio_var = self._calculate_portfolio_var(account_balance)
        
        # Max drawdown (potential loss if all stop losses hit)
        max_drawdown = sum(
            abs(p.entry_price - p.stop_loss) * p.lot_size * 100000
            for p in all_positions
        ) / account_balance
        
        # Correlation score
        correlation_score = self._calculate_correlation_score()
        
        # Diversification score (inverse of correlation)
        diversification_score = 100 - correlation_score
        
        # Sector concentration
        sector_concentration = self._calculate_sector_exposure()
        
        return PortfolioRisk(
            total_positions=self._total_position_count(),
            total_exposure=total_exposure / account_balance,
            portfolio_var=portfolio_var,
            max_drawdown=max_drawdown,
            correlation_score=correlation_score,
            diversification_score=diversification_score,
            sector_concentration=sector_concentration
        )
    
    def _calculate_portfolio_var(self, account_balance: float,
                                 confidence_level: float = 0.95) -> float:
        """
        Calculate Portfolio Value at Risk
        
        Uses correlation-adjusted VaR calculation
        """
        if not self.positions:
            return 0
        
        # Individual position VaRs
        position_vars = []
        
        all_positions = [p for pos_list in self.positions.values() for p in pos_list]
        for position in all_positions:
            # Assume 2% daily volatility for simplicity
            volatility = 0.02
            
            # Position value
            position_value = position.lot_size * position.current_price * 100000
            
            # Individual VaR (using normal distribution)
            z_score = 1.645 if confidence_level == 0.95 else 1.96
            
            var = position_value * volatility * z_score
            position_vars.append(var)
        
        # Correlation-adjusted portfolio VaR
        total_var = sum(position_vars)
        
        # Apply correlation adjustment
        avg_correlation = self._calculate_correlation_score() / 100
        
        num_positions = max(len(self.positions), 1)  # unique symbols
        # Diversification benefit
        diversification_factor = np.sqrt(
            avg_correlation + (1 - avg_correlation) / num_positions
        )
        
        portfolio_var = total_var * diversification_factor / account_balance
        
        return portfolio_var
    
    def _calculate_correlation_score(self) -> float:
        """
        Calculate average correlation score across portfolio
        Returns 0-100 (higher = more correlated)
        """
        if len(self.positions) < 2:
            return 0
        
        correlations = []
        symbols = list(self.positions.keys())
        
        for i in range(len(symbols)):
            for j in range(i + 1, len(symbols)):
                corr = abs(self.get_correlation(symbols[i], symbols[j]))
                correlations.append(corr)
        
        if not correlations:
            return 0
        
        avg_correlation = np.mean(correlations)
        return avg_correlation * 100
    
    def _calculate_sector_exposure(self) -> Dict[str, float]:
        """Calculate exposure by sector as fraction of max_positions capacity.
        
        Uses position COUNT / max_positions instead of notional value ratios.
        Old approach: 1 GBPUSD = 100% FOREX_MAJOR (blocked everything in sector).
        New approach: 1 GBPUSD with max_positions=5 = 20% FOREX_MAJOR (correct).
        """
        sector_counts: Dict[str, int] = {}
        
        for pos_list in self.positions.values():
            for position in pos_list:
                sector = position.sector
                sector_counts[sector] = sector_counts.get(sector, 0) + 1
        
        # Express as fraction of max_positions capacity
        capacity = max(self.max_positions, 1)
        sector_exposure = {
            sector: count / capacity
            for sector, count in sector_counts.items()
        }
        
        return sector_exposure
    
    def find_hedging_opportunities(self) -> List[Dict]:
        """
        Find potential hedging opportunities
        Based on negative correlations
        """
        opportunities = []
        
        for symbol, pos_list in self.positions.items():
            if not pos_list:
                continue
            position = pos_list[0]  # Use first position for direction reference
            # Look for negatively correlated symbols
            for candidate_symbol, corr in self.correlation_matrix.items():
                if candidate_symbol[0] != symbol:
                    continue
                
                hedge_symbol = candidate_symbol[1]
                
                # Check if correlation is negative
                if corr < -0.6:  # Strong negative correlation
                    # Check if we don't already have this position
                    if hedge_symbol not in self.positions:
                        opportunities.append({
                            'position': symbol,
                            'hedge_symbol': hedge_symbol,
                            'correlation': corr,
                            'direction': 'SELL' if position.direction == 'BUY' else 'BUY',
                            'reason': f'Hedge {symbol} with {hedge_symbol} (corr: {corr:.2f})'
                        })
        
        return opportunities
    
    def get_position_adjustment_multiplier(self, symbol: str) -> float:
        """
        Get position size multiplier based on correlation
        Higher correlation = smaller position size
        
        Returns:
            Multiplier between 0.5 and 1.0
        """
        if not self.positions:
            return 1.0
        
        max_correlation = 0
        
        for existing_symbol in self.positions.keys():
            corr = abs(self.get_correlation(symbol, existing_symbol))
            max_correlation = max(max_correlation, corr)
        
        # Linear reduction based on correlation
        # 0.3 correlation = no reduction
        # 0.7+ correlation = 50% reduction
        
        if max_correlation < 0.3:
            return 1.0
        elif max_correlation > 0.7:
            return 0.5
        else:
            # Linear interpolation
            reduction = (max_correlation - 0.3) / 0.4  # 0 to 1
            return 1.0 - (reduction * 0.5)  # 1.0 to 0.5
    
    def calculate_correlation_matrix_realtime(self, price_history: Dict[str, pd.DataFrame],
                                             period: int = 100) -> pd.DataFrame:
        """
        Calculate real-time correlation matrix from price data
        
        Args:
            price_history: Dictionary of symbol -> price dataframe
            period: Lookback period for correlation
            
        Returns:
            Correlation matrix as DataFrame
        """
        # Extract returns for each symbol
        returns_dict = {}
        
        for symbol, df in price_history.items():
            if len(df) < period:
                continue
            
            returns = df['close'].pct_change().iloc[-period:]
            returns_dict[symbol] = returns
        
        # Create DataFrame from returns
        returns_df = pd.DataFrame(returns_dict)
        
        # Calculate correlation
        correlation_matrix = returns_df.corr()
        
        return correlation_matrix
    
    def update_correlation_matrix(self, price_history: Dict[str, pd.DataFrame]):
        """Update correlation matrix with real-time data"""
        realtime_corr = self.calculate_correlation_matrix_realtime(price_history)
        
        # Update internal matrix
        for symbol1 in realtime_corr.columns:
            for symbol2 in realtime_corr.columns:
                if symbol1 != symbol2:
                    corr_value = realtime_corr.loc[symbol1, symbol2]
                    self.correlation_matrix[(symbol1, symbol2)] = corr_value
        
        # Store in history
        self.correlation_history.append({
            'timestamp': datetime.now(),
            'matrix': realtime_corr.copy()
        })
        
        # Keep only last 100 entries
        if len(self.correlation_history) > 100:
            self.correlation_history = self.correlation_history[-100:]
    
    def detect_correlation_changes(self, threshold: float = 0.3) -> List[Dict]:
        """
        Detect significant changes in correlation
        
        Args:
            threshold: Minimum correlation change to report
            
        Returns:
            List of correlation changes
        """
        if len(self.correlation_history) < 2:
            return []
        
        changes = []
        
        current_matrix = self.correlation_history[-1]['matrix']
        previous_matrix = self.correlation_history[-2]['matrix']
        
        for symbol1 in current_matrix.columns:
            for symbol2 in current_matrix.columns:
                if symbol1 >= symbol2:  # Avoid duplicates
                    continue
                
                current_corr = current_matrix.loc[symbol1, symbol2]
                previous_corr = previous_matrix.loc[symbol1, symbol2]
                
                change = abs(current_corr - previous_corr)
                
                if change > threshold:
                    changes.append({
                        'pair': (symbol1, symbol2),
                        'previous': previous_corr,
                        'current': current_corr,
                        'change': current_corr - previous_corr,
                        'timestamp': datetime.now()
                    })
        
        return changes
    
    def print_portfolio_status(self, account_balance: float):
        """Print portfolio status in readable format"""
        risk = self.calculate_portfolio_risk(account_balance)
        
        print("\n" + "="*80)
        print("PORTFOLIO STATUS")
        print("="*80)
        print(f"Active Positions: {risk.total_positions}/{self.max_positions}")
        print(f"Total Exposure: {risk.total_exposure:.1%} of account")
        print(f"Portfolio VaR (95%): {risk.portfolio_var:.2%}")
        print(f"Max Drawdown Risk: {risk.max_drawdown:.2%}")
        print(f"\nDiversification:")
        print(f"  Correlation Score: {risk.correlation_score:.1f}/100")
        print(f"  Diversification Score: {risk.diversification_score:.1f}/100")
        
        print(f"\nSector Concentration:")
        for sector, pct in risk.sector_concentration.items():
            print(f"  {sector:20s}: {pct:.1%}")
        
        print(f"\nActive Positions:")
        for symbol, pos_list in self.positions.items():
            for position in pos_list:
                pnl_pct = (position.unrealized_pnl / account_balance) * 100
                print(f"  {position.direction:4s} {symbol:10s} @ {position.entry_price:.5f} | "
                      f"P&L: ${position.unrealized_pnl:.2f} ({pnl_pct:+.2f}%)")
        
        print("="*80 + "\n")
