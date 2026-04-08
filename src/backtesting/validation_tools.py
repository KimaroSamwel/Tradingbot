"""
Validation Tools for Forex Trading Strategy
Integrated from future_features for robust strategy validation
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
import random


@dataclass
class MonteCarloResult:
    """Results from Monte Carlo simulation"""
    mean_return: float
    median_return: float
    std_return: float
    win_rate: float
    profit_factor: float
    max_drawdown: float
    sharpe_ratio: float
    final_equity_distribution: List[float]


class MonteCarloSimulator:
    """
    Monte Carlo Simulation for strategy validation
    Tests strategy resilience by randomizing trade sequences
    """
    
    def __init__(self, num_simulations: int = 1000):
        """
        Args:
            num_simulations: Number of simulations to run (1000-10000)
        """
        self.num_simulations = num_simulations
    
    def run_simulation(
        self,
        trades: List[Dict],
        initial_capital: float = 10000
    ) -> MonteCarloResult:
        """
        Run Monte Carlo simulation by randomizing trade order
        
        Args:
            trades: List of historical trades with 'pnl' field
            initial_capital: Starting capital
        
        Returns:
            MonteCarloResult with statistics
        """
        if len(trades) < 10:
            # Not enough trades for meaningful simulation
            return self._empty_result()
        
        # Extract trade PnLs
        trade_pnls = [t.get('pnl', 0) for t in trades]
        
        simulation_results = []
        
        for _ in range(self.num_simulations):
            # Randomize trade order
            shuffled_pnls = random.sample(trade_pnls, len(trade_pnls))
            
            # Calculate equity curve
            equity = initial_capital
            equity_curve = [equity]
            
            for pnl in shuffled_pnls:
                equity += pnl
                equity_curve.append(equity)
            
            # Calculate metrics for this simulation
            final_return = (equity - initial_capital) / initial_capital
            max_dd = self._calculate_max_drawdown(equity_curve)
            
            simulation_results.append({
                'final_return': final_return,
                'final_equity': equity,
                'max_drawdown': max_dd
            })
        
        # Aggregate results
        final_returns = [r['final_return'] for r in simulation_results]
        final_equities = [r['final_equity'] for r in simulation_results]
        max_dds = [r['max_drawdown'] for r in simulation_results]
        
        # Calculate statistics
        wins = sum(1 for t in trades if t.get('pnl', 0) > 0)
        losses = sum(1 for t in trades if t.get('pnl', 0) <= 0)
        win_rate = wins / len(trades) if trades else 0
        
        gross_profit = sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) > 0)
        gross_loss = abs(sum(t.get('pnl', 0) for t in trades if t.get('pnl', 0) < 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0
        
        # Sharpe ratio approximation
        returns_std = np.std(final_returns) if final_returns else 0
        mean_return = np.mean(final_returns) if final_returns else 0
        sharpe = (mean_return / returns_std * np.sqrt(252)) if returns_std > 0 else 0
        
        return MonteCarloResult(
            mean_return=mean_return,
            median_return=np.median(final_returns) if final_returns else 0,
            std_return=returns_std,
            win_rate=win_rate,
            profit_factor=profit_factor,
            max_drawdown=np.mean(max_dds) if max_dds else 0,
            sharpe_ratio=sharpe,
            final_equity_distribution=final_equities
        )
    
    def _calculate_max_drawdown(self, equity_curve: List[float]) -> float:
        """Calculate maximum drawdown from equity curve"""
        if not equity_curve:
            return 0.0
        
        peak = equity_curve[0]
        max_dd = 0.0
        
        for equity in equity_curve:
            if equity > peak:
                peak = equity
            dd = (peak - equity) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)
        
        return max_dd
    
    def _empty_result(self) -> MonteCarloResult:
        """Return empty result for insufficient data"""
        return MonteCarloResult(
            mean_return=0.0,
            median_return=0.0,
            std_return=0.0,
            win_rate=0.0,
            profit_factor=0.0,
            max_drawdown=0.0,
            sharpe_ratio=0.0,
            final_equity_distribution=[]
        )
    
    def print_results(self, result: MonteCarloResult):
        """Print Monte Carlo results"""
        print("\n" + "=" * 80)
        print("MONTE CARLO SIMULATION RESULTS")
        print("=" * 80)
        print(f"Simulations: {self.num_simulations:,}")
        print(f"\nMean Return: {result.mean_return*100:.2f}%")
        print(f"Median Return: {result.median_return*100:.2f}%")
        print(f"Std Deviation: {result.std_return*100:.2f}%")
        print(f"Win Rate: {result.win_rate*100:.1f}%")
        print(f"Profit Factor: {result.profit_factor:.2f}")
        print(f"Avg Max Drawdown: {result.max_drawdown*100:.1f}%")
        print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
        
        # Percentiles
        if result.final_equity_distribution:
            p5 = np.percentile(result.final_equity_distribution, 5)
            p95 = np.percentile(result.final_equity_distribution, 95)
            print(f"\n5th Percentile (worst 5%): ${p5:,.2f}")
            print(f"95th Percentile (best 5%): ${p95:,.2f}")
        
        # Assessment
        print("\n" + "=" * 80)
        if result.mean_return > 0.15 and result.max_drawdown < 0.20:
            print("✓ Strategy shows ROBUST performance across simulations")
        elif result.mean_return > 0.08:
            print("~ Strategy shows MODERATE robustness")
        else:
            print("✗ Strategy may NOT be robust - review carefully")


class RobustnessValidator:
    """
    Comprehensive robustness testing for forex strategies
    """
    
    def __init__(self):
        self.mc_simulator = MonteCarloSimulator(num_simulations=1000)
    
    def stress_test(
        self,
        trades: List[Dict],
        initial_capital: float = 10000
    ) -> Dict:
        """
        Stress test by applying worst-case scenarios
        
        Args:
            trades: List of historical trades
            initial_capital: Starting capital
        
        Returns:
            Dict with stress test results
        """
        if len(trades) < 10:
            return {'status': 'insufficient_data'}
        
        trade_pnls = [t.get('pnl', 0) for t in trades]
        
        # Scenario 1: All losses first, then wins
        losses = sorted([p for p in trade_pnls if p < 0])
        wins = sorted([p for p in trade_pnls if p >= 0], reverse=True)
        worst_case_sequence = losses + wins
        
        equity = initial_capital
        min_equity = equity
        for pnl in worst_case_sequence:
            equity += pnl
            min_equity = min(min_equity, equity)
        
        max_dd_worst = (initial_capital - min_equity) / initial_capital if initial_capital > 0 else 0
        final_worst = equity
        
        # Scenario 2: Alternating wins and losses (choppy)
        alternating = []
        for i in range(max(len(wins), len(losses))):
            if i < len(losses):
                alternating.append(losses[i])
            if i < len(wins):
                alternating.append(wins[i])
        
        equity = initial_capital
        min_equity_chop = equity
        for pnl in alternating:
            equity += pnl
            min_equity_chop = min(min_equity_chop, equity)
        
        max_dd_chop = (initial_capital - min_equity_chop) / initial_capital if initial_capital > 0 else 0
        
        return {
            'worst_case_drawdown': max_dd_worst,
            'worst_case_final_equity': final_worst,
            'choppy_market_drawdown': max_dd_chop,
            'min_equity': min_equity,
            'survived': min_equity > initial_capital * 0.5  # Didn't blow up 50%
        }
    
    def run_comprehensive_validation(
        self,
        trades: List[Dict],
        initial_capital: float = 10000
    ) -> Dict:
        """
        Run comprehensive validation suite
        
        Args:
            trades: List of historical trades
            initial_capital: Starting capital
        
        Returns:
            Complete validation results
        """
        print("\n" + "=" * 80)
        print("COMPREHENSIVE ROBUSTNESS VALIDATION")
        print("=" * 80)
        
        # Monte Carlo simulation
        print("\n1. Running Monte Carlo Simulation...")
        mc_result = self.mc_simulator.run_simulation(trades, initial_capital)
        self.mc_simulator.print_results(mc_result)
        
        # Stress testing
        print("\n2. Running Stress Tests...")
        stress_result = self.stress_test(trades, initial_capital)
        
        print("\n" + "=" * 80)
        print("STRESS TEST RESULTS")
        print("=" * 80)
        print(f"Worst Case Drawdown: {stress_result['worst_case_drawdown']*100:.1f}%")
        print(f"Choppy Market Drawdown: {stress_result['choppy_market_drawdown']*100:.1f}%")
        print(f"Min Equity: ${stress_result['min_equity']:,.2f}")
        print(f"Survived: {'✓ YES' if stress_result['survived'] else '✗ NO - Would blow up'}")
        
        # Final assessment
        assessment = self._generate_final_assessment({
            'monte_carlo': mc_result,
            'stress_test': stress_result
        })
        
        print("\n" + "=" * 80)
        print("FINAL ASSESSMENT")
        print("=" * 80)
        print(f"Overall Score: {assessment['score']}/10")
        print(f"Recommendation: {assessment['recommendation']}")
        print(f"Status: {assessment['status']}")
        
        return {
            'monte_carlo': mc_result,
            'stress_test': stress_result,
            'assessment': assessment
        }
    
    def _generate_final_assessment(self, results: Dict) -> Dict:
        """Generate final go/no-go assessment"""
        mc = results['monte_carlo']
        stress = results['stress_test']
        
        score = 0
        
        # Monte Carlo scoring (0-6 points)
        if mc.mean_return > 0.15:
            score += 2
        elif mc.mean_return > 0.08:
            score += 1
        
        if mc.win_rate > 0.55:
            score += 2
        elif mc.win_rate > 0.50:
            score += 1
        
        if mc.profit_factor > 1.8:
            score += 2
        elif mc.profit_factor > 1.5:
            score += 1
        
        # Stress test scoring (0-4 points)
        if stress['worst_case_drawdown'] < 0.25:
            score += 2
        elif stress['worst_case_drawdown'] < 0.35:
            score += 1
        
        if stress['survived']:
            score += 2
        
        # Generate recommendation
        if score >= 8:
            status = "EXCELLENT - Ready for live trading"
            recommendation = "Strategy is robust. Start with small position sizes."
        elif score >= 6:
            status = "GOOD - Consider live trading with caution"
            recommendation = "Strategy shows promise. Test on demo for 30 days first."
        elif score >= 4:
            status = "MODERATE - More testing needed"
            recommendation = "Strategy needs improvement. Continue optimizing."
        else:
            status = "POOR - Do not trade live"
            recommendation = "Strategy is not robust enough. Major revisions needed."
        
        return {
            'score': score,
            'status': status,
            'recommendation': recommendation
        }
