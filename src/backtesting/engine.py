"""
APEX FX Trading Bot - Backtesting Module
Historical backtesting, walk-forward validation, optimization
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from itertools import product
import json
from pathlib import Path


class Backtester:
    """Backtesting engine for strategy validation"""
    
    def __init__(self, initial_balance: float = 10000):
        self.initial_balance = initial_balance
        self.results = {}
        
    def run_backtest(self, strategy_func: Callable, df: pd.DataFrame, 
                     params: Dict = None) -> Dict[str, Any]:
        """
        Run backtest on historical data
        
        Args:
            strategy_func: Function that takes df and params, returns signal
            df: Historical OHLC data
            params: Strategy parameters
            
        Returns:
            Backtest results
        """
        params = params or {}
        
        # Initialize
        balance = self.initial_balance
        equity = self.initial_balance
        positions = []
        trades = []
        equity_curve = []
        
        # Run through each bar
        for i in range(100, len(df)):  # Need enough history
            current_bar = df.iloc[:i+1]
            
            # Get signal from strategy
            signal = strategy_func(current_bar, params)
            
            if signal and not positions:
                # Open position
                entry_price = df.iloc[i]['close']
                position = {
                    'entry_time': df.index[i],
                    'entry_price': entry_price,
                    'direction': signal['direction'],
                    'volume': self._calculate_lot_size(balance, 0.01),  # 1% risk
                    'sl': signal.get('sl'),
                    'tp': signal.get('tp')
                }
                positions.append(position)
            
            # Check for close signals
            for pos in list(positions):
                close_signal = self._check_close(pos, df.iloc[i], balance)
                
                if close_signal:
                    exit_price = df.iloc[i]['close']
                    pnl = self._calculate_pnl(pos, exit_price)
                    
                    trades.append({
                        'entry_time': pos['entry_time'],
                        'exit_time': df.index[i],
                        'direction': pos['direction'],
                        'entry_price': pos['entry_price'],
                        'exit_price': exit_price,
                        'volume': pos['volume'],
                        'pnl': pnl,
                        'return_pct': (pnl / balance) * 100
                    })
                    
                    balance += pnl
                    equity = balance
                    positions.remove(pos)
            
            # Update equity curve
            equity_curve.append({
                'time': df.index[i],
                'equity': equity,
                'drawdown': (equity - self.initial_balance) / self.initial_balance * 100
            })
        
        # Calculate metrics
        metrics = self._calculate_metrics(trades, equity_curve)
        
        return {
            'trades': trades,
            'equity_curve': equity_curve,
            'metrics': metrics
        }
    
    def run_walk_forward(self, strategy_func: Callable, df: pd.DataFrame,
                         train_periods: int = 2000, test_periods: int = 500,
                         step: int = 500) -> List[Dict]:
        """
        Walk-forward analysis
        
        Args:
            strategy_func: Strategy function
            df: Full historical data
            train_periods: Number of bars for training
            test_periods: Number of bars for testing
            step: Step size between tests
            
        Returns:
            List of walk-forward results
        """
        results = []
        
        i = train_periods
        while i + test_periods <= len(df):
            train_df = df.iloc[i-train_periods:i]
            test_df = df.iloc[i:i+test_periods]
            
            # Optimize on train
            best_params = self._optimize_params(strategy_func, train_df)
            
            # Test on test
            test_result = self.run_backtest(strategy_func, test_df, best_params)
            
            results.append({
                'period': f"{test_df.index[0]} to {test_df.index[-1]}",
                'params': best_params,
                'metrics': test_result['metrics']
            })
            
            i += step
        
        return results
    
    def optimize_params(self, strategy_func: Callable, df: pd.DataFrame,
                       param_grid: Dict, metric: str = 'sharpe_ratio') -> Dict:
        """
        Optimize strategy parameters
        
        Args:
            strategy_func: Strategy function
            df: Historical data
            param_grid: Parameter grid to search
            metric: Optimization metric
            
        Returns:
            Best parameters and results
        """
        # Generate parameter combinations
        keys = param_grid.keys()
        values = param_grid.values()
        combinations = list(product(*values))
        
        best_score = -float('inf')
        best_params = {}
        results = []
        
        for combo in combinations:
            params = dict(zip(keys, combo))
            result = self.run_backtest(strategy_func, df, params)
            score = result['metrics'].get(metric, 0)
            
            results.append({
                'params': params,
                'score': score,
                'metrics': result['metrics']
            })
            
            if score > best_score:
                best_score = score
                best_params = params
        
        return {
            'best_params': best_params,
            'best_score': best_score,
            'all_results': results
        }
    
    def _calculate_lot_size(self, balance: float, risk_pct: float) -> float:
        """Calculate lot size based on risk"""
        return round(balance * risk_pct / 100, 2)
    
    def _calculate_pnl(self, position: Dict, exit_price: float) -> float:
        """Calculate PnL for position"""
        if position['direction'] == 'BUY':
            return (exit_price - position['entry_price']) * position['volume'] * 100  # Simplified
        else:
            return (position['entry_price'] - exit_price) * position['volume'] * 100
    
    def _check_close(self, position: Dict, bar, balance: float) -> bool:
        """Check if position should be closed"""
        current_price = bar['close']
        
        # Check SL/TP
        if position['direction'] == 'BUY':
            if position['sl'] and current_price <= position['sl']:
                return True
            if position['tp'] and current_price >= position['tp']:
                return True
        else:
            if position['sl'] and current_price >= position['sl']:
                return True
            if position['tp'] and current_price <= position['tp']:
                return True
        
        return False
    
    def _calculate_metrics(self, trades: List[Dict], equity_curve: List[Dict]) -> Dict:
        """Calculate performance metrics"""
        if not trades:
            return {
                'total_trades': 0,
                'win_rate': 0,
                'profit_factor': 0,
                'max_drawdown': 0,
                'sharpe_ratio': 0,
                'total_return': 0
            }
        
        wins = [t for t in trades if t['pnl'] > 0]
        losses = [t for t in trades if t['pnl'] <= 0]
        
        total_wins = sum(t['pnl'] for t in wins)
        total_losses = abs(sum(t['pnl'] for t in losses))
        
        # Returns
        returns = [t['return_pct'] for t in trades]
        
        # Drawdown
        equity_values = [e['equity'] for e in equity_curve]
        peak = max(equity_values)
        max_dd = max((peak - e) / peak * 100 for e in equity_values)
        
        # Sharpe Ratio (assuming 252 trading days)
        if len(returns) > 1:
            avg_return = np.mean(returns)
            std_return = np.std(returns)
            sharpe = (avg_return / std_return * np.sqrt(252)) if std_return > 0 else 0
        else:
            sharpe = 0
        
        return {
            'total_trades': len(trades),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': len(wins) / len(trades) * 100,
            'total_profit': sum(t['pnl'] for t in trades),
            'profit_factor': total_wins / total_losses if total_losses > 0 else 0,
            'max_drawdown': max_dd,
            'sharpe_ratio': sharpe,
            'total_return': (equity_curve[-1]['equity'] - self.initial_balance) / self.initial_balance * 100,
            'avg_win': total_wins / len(wins) if wins else 0,
            'avg_loss': total_losses / len(losses) if losses else 0
        }
    
    def save_results(self, results: Dict, filename: str):
        """Save backtest results to file"""
        output_dir = Path(__file__).parent.parent.parent / 'backtest_results'
        output_dir.mkdir(exist_ok=True)
        
        with open(output_dir / f'{filename}.json', 'w') as f:
            json.dump(results, f, indent=2, default=str)
    
    def load_results(self, filename: str) -> Dict:
        """Load backtest results from file"""
        output_dir = Path(__file__).parent.parent.parent / 'backtest_results'
        
        with open(output_dir / f'{filename}.json', 'r') as f:
            return json.load(f)


# Global instance
backtester = Backtester()


def get_backtester() -> Backtester:
    """Get global backtester instance"""
    return backtester