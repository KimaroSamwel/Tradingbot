"""
PERFORMANCE ATTRIBUTION ENGINE
Comprehensive performance tracking and attribution analysis

Features:
- Strategy performance by market regime
- Session performance analysis
- Time-of-day patterns
- Symbol-specific performance
- Win rate and R:R tracking
- Strategy correlation analysis
- Performance insights and recommendations
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from collections import defaultdict
import json
import os


@dataclass
class TradeRecord:
    """Complete trade record"""
    trade_id: str
    symbol: str
    strategy: str
    direction: str
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    lot_size: float
    pnl: float
    pnl_percent: float
    market_regime: str
    session: str
    hour_of_day: int
    confluence_score: int
    risk_reward_ratio: float


@dataclass
class StrategyPerformance:
    """Strategy performance metrics"""
    strategy_name: str
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_win: float
    avg_loss: float
    avg_rr: float
    sharpe_ratio: float
    max_consecutive_wins: int
    max_consecutive_losses: int
    best_regime: str
    best_session: str
    best_hour: int


@dataclass
class PerformanceInsight:
    """Performance insight or recommendation"""
    category: str  # STRATEGY, REGIME, SESSION, TIME, SYMBOL
    insight_type: str  # STRENGTH, WEAKNESS, OPPORTUNITY, THREAT
    title: str
    description: str
    recommendation: str
    priority: int  # 1-5 (5 = highest)
    data: Dict


class PerformanceAttributionEngine:
    """
    Analyzes and attributes performance across multiple dimensions
    """
    
    def __init__(self):
        self.trades: List[TradeRecord] = []
        self.strategy_performance: Dict[str, StrategyPerformance] = {}
        self.regime_performance: Dict[str, Dict] = defaultdict(dict)
        self.session_performance: Dict[str, Dict] = defaultdict(dict)
        self.time_performance: Dict[int, Dict] = defaultdict(dict)
        self.symbol_performance: Dict[str, Dict] = defaultdict(dict)
        
    def add_trade(self, trade: TradeRecord):
        """Add trade to performance tracking"""
        self.trades.append(trade)
        
        # Update all performance dimensions
        self._update_strategy_performance(trade)
        self._update_regime_performance(trade)
        self._update_session_performance(trade)
        self._update_time_performance(trade)
        self._update_symbol_performance(trade)

    def _trade_to_dict(self, trade: TradeRecord) -> Dict:
        """Serialize TradeRecord to JSON-safe dict."""
        return {
            'trade_id': trade.trade_id,
            'symbol': trade.symbol,
            'strategy': trade.strategy,
            'direction': trade.direction,
            'entry_price': float(trade.entry_price),
            'exit_price': float(trade.exit_price),
            'entry_time': trade.entry_time.isoformat(),
            'exit_time': trade.exit_time.isoformat(),
            'lot_size': float(trade.lot_size),
            'pnl': float(trade.pnl),
            'pnl_percent': float(trade.pnl_percent),
            'market_regime': trade.market_regime,
            'session': trade.session,
            'hour_of_day': int(trade.hour_of_day),
            'confluence_score': int(trade.confluence_score),
            'risk_reward_ratio': float(trade.risk_reward_ratio)
        }

    def _dict_to_trade(self, data: Dict) -> TradeRecord:
        """Deserialize dict into TradeRecord with safe defaults."""
        return TradeRecord(
            trade_id=str(data.get('trade_id', '')),
            symbol=str(data.get('symbol', 'UNKNOWN')),
            strategy=str(data.get('strategy', 'UNKNOWN')),
            direction=str(data.get('direction', 'NEUTRAL')),
            entry_price=float(data.get('entry_price', 0.0)),
            exit_price=float(data.get('exit_price', 0.0)),
            entry_time=datetime.fromisoformat(str(data.get('entry_time', datetime.now().isoformat()))),
            exit_time=datetime.fromisoformat(str(data.get('exit_time', datetime.now().isoformat()))),
            lot_size=float(data.get('lot_size', 0.0)),
            pnl=float(data.get('pnl', 0.0)),
            pnl_percent=float(data.get('pnl_percent', 0.0)),
            market_regime=str(data.get('market_regime', 'UNKNOWN')),
            session=str(data.get('session', 'UNKNOWN')),
            hour_of_day=int(data.get('hour_of_day', 0)),
            confluence_score=int(data.get('confluence_score', 0)),
            risk_reward_ratio=float(data.get('risk_reward_ratio', 0.0))
        )

    def load_trades_from_json(self, file_path: str) -> int:
        """Load persisted trades and rebuild all performance aggregates."""
        if not file_path or not os.path.exists(file_path):
            return 0

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if not isinstance(data, list):
            return 0

        # Reset state before rebuilding
        self.trades = []
        self.strategy_performance = {}
        self.regime_performance = defaultdict(dict)
        self.session_performance = defaultdict(dict)
        self.time_performance = defaultdict(dict)
        self.symbol_performance = defaultdict(dict)

        loaded = 0
        for item in data:
            try:
                trade = self._dict_to_trade(item)
                self.add_trade(trade)
                loaded += 1
            except Exception:
                # Skip malformed rows while keeping valid history
                continue

        return loaded

    def save_trades_to_json(self, file_path: str, max_records: int = 5000) -> int:
        """Persist recent trade history to disk for forward validation continuity."""
        if not file_path:
            return 0

        directory = os.path.dirname(file_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        trades_to_save = self.trades[-max_records:] if max_records > 0 else self.trades
        payload = [self._trade_to_dict(t) for t in trades_to_save]

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(payload, f, indent=2)

        return len(payload)
    
    def _update_strategy_performance(self, trade: TradeRecord):
        """Update strategy-level performance"""
        strategy = trade.strategy
        
        if strategy not in self.strategy_performance:
            self.strategy_performance[strategy] = StrategyPerformance(
                strategy_name=strategy,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0,
                total_pnl=0,
                avg_win=0,
                avg_loss=0,
                avg_rr=0,
                sharpe_ratio=0,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
                best_regime='UNKNOWN',
                best_session='UNKNOWN',
                best_hour=0
            )
        
        perf = self.strategy_performance[strategy]
        perf.total_trades += 1
        perf.total_pnl += trade.pnl
        
        if trade.pnl > 0:
            perf.winning_trades += 1
            total_wins = sum(t.pnl for t in self.trades if t.strategy == strategy and t.pnl > 0)
            perf.avg_win = total_wins / perf.winning_trades
        else:
            perf.losing_trades += 1
            total_losses = sum(abs(t.pnl) for t in self.trades if t.strategy == strategy and t.pnl < 0)
            perf.avg_loss = total_losses / perf.losing_trades
        
        perf.win_rate = (perf.winning_trades / perf.total_trades) * 100
        
        # Calculate average R:R
        rr_ratios = [t.risk_reward_ratio for t in self.trades if t.strategy == strategy and t.risk_reward_ratio > 0]
        perf.avg_rr = np.mean(rr_ratios) if rr_ratios else 0
        
        # Calculate Sharpe ratio
        strategy_pnls = [t.pnl_percent for t in self.trades if t.strategy == strategy]
        if len(strategy_pnls) > 1:
            perf.sharpe_ratio = np.mean(strategy_pnls) / np.std(strategy_pnls) if np.std(strategy_pnls) > 0 else 0
    
    def _update_regime_performance(self, trade: TradeRecord):
        """Update regime-specific performance"""
        regime = trade.market_regime
        strategy = trade.strategy
        
        if strategy not in self.regime_performance[regime]:
            self.regime_performance[regime][strategy] = {
                'trades': 0,
                'wins': 0,
                'total_pnl': 0,
                'win_rate': 0
            }
        
        perf = self.regime_performance[regime][strategy]
        perf['trades'] += 1
        perf['total_pnl'] += trade.pnl
        
        if trade.pnl > 0:
            perf['wins'] += 1
        
        perf['win_rate'] = (perf['wins'] / perf['trades']) * 100
    
    def _update_session_performance(self, trade: TradeRecord):
        """Update session-specific performance"""
        session = trade.session
        strategy = trade.strategy
        
        if strategy not in self.session_performance[session]:
            self.session_performance[session][strategy] = {
                'trades': 0,
                'wins': 0,
                'total_pnl': 0,
                'win_rate': 0
            }
        
        perf = self.session_performance[session][strategy]
        perf['trades'] += 1
        perf['total_pnl'] += trade.pnl
        
        if trade.pnl > 0:
            perf['wins'] += 1
        
        perf['win_rate'] = (perf['wins'] / perf['trades']) * 100
    
    def _update_time_performance(self, trade: TradeRecord):
        """Update time-of-day performance"""
        hour = trade.hour_of_day
        
        if 'trades' not in self.time_performance[hour]:
            self.time_performance[hour] = {
                'trades': 0,
                'wins': 0,
                'total_pnl': 0,
                'win_rate': 0
            }
        
        perf = self.time_performance[hour]
        perf['trades'] += 1
        perf['total_pnl'] += trade.pnl
        
        if trade.pnl > 0:
            perf['wins'] += 1
        
        perf['win_rate'] = (perf['wins'] / perf['trades']) * 100
    
    def _update_symbol_performance(self, trade: TradeRecord):
        """Update symbol-specific performance"""
        symbol = trade.symbol
        
        if 'trades' not in self.symbol_performance[symbol]:
            self.symbol_performance[symbol] = {
                'trades': 0,
                'wins': 0,
                'total_pnl': 0,
                'win_rate': 0
            }
        
        perf = self.symbol_performance[symbol]
        perf['trades'] += 1
        perf['total_pnl'] += trade.pnl
        
        if trade.pnl > 0:
            perf['wins'] += 1
        
        perf['win_rate'] = (perf['wins'] / perf['trades']) * 100
    
    def generate_insights(self, min_trades: int = 10) -> List[PerformanceInsight]:
        """
        Generate actionable insights from performance data
        
        Args:
            min_trades: Minimum trades required for insight
            
        Returns:
            List of performance insights
        """
        insights = []
        
        # Strategy insights
        insights.extend(self._generate_strategy_insights(min_trades))
        
        # Regime insights
        insights.extend(self._generate_regime_insights(min_trades))
        
        # Session insights
        insights.extend(self._generate_session_insights(min_trades))
        
        # Time insights
        insights.extend(self._generate_time_insights(min_trades))
        
        # Symbol insights
        insights.extend(self._generate_symbol_insights(min_trades))
        
        # Sort by priority
        insights.sort(key=lambda x: x.priority, reverse=True)
        
        return insights
    
    def _generate_strategy_insights(self, min_trades: int) -> List[PerformanceInsight]:
        """Generate strategy-specific insights"""
        insights = []
        
        for strategy, perf in self.strategy_performance.items():
            if perf.total_trades < min_trades:
                continue
            
            # Best performing strategy
            if perf.win_rate > 60 and perf.avg_rr > 1.5:
                insights.append(PerformanceInsight(
                    category='STRATEGY',
                    insight_type='STRENGTH',
                    title=f'{strategy} performing excellently',
                    description=f'Win rate: {perf.win_rate:.1f}%, Avg R:R: {perf.avg_rr:.2f}',
                    recommendation=f'Increase allocation to {strategy}',
                    priority=5,
                    data={'strategy': strategy, 'win_rate': perf.win_rate, 'avg_rr': perf.avg_rr}
                ))
            
            # Poor performing strategy
            elif perf.win_rate < 40 or perf.total_pnl < 0:
                insights.append(PerformanceInsight(
                    category='STRATEGY',
                    insight_type='WEAKNESS',
                    title=f'{strategy} underperforming',
                    description=f'Win rate: {perf.win_rate:.1f}%, Total P&L: ${perf.total_pnl:.2f}',
                    recommendation=f'Reduce or disable {strategy}',
                    priority=4,
                    data={'strategy': strategy, 'win_rate': perf.win_rate, 'total_pnl': perf.total_pnl}
                ))
        
        return insights
    
    def _generate_regime_insights(self, min_trades: int) -> List[PerformanceInsight]:
        """Generate regime-specific insights"""
        insights = []
        
        for regime, strategies in self.regime_performance.items():
            regime_trades = sum(s['trades'] for s in strategies.values())
            
            if regime_trades < min_trades:
                continue
            
            # Find best strategy for regime
            best_strategy = max(strategies.items(), key=lambda x: x[1]['win_rate'])
            
            if best_strategy[1]['win_rate'] > 55:
                insights.append(PerformanceInsight(
                    category='REGIME',
                    insight_type='OPPORTUNITY',
                    title=f'Best strategy for {regime} regime',
                    description=f'{best_strategy[0]} has {best_strategy[1]["win_rate"]:.1f}% win rate in {regime}',
                    recommendation=f'Prioritize {best_strategy[0]} during {regime} market conditions',
                    priority=4,
                    data={'regime': regime, 'strategy': best_strategy[0], 'win_rate': best_strategy[1]['win_rate']}
                ))
        
        return insights
    
    def _generate_session_insights(self, min_trades: int) -> List[PerformanceInsight]:
        """Generate session-specific insights"""
        insights = []
        
        for session, strategies in self.session_performance.items():
            session_trades = sum(s['trades'] for s in strategies.values())
            
            if session_trades < min_trades:
                continue
            
            # Calculate overall session performance
            session_pnl = sum(s['total_pnl'] for s in strategies.values())
            session_win_rate = (sum(s['wins'] for s in strategies.values()) / session_trades) * 100
            
            if session_win_rate > 55 and session_pnl > 0:
                insights.append(PerformanceInsight(
                    category='SESSION',
                    insight_type='STRENGTH',
                    title=f'{session} session performing well',
                    description=f'Win rate: {session_win_rate:.1f}%, P&L: ${session_pnl:.2f}',
                    recommendation=f'Focus trading during {session} session',
                    priority=3,
                    data={'session': session, 'win_rate': session_win_rate, 'pnl': session_pnl}
                ))
            elif session_win_rate < 45 or session_pnl < 0:
                insights.append(PerformanceInsight(
                    category='SESSION',
                    insight_type='THREAT',
                    title=f'{session} session underperforming',
                    description=f'Win rate: {session_win_rate:.1f}%, P&L: ${session_pnl:.2f}',
                    recommendation=f'Avoid or reduce trading during {session} session',
                    priority=4,
                    data={'session': session, 'win_rate': session_win_rate, 'pnl': session_pnl}
                ))
        
        return insights
    
    def _generate_time_insights(self, min_trades: int) -> List[PerformanceInsight]:
        """Generate time-of-day insights"""
        insights = []
        
        # Find best and worst hours
        valid_hours = {h: p for h, p in self.time_performance.items() if p['trades'] >= min_trades}
        
        if not valid_hours:
            return insights
        
        best_hour = max(valid_hours.items(), key=lambda x: x[1]['win_rate'])
        worst_hour = min(valid_hours.items(), key=lambda x: x[1]['win_rate'])
        
        if best_hour[1]['win_rate'] > 60:
            insights.append(PerformanceInsight(
                category='TIME',
                insight_type='OPPORTUNITY',
                title=f'Best trading hour: {best_hour[0]}:00',
                description=f'Win rate: {best_hour[1]["win_rate"]:.1f}% at {best_hour[0]}:00',
                recommendation=f'Increase activity during {best_hour[0]}:00 hour',
                priority=3,
                data={'hour': best_hour[0], 'win_rate': best_hour[1]['win_rate']}
            ))
        
        if worst_hour[1]['win_rate'] < 40:
            insights.append(PerformanceInsight(
                category='TIME',
                insight_type='THREAT',
                title=f'Worst trading hour: {worst_hour[0]}:00',
                description=f'Win rate: {worst_hour[1]["win_rate"]:.1f}% at {worst_hour[0]}:00',
                recommendation=f'Avoid trading during {worst_hour[0]}:00 hour',
                priority=3,
                data={'hour': worst_hour[0], 'win_rate': worst_hour[1]['win_rate']}
            ))
        
        return insights
    
    def _generate_symbol_insights(self, min_trades: int) -> List[PerformanceInsight]:
        """Generate symbol-specific insights"""
        insights = []
        
        for symbol, perf in self.symbol_performance.items():
            if perf['trades'] < min_trades:
                continue
            
            if perf['win_rate'] > 60 and perf['total_pnl'] > 0:
                insights.append(PerformanceInsight(
                    category='SYMBOL',
                    insight_type='STRENGTH',
                    title=f'{symbol} performing well',
                    description=f'Win rate: {perf["win_rate"]:.1f}%, P&L: ${perf["total_pnl"]:.2f}',
                    recommendation=f'Increase focus on {symbol}',
                    priority=3,
                    data={'symbol': symbol, 'win_rate': perf['win_rate'], 'pnl': perf['total_pnl']}
                ))
            elif perf['win_rate'] < 40 or perf['total_pnl'] < 0:
                insights.append(PerformanceInsight(
                    category='SYMBOL',
                    insight_type='WEAKNESS',
                    title=f'{symbol} underperforming',
                    description=f'Win rate: {perf["win_rate"]:.1f}%, P&L: ${perf["total_pnl"]:.2f}',
                    recommendation=f'Reduce or avoid {symbol}',
                    priority=3,
                    data={'symbol': symbol, 'win_rate': perf['win_rate'], 'pnl': perf['total_pnl']}
                ))
        
        return insights
    
    def get_performance_summary(self) -> Dict:
        """Get overall performance summary"""
        if not self.trades:
            return {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'win_rate': 0,
                'total_pnl': 0,
                'avg_win': 0,
                'avg_loss': 0,
                'avg_rr': 0,
                'sharpe_ratio': 0,
                'best_strategy': 'N/A',
                'best_strategy_win_rate': 0
            }
        
        total_trades = len(self.trades)
        winning_trades = sum(1 for t in self.trades if t.pnl > 0)
        losing_trades = sum(1 for t in self.trades if t.pnl < 0)
        breakeven_trades = total_trades - winning_trades - losing_trades
        win_rate = (winning_trades / total_trades) * 100
        total_pnl = sum(t.pnl for t in self.trades)
        
        # Average R:R
        rr_ratios = [t.risk_reward_ratio for t in self.trades if t.risk_reward_ratio > 0]
        avg_rr = np.mean(rr_ratios) if rr_ratios else 0
        
        # Sharpe ratio
        pnl_percents = [t.pnl_percent for t in self.trades]
        sharpe_ratio = np.mean(pnl_percents) / np.std(pnl_percents) if np.std(pnl_percents) > 0 else 0

        wins = [t.pnl for t in self.trades if t.pnl > 0]
        losses = [abs(t.pnl) for t in self.trades if t.pnl < 0]
        
        # Best strategy
        best_strategy = max(self.strategy_performance.items(), 
                          key=lambda x: x[1].win_rate) if self.strategy_performance else ('N/A', None)
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning_trades,
            'losing_trades': losing_trades,
            'breakeven_trades': breakeven_trades,
            'win_rate': win_rate,
            'total_pnl': total_pnl,
            'avg_win': float(np.mean(wins)) if wins else 0,
            'avg_loss': float(np.mean(losses)) if losses else 0,
            'avg_rr': avg_rr,
            'sharpe_ratio': sharpe_ratio,
            'best_strategy': best_strategy[0],
            'best_strategy_win_rate': best_strategy[1].win_rate if best_strategy[1] else 0
        }
    
    def calculate_strategy_correlation(self) -> pd.DataFrame:
        """Calculate correlation between strategy returns"""
        if len(self.trades) < 20:
            return pd.DataFrame()
        
        # Create returns matrix by strategy
        strategies = list(set(t.strategy for t in self.trades))
        
        # Group trades by date and strategy
        strategy_daily_returns = defaultdict(lambda: defaultdict(float))
        
        for trade in self.trades:
            date = trade.entry_time.date()
            strategy_daily_returns[date][trade.strategy] += trade.pnl_percent
        
        # Convert to DataFrame
        returns_data = []
        for date in sorted(strategy_daily_returns.keys()):
            row = {strategy: strategy_daily_returns[date].get(strategy, 0) for strategy in strategies}
            returns_data.append(row)
        
        returns_df = pd.DataFrame(returns_data)
        
        # Calculate correlation
        correlation_matrix = returns_df.corr()
        
        return correlation_matrix
    
    def print_performance_report(self):
        """Print comprehensive performance report"""
        summary = self.get_performance_summary()
        
        print("\n" + "="*80)
        print("PERFORMANCE ATTRIBUTION REPORT")
        print("="*80)
        
        print(f"\nOVERALL PERFORMANCE:")
        print(f"  Total Trades: {summary['total_trades']}")
        print(f"  Win Rate: {summary['win_rate']:.1f}%")
        print(f"  Total P&L: ${summary['total_pnl']:.2f}")
        print(f"  Average R:R: {summary['avg_rr']:.2f}")
        print(f"  Sharpe Ratio: {summary['sharpe_ratio']:.2f}")
        print(
            f"  Best Strategy: {summary.get('best_strategy', 'N/A')} "
            f"({summary.get('best_strategy_win_rate', 0):.1f}% WR)"
        )
        
        print(f"\nSTRATEGY PERFORMANCE:")
        for strategy, perf in sorted(self.strategy_performance.items(), 
                                     key=lambda x: x[1].win_rate, reverse=True):
            print(f"  {strategy:30s} | Trades: {perf.total_trades:3d} | "
                  f"WR: {perf.win_rate:5.1f}% | P&L: ${perf.total_pnl:8.2f} | "
                  f"Avg R:R: {perf.avg_rr:.2f}")
        
        print(f"\nREGIME PERFORMANCE:")
        for regime in self.regime_performance.keys():
            regime_trades = sum(s['trades'] for s in self.regime_performance[regime].values())
            regime_pnl = sum(s['total_pnl'] for s in self.regime_performance[regime].values())
            regime_wins = sum(s['wins'] for s in self.regime_performance[regime].values())
            regime_wr = (regime_wins / regime_trades * 100) if regime_trades > 0 else 0
            
            print(f"  {regime:20s} | Trades: {regime_trades:3d} | "
                  f"WR: {regime_wr:5.1f}% | P&L: ${regime_pnl:8.2f}")
        
        print(f"\nSESSION PERFORMANCE:")
        for session in self.session_performance.keys():
            session_trades = sum(s['trades'] for s in self.session_performance[session].values())
            session_pnl = sum(s['total_pnl'] for s in self.session_performance[session].values())
            session_wins = sum(s['wins'] for s in self.session_performance[session].values())
            session_wr = (session_wins / session_trades * 100) if session_trades > 0 else 0
            
            print(f"  {session:20s} | Trades: {session_trades:3d} | "
                  f"WR: {session_wr:5.1f}% | P&L: ${session_pnl:8.2f}")
        
        # Insights
        insights = self.generate_insights()
        if insights:
            print(f"\nKEY INSIGHTS:")
            for insight in insights[:5]:  # Top 5 insights
                print(f"  [{insight.insight_type}] {insight.title}")
                print(f"    → {insight.recommendation}")
        
        print("="*80 + "\n")
