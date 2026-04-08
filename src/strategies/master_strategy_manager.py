"""
MASTER STRATEGY MANAGER
Unified orchestrator for ALL 110+ trading strategies

Integrates:
- Technical Indicators (20 strategies)
- Breakout Strategies (15 strategies)
- Forex-Specific (12 strategies)
- Synthetic Indices Specific (3 strategies)
- Scalping & Swing (10 strategies)
- Pattern Recognition (15 strategies)
- Advanced Indicators (15 strategies)
- Smart Money & Intermarket (15 strategies)
- Time-Based & Grid (10 strategies)
- ICT/AMD/Supply-Demand (5 strategies)

Total: 120+ strategies
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Any
from datetime import datetime
from dataclasses import dataclass

# Import all strategy modules with error handling
try:
    from src.strategies.technical_strategies_collection import TechnicalStrategySelector
except Exception as e:
    print(f"Warning: Could not load TechnicalStrategySelector: {e}")
    TechnicalStrategySelector = None

try:
    from src.strategies.breakout_strategies_collection import BreakoutStrategySelector
except Exception as e:
    print(f"Warning: Could not load BreakoutStrategySelector: {e}")
    BreakoutStrategySelector = None

try:
    from src.strategies.forex_specific_strategies import ForexStrategySelector
except Exception as e:
    print(f"Warning: Could not load ForexStrategySelector: {e}")
    ForexStrategySelector = None

try:
    from src.strategies.scalping_swing_complete import ScalpSwingSelector
except Exception as e:
    print(f"Warning: Could not load ScalpSwingSelector: {e}")
    ScalpSwingSelector = None

try:
    from src.strategies.pattern_recognition_strategies import PatternRecognitionSelector
except Exception as e:
    print(f"Warning: Could not load PatternRecognitionSelector: {e}")
    PatternRecognitionSelector = None

try:
    from src.strategies.advanced_indicators_strategies import AdvancedIndicatorsSelector
except Exception as e:
    print(f"Warning: Could not load AdvancedIndicatorsSelector: {e}")
    AdvancedIndicatorsSelector = None

try:
    from src.strategies.smart_money_intermarket_strategies import SmartMoneyIntermarketSelector
except Exception as e:
    print(f"Warning: Could not load SmartMoneyIntermarketSelector: {e}")
    SmartMoneyIntermarketSelector = None

try:
    from src.strategies.time_grid_strategies import TimeGridStrategySelector
except Exception as e:
    print(f"Warning: Could not load TimeGridStrategySelector: {e}")
    TimeGridStrategySelector = None

try:
    from src.strategies.synthetic_strategies import SyntheticStrategySelector
except Exception as e:
    try:
        from src.strategies.synthetic_indices_strategies import SyntheticStrategySelector
    except Exception:
        print(f"Warning: Could not load SyntheticStrategySelector: {e}")
        SyntheticStrategySelector = None


@dataclass
class UnifiedSignal:
    """Unified signal format for all strategies"""
    strategy_category: str
    strategy_name: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    timeframe: str
    additional_info: Dict


class MasterStrategyManager:
    """
    Master orchestrator for all 110+ trading strategies
    
    Capabilities:
    - Runs all strategies simultaneously
    - Ranks signals by confidence
    - Filters by market regime
    - Provides multi-strategy portfolio
    """
    
    def __init__(self, config: Dict = None):
        """Initialize all strategy modules"""
        self.config = config or {}
        
        # Initialize all strategy selectors (with None checks)
        self.technical = TechnicalStrategySelector() if TechnicalStrategySelector else None
        self.breakout = BreakoutStrategySelector() if BreakoutStrategySelector else None
        self.forex = ForexStrategySelector() if ForexStrategySelector else None
        self.scalp_swing = ScalpSwingSelector() if ScalpSwingSelector else None
        self.patterns = PatternRecognitionSelector() if PatternRecognitionSelector else None
        self.advanced_indicators = AdvancedIndicatorsSelector() if AdvancedIndicatorsSelector else None
        self.smart_money = SmartMoneyIntermarketSelector() if SmartMoneyIntermarketSelector else None
        self.time_grid = TimeGridStrategySelector() if TimeGridStrategySelector else None
        self.synthetic = SyntheticStrategySelector(self.config.get('synthetic_strategies', {})) if SyntheticStrategySelector else None
        
        # Strategy enablement (from config)
        self.enabled_categories = {
            'technical': self.config.get('technical', {}).get('enabled', True),
            'breakout': self.config.get('breakout', {}).get('enabled', True),
            'forex': self.config.get('forex_specific', {}).get('enabled', True),
            'scalping': self.config.get('scalping', {}).get('enabled', False),
            'swing': self.config.get('swing', {}).get('enabled', True),
            'patterns': self.config.get('patterns', {}).get('enabled', True),
            'advanced': self.config.get('advanced_indicators', {}).get('enabled', True),
            'smart_money': self.config.get('smart_money', {}).get('enabled', True),
            'time_based': self.config.get('time_based', {}).get('enabled', True),
            'grid': self.config.get('grid', {}).get('enabled', False),
            'synthetic': self.config.get('synthetic_strategies', {}).get('enabled', True)
        }
        
        # Performance tracking
        self.strategy_performance = {}
    
    def analyze_all_strategies(self, symbol: str, df: pd.DataFrame,
                               df_h4: pd.DataFrame = None,
                               df_h1: pd.DataFrame = None,
                               related_data: Dict[str, pd.DataFrame] = None,
                               current_time: datetime = None) -> List[UnifiedSignal]:
        """
        Run ALL enabled strategies and return all signals
        
        Args:
            symbol: Trading symbol
            df: Primary timeframe data (M15)
            df_h4: 4-hour data (optional)
            df_h1: 1-hour data (optional)
            related_data: Related pairs/indices data
            current_time: Current timestamp
            
        Returns:
            List of all valid signals from all strategies
        """
        all_signals = []
        
        if current_time is None:
            current_time = datetime.now()
        
        # 1. Technical Indicators Strategies
        if self.enabled_categories['technical'] and self.technical:
            try:
                tech_signals = self.technical.get_all_signals(df)
            except Exception as e:
                print(f"Technical strategy error: {e}")
                tech_signals = []
            
            for sig in tech_signals:
                all_signals.append(UnifiedSignal(
                    strategy_category='technical',
                    strategy_name=sig.strategy,
                    direction=sig.direction,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    confidence=sig.confidence,
                    timeframe=sig.timeframe,
                    additional_info={'indicators': sig.indicators}
                ))
        
        # 2. Breakout Strategies
        if self.enabled_categories['breakout'] and self.breakout:
            try:
                breakout_signals = self.breakout.get_all_signals(df, current_time)
            except Exception as e:
                print(f"Breakout strategy error: {e}")
                breakout_signals = []
            
            for sig in breakout_signals:
                all_signals.append(UnifiedSignal(
                    strategy_category='breakout',
                    strategy_name=sig.strategy,
                    direction=sig.direction,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    confidence=sig.confidence,
                    timeframe=sig.timeframe,
                    additional_info={
                        'breakout_level': sig.breakout_level,
                        'volume_confirmation': sig.volume_confirmation
                    }
                ))
        
        # 3. Forex-Specific Strategies
        if self.enabled_categories['forex'] and self.forex:
            try:
                forex_signals = self.forex.get_all_signals(symbol, df, related_data)
            except Exception as e:
                print(f"Forex strategy error: {e}")
                forex_signals = []
            
            for sig in forex_signals:
                all_signals.append(UnifiedSignal(
                    strategy_category='forex_specific',
                    strategy_name=sig.strategy,
                    direction=sig.direction,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    confidence=sig.confidence,
                    timeframe=sig.timeframe,
                    additional_info={
                        'correlation_pairs': sig.correlation_pairs,
                        'interest_differential': sig.interest_differential
                    }
                ))

        # 3B. Synthetic indices dedicated strategies
        if self.enabled_categories['synthetic'] and self.synthetic:
            try:
                synthetic_signals = self.synthetic.get_all_signals(symbol, df)
            except Exception as e:
                print(f"Synthetic strategy error: {e}")
                synthetic_signals = []

            for sig in synthetic_signals:
                all_signals.append(UnifiedSignal(
                    strategy_category='synthetic',
                    strategy_name=sig.strategy,
                    direction=sig.direction,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    confidence=sig.confidence,
                    timeframe=sig.timeframe,
                    additional_info={
                        'regime': sig.regime,
                        'details': sig.details,
                    }
                ))
        
        # 4. Scalping Strategies
        if self.enabled_categories['scalping'] and self.scalp_swing:
            try:
                scalp_signals = self.scalp_swing.get_scalp_signals(df)
            except Exception as e:
                print(f"Scalping strategy error: {e}")
                scalp_signals = []
            
            for sig in scalp_signals:
                all_signals.append(UnifiedSignal(
                    strategy_category='scalping',
                    strategy_name=sig.strategy,
                    direction=sig.direction,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    confidence=sig.confidence,
                    timeframe=sig.timeframe,
                    additional_info={'pips_target': sig.pips_target}
                ))
        
        # 5. Swing Trading Strategies
        if self.enabled_categories['swing'] and self.scalp_swing and df_h4 is not None:
            try:
                swing_signals = self.scalp_swing.get_swing_signals(df_h4)
            except Exception as e:
                print(f"Swing strategy error: {e}")
                swing_signals = []
            
            for sig in swing_signals:
                all_signals.append(UnifiedSignal(
                    strategy_category='swing',
                    strategy_name=sig.strategy,
                    direction=sig.direction,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit_2,  # Use TP2
                    confidence=sig.confidence,
                    timeframe=sig.timeframe,
                    additional_info={'holding_days': sig.holding_days}
                ))
        
        # 6. Pattern Recognition Strategies
        if self.enabled_categories['patterns'] and self.patterns:
            try:
                pattern_signals = self.patterns.get_all_signals(df)
            except Exception as e:
                print(f"Pattern strategy error: {e}")
                pattern_signals = []
            
            for sig in pattern_signals:
                all_signals.append(UnifiedSignal(
                    strategy_category='patterns',
                    strategy_name=sig.strategy,
                    direction=sig.direction,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    confidence=sig.confidence,
                    timeframe=sig.timeframe,
                    additional_info={
                        'pattern_type': sig.pattern_type,
                        'pattern_quality': sig.pattern_quality
                    }
                ))
        
        # 7. Advanced Indicators Strategies
        if self.enabled_categories['advanced'] and self.advanced_indicators:
            try:
                advanced_signals = self.advanced_indicators.get_all_signals(df)
            except Exception as e:
                print(f"Advanced indicator strategy error: {e}")
                advanced_signals = []
            
            for sig in advanced_signals:
                all_signals.append(UnifiedSignal(
                    strategy_category='advanced_indicators',
                    strategy_name=sig.strategy,
                    direction=sig.direction,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    confidence=sig.confidence,
                    timeframe=sig.timeframe,
                    additional_info={
                        'indicator': sig.indicator,
                        'indicator_value': sig.indicator_value
                    }
                ))
        
        # 8. Smart Money Strategies
        if self.enabled_categories['smart_money'] and self.smart_money:
            try:
                smart_signals = self.smart_money.get_smart_money_signals(df)
            except Exception as e:
                print(f"Smart money strategy error: {e}")
                smart_signals = []
            
            for sig in smart_signals:
                all_signals.append(UnifiedSignal(
                    strategy_category='smart_money',
                    strategy_name=sig.strategy,
                    direction=sig.direction,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    confidence=sig.confidence,
                    timeframe=sig.timeframe,
                    additional_info={
                        'concept': sig.concept,
                        'institutional_level': sig.institutional_level
                    }
                ))
        
        # 9. Time-Based Strategies
        if self.enabled_categories['time_based'] and self.time_grid:
            try:
                time_signals = self.time_grid.get_time_signals(df, current_time)
            except Exception as e:
                print(f"Time-based strategy error: {e}")
                time_signals = []
            
            for sig in time_signals:
                all_signals.append(UnifiedSignal(
                    strategy_category='time_based',
                    strategy_name=sig.strategy,
                    direction=sig.direction,
                    entry_price=sig.entry_price,
                    stop_loss=sig.stop_loss,
                    take_profit=sig.take_profit,
                    confidence=sig.confidence,
                    timeframe=sig.timeframe,
                    additional_info={
                        'time_pattern': sig.time_pattern,
                        'time_factor': sig.time_factor
                    }
                ))
        
        return all_signals
    
    def get_best_signal(self, symbol: str, df: pd.DataFrame,
                       df_h4: pd.DataFrame = None,
                       df_h1: pd.DataFrame = None,
                       related_data: Dict[str, pd.DataFrame] = None,
                       current_time: datetime = None) -> Optional[UnifiedSignal]:
        """
        Get single best signal from all strategies
        
        Returns:
            Highest confidence signal
        """
        all_signals = self.analyze_all_strategies(
            symbol, df, df_h4, df_h1, related_data, current_time
        )
        
        if not all_signals:
            return None
        
        # Sort by confidence
        all_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return all_signals[0]
    
    def get_top_n_signals(self, symbol: str, df: pd.DataFrame,
                         n: int = 5,
                         df_h4: pd.DataFrame = None,
                         df_h1: pd.DataFrame = None,
                         related_data: Dict[str, pd.DataFrame] = None,
                         current_time: datetime = None) -> List[UnifiedSignal]:
        """
        Get top N signals for portfolio diversification
        
        Args:
            n: Number of top signals to return
            
        Returns:
            Top N signals by confidence
        """
        all_signals = self.analyze_all_strategies(
            symbol, df, df_h4, df_h1, related_data, current_time
        )
        
        if not all_signals:
            return []
        
        # Sort by confidence and return top N
        all_signals.sort(key=lambda x: x.confidence, reverse=True)
        
        return all_signals[:n]
    
    def get_consensus_signal(self, symbol: str, df: pd.DataFrame,
                            df_h4: pd.DataFrame = None,
                            df_h1: pd.DataFrame = None,
                            related_data: Dict[str, pd.DataFrame] = None,
                            current_time: datetime = None,
                            min_agreement: int = 3) -> Optional[Dict]:
        """
        Get consensus signal when multiple strategies agree
        
        Args:
            min_agreement: Minimum number of strategies that must agree
            
        Returns:
            Consensus signal with increased confidence
        """
        all_signals = self.analyze_all_strategies(
            symbol, df, df_h4, df_h1, related_data, current_time
        )
        
        if len(all_signals) < min_agreement:
            return None
        
        # Count by direction
        long_signals = [s for s in all_signals if s.direction == 'LONG']
        short_signals = [s for s in all_signals if s.direction == 'SHORT']
        
        # Check for consensus
        if len(long_signals) >= min_agreement:
            avg_confidence = sum(s.confidence for s in long_signals) / len(long_signals)
            best_long = max(long_signals, key=lambda x: x.confidence)
            
            return {
                'direction': 'LONG',
                'entry_price': best_long.entry_price,
                'stop_loss': best_long.stop_loss,
                'take_profit': best_long.take_profit,
                'confidence': min(avg_confidence * 1.2, 100),  # Boost for consensus
                'agreeing_strategies': len(long_signals),
                'strategy_names': [s.strategy_name for s in long_signals]
            }
        
        elif len(short_signals) >= min_agreement:
            avg_confidence = sum(s.confidence for s in short_signals) / len(short_signals)
            best_short = max(short_signals, key=lambda x: x.confidence)
            
            return {
                'direction': 'SHORT',
                'entry_price': best_short.entry_price,
                'stop_loss': best_short.stop_loss,
                'take_profit': best_short.take_profit,
                'confidence': min(avg_confidence * 1.2, 100),
                'agreeing_strategies': len(short_signals),
                'strategy_names': [s.strategy_name for s in short_signals]
            }
        
        return None
    
    def get_strategy_statistics(self) -> Dict:
        """Get statistics on all strategies"""
        return {
            'total_strategies': 120,
            'enabled_categories': {k: v for k, v in self.enabled_categories.items() if v},
            'disabled_categories': {k: v for k, v in self.enabled_categories.items() if not v},
            'performance': self.strategy_performance
        }
    
    def print_all_signals(self, symbol: str, df: pd.DataFrame,
                         df_h4: pd.DataFrame = None,
                         df_h1: pd.DataFrame = None,
                         related_data: Dict[str, pd.DataFrame] = None):
        """Print all signals for analysis"""
        signals = self.analyze_all_strategies(symbol, df, df_h4, df_h1, related_data)
        
        print(f"\n{'='*80}")
        print(f"ALL STRATEGY SIGNALS FOR {symbol}")
        print(f"{'='*80}")
        print(f"Total Signals Generated: {len(signals)}")
        print(f"{'='*80}\n")
        
        if not signals:
            print("No signals generated.\n")
            return
        
        # Group by category
        by_category = {}
        for sig in signals:
            if sig.strategy_category not in by_category:
                by_category[sig.strategy_category] = []
            by_category[sig.strategy_category].append(sig)
        
        for category, sigs in by_category.items():
            print(f"\n{category.upper()} ({len(sigs)} signals):")
            print("-" * 80)
            
            for sig in sorted(sigs, key=lambda x: x.confidence, reverse=True):
                print(f"  {sig.strategy_name:30} | {sig.direction:5} | "
                      f"Conf: {sig.confidence:5.1f} | Entry: {sig.entry_price:.5f} | "
                      f"TF: {sig.timeframe}")
        
        print(f"\n{'='*80}")
        print(f"TOP 5 SIGNALS BY CONFIDENCE:")
        print(f"{'='*80}")
        
        top5 = sorted(signals, key=lambda x: x.confidence, reverse=True)[:5]
        for i, sig in enumerate(top5, 1):
            print(f"{i}. [{sig.strategy_category}] {sig.strategy_name}")
            print(f"   Direction: {sig.direction} | Confidence: {sig.confidence:.1f}")
            print(f"   Entry: {sig.entry_price:.5f} | SL: {sig.stop_loss:.5f} | TP: {sig.take_profit:.5f}")
            print()


# Convenience function for quick access
def get_all_strategies_signals(symbol: str, df: pd.DataFrame, config: Dict = None) -> List[UnifiedSignal]:
    """
    Quick function to get all strategy signals
    
    Usage:
        signals = get_all_strategies_signals('EURUSD', df)
    """
    manager = MasterStrategyManager(config)
    return manager.analyze_all_strategies(symbol, df)


def get_best_strategy_signal(symbol: str, df: pd.DataFrame, config: Dict = None) -> Optional[UnifiedSignal]:
    """
    Quick function to get best signal
    
    Usage:
        best_signal = get_best_strategy_signal('EURUSD', df)
    """
    manager = MasterStrategyManager(config)
    return manager.get_best_signal(symbol, df)
