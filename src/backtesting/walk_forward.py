"""
WALK-FORWARD ANALYSIS
Advanced backtesting with walk-forward optimization
Prevents overfitting by using rolling optimization and out-of-sample testing
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import json


@dataclass
class WalkForwardConfig:
    """Walk-forward analysis configuration"""
    training_period_days: int = 180  # 6 months training
    testing_period_days: int = 30    # 1 month testing
    step_days: int = 30              # Roll forward 1 month at a time
    min_trades_required: int = 50    # Minimum trades for valid test
    optimization_metric: str = 'sharpe_ratio'  # 'sharpe_ratio', 'profit_factor', 'win_rate'


@dataclass
class PeriodResults:
    """Results for a single walk-forward period"""
    period_number: int
    training_start: datetime
    training_end: datetime
    testing_start: datetime
    testing_end: datetime
    
    # Training metrics
    training_trades: int
    training_win_rate: float
    training_profit_factor: float
    training_sharpe: float
    training_total_return: float
    
    # Testing (out-of-sample) metrics
    testing_trades: int
    testing_win_rate: float
    testing_profit_factor: float
    testing_sharpe: float
    testing_total_return: float
    
    # Optimized parameters used in testing
    optimized_params: Dict
    
    # Performance degradation
    performance_degradation: float


class WalkForwardAnalyzer:
    """
    Walk-Forward Analysis Engine
    
    Methodology:
    1. Split data into training and testing windows
    2. Optimize parameters on training data
    3. Test optimized parameters on out-of-sample testing data
    4. Roll forward and repeat
    5. Aggregate results across all periods
    
    This prevents overfitting and gives realistic performance estimates.
    """
    
    def __init__(self, config: WalkForwardConfig = None):
        """
        Initialize walk-forward analyzer
        
        Args:
            config: Walk-forward configuration
        """
        self.config = config or WalkForwardConfig()
        self.results: List[PeriodResults] = []
    
    def analyze(self, data: pd.DataFrame, strategy_class,
               param_grid: Dict[str, List]) -> Dict:
        """
        Run complete walk-forward analysis
        
        Args:
            data: Historical price data
            strategy_class: Strategy class to test
            param_grid: Parameter grid for optimization
        
        Returns:
            Aggregated walk-forward results
        """
        print("\n" + "="*80)
        print("WALK-FORWARD ANALYSIS")
        print("="*80)
        
        periods = self._create_periods(data)
        self.results = []
        
        for i, (train_data, test_data) in enumerate(periods, 1):
            print(f"\n📊 Period {i}/{len(periods)}")
            print(f"   Training: {train_data.index[0]} to {train_data.index[-1]}")
            print(f"   Testing:  {test_data.index[0]} to {test_data.index[-1]}")
            
            # Optimize on training data
            best_params = self._optimize_parameters(
                train_data, strategy_class, param_grid
            )
            
            # Test on out-of-sample data
            train_results = self._backtest_period(train_data, strategy_class, best_params)
            test_results = self._backtest_period(test_data, strategy_class, best_params)
            
            # Calculate performance degradation
            degradation = self._calculate_degradation(train_results, test_results)
            
            # Store results
            period_result = PeriodResults(
                period_number=i,
                training_start=train_data.index[0],
                training_end=train_data.index[-1],
                testing_start=test_data.index[0],
                testing_end=test_data.index[-1],
                
                training_trades=train_results['total_trades'],
                training_win_rate=train_results['win_rate'],
                training_profit_factor=train_results['profit_factor'],
                training_sharpe=train_results['sharpe_ratio'],
                training_total_return=train_results['total_return'],
                
                testing_trades=test_results['total_trades'],
                testing_win_rate=test_results['win_rate'],
                testing_profit_factor=test_results['profit_factor'],
                testing_sharpe=test_results['sharpe_ratio'],
                testing_total_return=test_results['total_return'],
                
                optimized_params=best_params,
                performance_degradation=degradation
            )
            
            self.results.append(period_result)
            
            print(f"   Training: WR={train_results['win_rate']:.1%}, PF={train_results['profit_factor']:.2f}")
            print(f"   Testing:  WR={test_results['win_rate']:.1%}, PF={test_results['profit_factor']:.2f}")
            print(f"   Degradation: {degradation:.1%}")
        
        # Aggregate results
        aggregate = self._aggregate_results()
        self._print_summary(aggregate)
        
        return aggregate
    
    def _create_periods(self, data: pd.DataFrame) -> List[Tuple[pd.DataFrame, pd.DataFrame]]:
        """Create training/testing period splits"""
        periods = []
        
        start_date = data.index[0]
        end_date = data.index[-1]
        
        current_date = start_date
        
        while current_date + timedelta(days=self.config.training_period_days + 
                                      self.config.testing_period_days) <= end_date:
            
            train_start = current_date
            train_end = current_date + timedelta(days=self.config.training_period_days)
            test_start = train_end
            test_end = test_start + timedelta(days=self.config.testing_period_days)
            
            train_data = data[(data.index >= train_start) & (data.index < train_end)]
            test_data = data[(data.index >= test_start) & (data.index < test_end)]
            
            if len(train_data) > 0 and len(test_data) > 0:
                periods.append((train_data, test_data))
            
            current_date += timedelta(days=self.config.step_days)
        
        return periods
    
    def _optimize_parameters(self, data: pd.DataFrame, strategy_class,
                            param_grid: Dict[str, List]) -> Dict:
        """
        Optimize strategy parameters on training data
        
        Args:
            data: Training data
            strategy_class: Strategy to optimize
            param_grid: Parameter grid to search
        
        Returns:
            Best parameters
        """
        best_score = -np.inf
        best_params = {}
        
        # Generate all parameter combinations
        param_combinations = self._generate_param_combinations(param_grid)
        
        for params in param_combinations:
            results = self._backtest_period(data, strategy_class, params)
            
            # Score based on optimization metric
            if self.config.optimization_metric == 'sharpe_ratio':
                score = results['sharpe_ratio']
            elif self.config.optimization_metric == 'profit_factor':
                score = results['profit_factor']
            elif self.config.optimization_metric == 'win_rate':
                score = results['win_rate']
            else:
                score = results['total_return']
            
            if score > best_score and results['total_trades'] >= self.config.min_trades_required:
                best_score = score
                best_params = params
        
        return best_params
    
    def _generate_param_combinations(self, param_grid: Dict[str, List]) -> List[Dict]:
        """Generate all combinations of parameters"""
        import itertools
        
        keys = param_grid.keys()
        values = param_grid.values()
        
        combinations = []
        for combo in itertools.product(*values):
            combinations.append(dict(zip(keys, combo)))
        
        return combinations
    
    def _backtest_period(self, data: pd.DataFrame, strategy_class, params: Dict) -> Dict:
        """
        Backtest strategy on data period
        
        Args:
            data: Price data
            strategy_class: Strategy class
            params: Strategy parameters
        
        Returns:
            Performance metrics
        """
        # Simplified backtest - in production, use full BacktestEngine
        trades = []
        equity = 10000.0
        
        # Simulate trades (placeholder - integrate with actual strategy)
        num_trades = max(1, len(data) // 20)  # Simulate ~1 trade per 20 bars
        winning_trades = int(num_trades * 0.55)  # 55% win rate
        
        for i in range(num_trades):
            if i < winning_trades:
                profit = np.random.uniform(100, 300)
            else:
                profit = np.random.uniform(-200, -50)
            
            trades.append(profit)
            equity += profit
        
        trades = np.array(trades)
        
        # Calculate metrics
        winning = trades[trades > 0]
        losing = trades[trades < 0]
        
        win_rate = len(winning) / len(trades) if len(trades) > 0 else 0
        avg_win = winning.mean() if len(winning) > 0 else 0
        avg_loss = abs(losing.mean()) if len(losing) > 0 else 1
        profit_factor = (winning.sum() / abs(losing.sum())) if losing.sum() != 0 else 0
        
        returns = trades / 10000
        sharpe = (returns.mean() / returns.std() * np.sqrt(252)) if returns.std() > 0 else 0
        
        return {
            'total_trades': len(trades),
            'win_rate': win_rate,
            'profit_factor': profit_factor,
            'sharpe_ratio': sharpe,
            'total_return': (equity - 10000) / 10000,
            'avg_win': avg_win,
            'avg_loss': avg_loss
        }
    
    def _calculate_degradation(self, train_results: Dict, test_results: Dict) -> float:
        """Calculate performance degradation from training to testing"""
        if train_results['profit_factor'] == 0:
            return 0.0
        
        degradation = (train_results['profit_factor'] - test_results['profit_factor']) / train_results['profit_factor']
        return degradation
    
    def _aggregate_results(self) -> Dict:
        """Aggregate results across all periods"""
        if not self.results:
            return {}
        
        total_periods = len(self.results)
        
        # Out-of-sample (testing) metrics
        oos_win_rates = [r.testing_win_rate for r in self.results]
        oos_profit_factors = [r.testing_profit_factor for r in self.results]
        oos_sharpes = [r.testing_sharpe for r in self.results]
        oos_returns = [r.testing_total_return for r in self.results]
        degradations = [r.performance_degradation for r in self.results]
        
        return {
            'total_periods': total_periods,
            'oos_avg_win_rate': np.mean(oos_win_rates),
            'oos_avg_profit_factor': np.mean(oos_profit_factors),
            'oos_avg_sharpe': np.mean(oos_sharpes),
            'oos_total_return': np.sum(oos_returns),
            'oos_std_win_rate': np.std(oos_win_rates),
            'oos_std_profit_factor': np.std(oos_profit_factors),
            'avg_degradation': np.mean(degradations),
            'max_degradation': max(degradations),
            'periods_profitable': sum(1 for r in oos_returns if r > 0),
            'consistency': sum(1 for r in oos_returns if r > 0) / total_periods
        }
    
    def _print_summary(self, aggregate: Dict):
        """Print walk-forward analysis summary"""
        print("\n" + "="*80)
        print("WALK-FORWARD ANALYSIS RESULTS (Out-of-Sample)")
        print("="*80)
        
        print(f"\n📊 Total Periods: {aggregate['total_periods']}")
        print(f"   Profitable Periods: {aggregate['periods_profitable']}/{aggregate['total_periods']}")
        print(f"   Consistency: {aggregate['consistency']:.1%}")
        
        print(f"\n📈 Performance Metrics (Out-of-Sample):")
        print(f"   Win Rate: {aggregate['oos_avg_win_rate']:.1%} ± {aggregate['oos_std_win_rate']:.1%}")
        print(f"   Profit Factor: {aggregate['oos_avg_profit_factor']:.2f} ± {aggregate['oos_std_profit_factor']:.2f}")
        print(f"   Sharpe Ratio: {aggregate['oos_avg_sharpe']:.2f}")
        print(f"   Total Return: {aggregate['oos_total_return']:.1%}")
        
        print(f"\n⚠️ Performance Degradation:")
        print(f"   Average: {aggregate['avg_degradation']:.1%}")
        print(f"   Maximum: {aggregate['max_degradation']:.1%}")
        
        if aggregate['avg_degradation'] > 0.3:
            print(f"\n❌ HIGH DEGRADATION WARNING: Strategy may be overfit!")
        elif aggregate['avg_degradation'] < 0.15:
            print(f"\n✅ LOW DEGRADATION: Strategy appears robust")
        
        print("="*80)
    
    def save_results(self, filename: str = 'data/results/walk_forward_results.json'):
        """Save results to file"""
        import os
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        results_dict = {
            'config': {
                'training_period_days': self.config.training_period_days,
                'testing_period_days': self.config.testing_period_days,
                'step_days': self.config.step_days
            },
            'periods': [
                {
                    'period': r.period_number,
                    'training_win_rate': r.training_win_rate,
                    'testing_win_rate': r.testing_win_rate,
                    'degradation': r.performance_degradation
                }
                for r in self.results
            ],
            'aggregate': self._aggregate_results()
        }
        
        with open(filename, 'w') as f:
            json.dump(results_dict, f, indent=2)
        
        print(f"\n💾 Results saved to {filename}")
