"""
STRATEGY CONFLICT MANAGER
Intelligent strategy grouping and conflict resolution for all 112+ strategies

Features:
- Strategy compatibility groups
- Conflict detection and resolution
- Dynamic group selection based on market regime
- Performance-based strategy weighting
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class MarketRegime(Enum):
    """Market regime types"""
    STRONG_TREND = "STRONG_TREND"
    MODERATE_TREND = "MODERATE_TREND"
    RANGING = "RANGING"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    LOW_VOLATILITY = "LOW_VOLATILITY"
    TRANSITION = "TRANSITION"


@dataclass
class StrategyGroup:
    """Strategy group definition"""
    name: str
    strategies: List[str]
    market_conditions: List[MarketRegime]
    conflict_score: float  # 0-1, lower is better
    max_strategies: int
    performance_weight: float = 1.0


class StrategyConflictManager:
    """
    Manages strategy conflicts and intelligent grouping
    Ensures complementary strategies run together
    CRITICAL: Prevents conflicting strategies from running simultaneously
    """
    
    def __init__(self):
        """Initialize conflict manager with strategy groups"""
        
        # CRITICAL ADDITION: Explicit conflict pairs
        # These strategies CANNOT run together
        self.conflicting_strategy_pairs = [
            # Trend following vs Mean reversion (OPPOSITE directions)
            ('trend_following', 'mean_reversion'),
            ('ma_crossover', 'bollinger_reversion'),
            ('breakout', 'grid_trading'),
            ('momentum', 'pivot_bounce'),
            
            # ICT conflicting approaches
            ('ict_trend', 'ict_counter_trend'),
            ('liquidity_sweep_long', 'liquidity_sweep_short'),
            
            # Volatility conflicts
            ('volatility_breakout', 'low_volatility_strategy'),
            ('news_trading', 'avoid_news_strategy'),
        ]
        
        # Define strategy compatibility groups
        self.strategy_groups = {
            # GROUP 1: TREND FOLLOWING (Complementary)
            'TREND_FOLLOWING_GROUP': StrategyGroup(
                name='TREND_FOLLOWING',
                strategies=[
                    'ma_crossover', 'triple_ema', 'golden_cross',
                    'ichimoku', 'supertrend', 'adx_trend',
                    'trendline_breakout', 'channel_breakout'
                ],
                market_conditions=[MarketRegime.STRONG_TREND, MarketRegime.MODERATE_TREND],
                conflict_score=0.1,
                max_strategies=4
            ),
            
            # GROUP 2: MEAN REVERSION (Complementary)
            'MEAN_REVERSION_GROUP': StrategyGroup(
                name='MEAN_REVERSION',
                strategies=[
                    'bollinger_reversion', 'rsi_oversold', 'rsi_overbought',
                    'stochastic_reversion', 'pivot_bounce', 'support_resistance',
                    'fibonacci_retracement', 'mean_reversion'
                ],
                market_conditions=[MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY],
                conflict_score=0.15,
                max_strategies=3
            ),
            
            # GROUP 3: BREAKOUT/MOMENTUM (Complementary)
            'BREAKOUT_GROUP': StrategyGroup(
                name='BREAKOUT_MOMENTUM',
                strategies=[
                    'volatility_breakout', 'session_breakout', 'london_open',
                    'ny_open', 'opening_range', 'momentum', 'macd_momentum',
                    'rsi_momentum', 'atr_expansion', 'donchian_breakout'
                ],
                market_conditions=[MarketRegime.TRANSITION, MarketRegime.HIGH_VOLATILITY],
                conflict_score=0.2,
                max_strategies=3
            ),
            
            # GROUP 4: ICT/SMART MONEY (Complementary)
            'ICT_SMART_MONEY_GROUP': StrategyGroup(
                name='ICT_SMART_MONEY',
                strategies=[
                    'ict_2022', 'power_of_3', 'supply_demand', 'order_blocks',
                    'fvg', 'liquidity_sweep', 'market_structure', 'breaker_blocks',
                    'wyckoff', 'vsa'
                ],
                market_conditions=[
                    MarketRegime.STRONG_TREND, MarketRegime.MODERATE_TREND,
                    MarketRegime.RANGING, MarketRegime.HIGH_VOLATILITY
                ],
                conflict_score=0.05,  # Very low conflict
                max_strategies=4
            ),
            
            # GROUP 5: FOREX-SPECIFIC (Complementary)
            'FOREX_GROUP': StrategyGroup(
                name='FOREX_SPECIFIC',
                strategies=[
                    'carry_trade', 'correlation_trading', 'dxy_correlation',
                    'currency_strength', 'intermarket', 'gold_usd_correlation',
                    'oil_cad_correlation', 'risk_sentiment'
                ],
                market_conditions=[
                    MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY,
                    MarketRegime.MODERATE_TREND
                ],
                conflict_score=0.12,
                max_strategies=3
            ),
            
            # GROUP 6: SCALPING (High conflict within, but OK together)
            'SCALPING_GROUP': StrategyGroup(
                name='SCALPING',
                strategies=[
                    'ema_scalping', 'bb_scalping', 'stochastic_scalping',
                    'volume_scalping', 'tick_scalping', 'rsi_scalping'
                ],
                market_conditions=[MarketRegime.HIGH_VOLATILITY, MarketRegime.MODERATE_TREND],
                conflict_score=0.25,
                max_strategies=2  # Limit scalping strategies
            ),
            
            # GROUP 7: SWING TRADING (Complementary)
            'SWING_GROUP': StrategyGroup(
                name='SWING_TRADING',
                strategies=[
                    'fibonacci_swing', 'macd_divergence_swing', 'rsi_divergence_swing',
                    'support_resistance_swing', 'trendline_swing'
                ],
                market_conditions=[
                    MarketRegime.STRONG_TREND, MarketRegime.MODERATE_TREND,
                    MarketRegime.RANGING
                ],
                conflict_score=0.1,
                max_strategies=3
            ),
            
            # GROUP 8: PATTERN RECOGNITION (Complementary)
            'PATTERN_GROUP': StrategyGroup(
                name='PATTERN_RECOGNITION',
                strategies=[
                    'hammer', 'shooting_star', 'engulfing', 'morning_star',
                    'evening_star', 'head_shoulders', 'double_top', 'double_bottom',
                    'triangle', 'gartley', 'butterfly'
                ],
                market_conditions=[
                    MarketRegime.RANGING, MarketRegime.TRANSITION,
                    MarketRegime.MODERATE_TREND
                ],
                conflict_score=0.18,
                max_strategies=3
            ),
            
            # GROUP 9: TIME-BASED (Complementary)
            'TIME_BASED_GROUP': StrategyGroup(
                name='TIME_BASED',
                strategies=[
                    'day_of_week', 'time_of_day', 'turn_of_month',
                    'london_fix', 'ny_close', 'weekend_gap'
                ],
                market_conditions=[MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY],
                conflict_score=0.15,
                max_strategies=2
            ),
            
            # GROUP 10: GRID TRADING (Special handling)
            'GRID_GROUP': StrategyGroup(
                name='GRID_TRADING',
                strategies=[
                    'standard_grid', 'fibonacci_grid', 'mean_reversion_grid',
                    'pivot_grid'
                ],
                market_conditions=[MarketRegime.RANGING, MarketRegime.LOW_VOLATILITY],
                conflict_score=0.3,  # Higher conflict with breakout strategies
                max_strategies=1  # Only one grid strategy at a time
            )
        }
        
        # Define EXPLICIT conflict pairs (cannot run simultaneously)
        self.conflict_pairs = [
            ('trend_following', 'mean_reversion'),  # Direct opposite
            ('breakout', 'grid_trading'),  # Breakout vs fade
            ('carry_trade', 'news_trading'),  # Long-term vs event
            ('scalping', 'swing_trading'),  # Timeframe conflict
            ('momentum', 'mean_reversion'),  # Continuation vs reversal
            ('volatility_breakout', 'range_trading'),  # Breakout vs fade
        ]
        
        # Performance tracking
        self.strategy_performance = {}
        self.group_performance = {}
        
    def select_compatible_groups(self, market_regime: MarketRegime,
                                 max_groups: int = 3) -> List[StrategyGroup]:
        """
        Select compatible strategy groups for current market regime
        
        Args:
            market_regime: Current market regime
            max_groups: Maximum number of groups to select
            
        Returns:
            List of compatible strategy groups
        """
        compatible_groups = []
        
        # Filter groups by market regime
        for group_key, group in self.strategy_groups.items():
            if market_regime in group.market_conditions:
                compatible_groups.append(group)
        
        # Sort by performance weight (if available)
        compatible_groups.sort(
            key=lambda g: g.performance_weight * (1 - g.conflict_score),
            reverse=True
        )
        
        # Select top groups ensuring no conflicts
        selected_groups = []
        for group in compatible_groups:
            if self._is_group_compatible(group, selected_groups):
                selected_groups.append(group)
                
            if len(selected_groups) >= max_groups:
                break
        
        return selected_groups
    
    def select_strategies_from_groups(self, groups: List[StrategyGroup],
                                     max_total_strategies: int = 15) -> List[str]:
        """
        Select individual strategies from groups
        
        Args:
            groups: Selected strategy groups
            max_total_strategies: Maximum total strategies to select
            
        Returns:
            List of strategy names
        """
        selected_strategies = []
        
        for group in groups:
            # Get strategies from this group
            group_strategies = group.strategies[:group.max_strategies]
            
            # Filter by performance if available
            if self.strategy_performance:
                group_strategies = self._filter_by_performance(
                    group_strategies,
                    min_win_rate=45
                )
            
            # Add strategies ensuring no conflicts
            for strategy in group_strategies:
                if not self._has_strategy_conflict(strategy, selected_strategies):
                    selected_strategies.append(strategy)
                    
                if len(selected_strategies) >= max_total_strategies:
                    return selected_strategies
        
        return selected_strategies
    
    def detect_conflicts(self, strategies: List[str]) -> List[Tuple[str, str, str]]:
        """
        Detect conflicts in strategy list
        
        Args:
            strategies: List of strategy names
            
        Returns:
            List of (strategy1, strategy2, conflict_reason) tuples
        """
        conflicts = []
        
        for i, strategy1 in enumerate(strategies):
            for strategy2 in strategies[i+1:]:
                # Check explicit conflicts
                if self._is_conflict_pair(strategy1, strategy2):
                    conflicts.append((
                        strategy1,
                        strategy2,
                        "Explicit conflict pair"
                    ))
                
                # Check group conflicts
                group1 = self._get_strategy_group(strategy1)
                group2 = self._get_strategy_group(strategy2)
                
                if group1 and group2 and group1.name != group2.name:
                    # Check if groups have high combined conflict score
                    combined_conflict = group1.conflict_score + group2.conflict_score
                    if combined_conflict > 0.5:
                        conflicts.append((
                            strategy1,
                            strategy2,
                            f"High group conflict: {combined_conflict:.2f}"
                        ))
        
        return conflicts
    
    def resolve_conflicts(self, strategies: List[str]) -> List[str]:
        """
        Resolve conflicts by removing lower-performing strategies
        
        Args:
            strategies: List of strategy names with potential conflicts
            
        Returns:
            Conflict-free strategy list
        """
        conflicts = self.detect_conflicts(strategies)
        
        if not conflicts:
            return strategies
        
        # Build conflict graph
        conflict_graph = {}
        for s1, s2, reason in conflicts:
            if s1 not in conflict_graph:
                conflict_graph[s1] = []
            if s2 not in conflict_graph:
                conflict_graph[s2] = []
            conflict_graph[s1].append(s2)
            conflict_graph[s2].append(s1)
        
        # Remove strategies with most conflicts, lowest performance
        resolved = strategies.copy()
        
        for strategy in sorted(conflict_graph.keys(),
                              key=lambda s: len(conflict_graph[s]),
                              reverse=True):
            
            if strategy in resolved:
                # Check if removing this strategy resolves conflicts
                remaining_conflicts = self.detect_conflicts(
                    [s for s in resolved if s != strategy]
                )
                
                if len(remaining_conflicts) < len(conflicts):
                    resolved.remove(strategy)
                    conflicts = remaining_conflicts
                    
                if not conflicts:
                    break
        
        return resolved
    
    def update_performance(self, strategy: str, trade_result: Dict):
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
                'win_rate': 0,
                'avg_win': 0,
                'avg_loss': 0
            }
        
        perf = self.strategy_performance[strategy]
        perf['trades'] += 1
        
        if trade_result['pnl'] > 0:
            perf['wins'] += 1
            perf['avg_win'] = (perf['avg_win'] * (perf['wins'] - 1) + 
                              trade_result['pnl']) / perf['wins']
        else:
            perf['losses'] += 1
            perf['avg_loss'] = (perf['avg_loss'] * (perf['losses'] - 1) + 
                               abs(trade_result['pnl'])) / perf['losses']
        
        perf['total_pnl'] += trade_result['pnl']
        perf['win_rate'] = (perf['wins'] / perf['trades']) * 100
    
    def get_strategy_context(self, market_regime: MarketRegime,
                           volatility: float,
                           session: str) -> Dict:
        """
        Get complete strategy context with groups and individual strategies
        
        Args:
            market_regime: Current market regime
            volatility: Current volatility (0-1)
            session: Trading session (LONDON, NY, ASIAN)
            
        Returns:
            Dictionary with selected groups and strategies
        """
        # Select compatible groups
        selected_groups = self.select_compatible_groups(market_regime)
        
        # Adjust for volatility
        if volatility > 0.7:  # High volatility
            # Prefer breakout and momentum groups
            selected_groups = [g for g in selected_groups 
                             if 'BREAKOUT' in g.name or 'MOMENTUM' in g.name]
        elif volatility < 0.3:  # Low volatility
            # Prefer mean reversion and range groups
            selected_groups = [g for g in selected_groups 
                             if 'REVERSION' in g.name or 'RANGE' in g.name]
        
        # Adjust for session
        if session == 'LONDON' or session == 'NY':
            # Add ICT group for killzone sessions
            ict_group = self.strategy_groups.get('ICT_SMART_MONEY_GROUP')
            if ict_group and ict_group not in selected_groups:
                selected_groups.insert(0, ict_group)
        
        # Select strategies from groups
        strategies = self.select_strategies_from_groups(selected_groups)
        
        # Resolve any conflicts
        strategies = self.resolve_conflicts(strategies)
        
        return {
            'groups': [g.name for g in selected_groups],
            'strategies': strategies,
            'total_strategies': len(strategies),
            'conflict_score': self._calculate_total_conflict(strategies)
        }
    
    def _is_group_compatible(self, group: StrategyGroup,
                            selected_groups: List[StrategyGroup]) -> bool:
        """Check if group is compatible with already selected groups"""
        for selected in selected_groups:
            # Check if any strategies from groups conflict
            for s1 in group.strategies:
                for s2 in selected.strategies:
                    if self._is_conflict_pair(s1, s2):
                        return False
        return True
    
    def _has_strategy_conflict(self, strategy: str,
                              selected_strategies: List[str]) -> bool:
        """Check if strategy conflicts with any selected strategy"""
        for selected in selected_strategies:
            if self._is_conflict_pair(strategy, selected):
                return True
        return False
    
    def _is_conflict_pair(self, strategy1: str, strategy2: str) -> bool:
        """Check if two strategies are an explicit conflict pair"""
        for s1, s2 in self.conflict_pairs:
            if (s1 in strategy1.lower() and s2 in strategy2.lower()) or \
               (s2 in strategy1.lower() and s1 in strategy2.lower()):
                return True
        return False
    
    def _get_strategy_group(self, strategy: str) -> Optional[StrategyGroup]:
        """Get the group a strategy belongs to"""
        for group in self.strategy_groups.values():
            if strategy in group.strategies:
                return group
        return None
    
    def _filter_by_performance(self, strategies: List[str],
                               min_win_rate: float = 45) -> List[str]:
        """Filter strategies by minimum win rate"""
        filtered = []
        for strategy in strategies:
            perf = self.strategy_performance.get(strategy)
            if not perf or perf['win_rate'] >= min_win_rate:
                filtered.append(strategy)
        return filtered
    
    def _calculate_total_conflict(self, strategies: List[str]) -> float:
        """Calculate total conflict score for strategy list"""
        if len(strategies) <= 1:
            return 0.0
        
        conflicts = self.detect_conflicts(strategies)
        return len(conflicts) / (len(strategies) * (len(strategies) - 1) / 2)
    
    def _update_group_performance(self, group_name: str, trade_result: Dict):
        """Update group-level performance"""
        if group_name not in self.group_performance:
            self.group_performance[group_name] = {
                'trades': 0,
                'total_pnl': 0,
                'win_rate': 0
            }
        
        gperf = self.group_performance[group_name]
        gperf['trades'] += 1
        gperf['total_pnl'] += trade_result['pnl']
        
        # Update group's performance weight in strategy_groups
        group = next((g for g in self.strategy_groups.values() 
                     if g.name == group_name), None)
        if group:
            # Weight based on recent performance
            if gperf['trades'] >= 10:
                group.performance_weight = max(0.5, min(2.0, 
                    1.0 + (gperf['total_pnl'] / gperf['trades']) / 100))
    
    def print_strategy_mix(self, strategy_mix: Dict):
        """Print selected strategy mix in readable format"""
        print("\n" + "="*80)
        print("SELECTED STRATEGY MIX")
        print("="*80)
        print(f"Total Strategies: {strategy_mix['total_strategies']}")
        print(f"Conflict Score: {strategy_mix['conflict_score']:.3f}")
        print(f"\nActive Groups: {', '.join(strategy_mix['groups'])}")
        print(f"\nStrategies:")
        for i, strategy in enumerate(strategy_mix['strategies'], 1):
            group = self._get_strategy_group(strategy)
            group_name = group.name if group else 'UNKNOWN'
            perf = self.strategy_performance.get(strategy, {})
            win_rate = perf.get('win_rate', 0)
            print(f"  {i:2d}. [{group_name:20s}] {strategy:30s} "
                  f"(WR: {win_rate:.1f}%)")
        print("="*80 + "\n")
