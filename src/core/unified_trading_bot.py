"""
UNIFIED PROFESSIONAL TRADING BOT - Complete Integration
Combines ICT (primary) + Traditional Strategies + AMD Cycle Detection

Strategy Priority:
1. ICT 2022 Mentorship (Primary - XAUUSD)
2. Power of 3 / AMD Cycle (Gold/FX during sessions)
3. Trend Following (Backup strategy)
4. Mean Reversion (Range-bound markets)

All strategies include:
- Multi-timeframe analysis
- Killzone session filtering
- Comprehensive risk management
- AMD cycle alignment
"""

import MetaTrader5 as mt5
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import time
import yaml

# ICT Modules (Primary Strategy)
from src.ict import (
    ICT2022Strategy,
    PowerOf3Strategy,
    ICTKillzoneFilter,
    ICTLiquidityDetector,
    ICTMarketStructure,
    ICTFVGDetector,
    ICTTradeSignal
)

# Traditional Analysis
from src.analysis.advanced_indicators import AdvancedIndicators
from src.analysis.market_regime import MarketRegimeDetector
from src.analysis.order_blocks import OrderBlockDetector

# Execution & Risk
from src.execution.adaptive_position_sizer import AdaptivePositionSizer
from src.execution.trade_manager import TradeManager, TrailingStopConfig
from src.execution.dynamic_exit_manager import DynamicExitManager
from src.execution.position_scaling import PositionScaling
from src.risk.portfolio_risk import PortfolioRiskManager
from src.monitoring.psychology_monitor import PsychologyMonitor
from src.data.news_filter import NewsFilter, EconomicCalendar

# Utilities
from src.utils.logger import setup_logger
from src.analysis.session_analyzer import SessionAnalyzer


class UnifiedTradingBot:
    """
    Unified Trading Bot - Complete Strategy Integration
    
    Strategy Selection Logic:
    1. Check Killzone (mandatory)
    2. Detect market phase (Accumulation/Manipulation/Distribution)
    3. Select best strategy for current conditions
    4. Execute with comprehensive risk management
    """
    
    def __init__(self, config_path: str = 'config/config.yaml'):
        """Initialize unified trading bot with all strategies"""
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.logger = setup_logger('UnifiedTradingBot', 'data/logs')
        self.logger.info("Initializing Unified Trading Bot - All Strategies")
        
        # Strategy Selection
        self.primary_strategy = self.config.get('primary_strategy', 'ict_2022')
        self.enable_amd_detection = self.config.get('ict', {}).get('enable_amd', True)
        self.enable_fallback_strategies = self.config.get('enable_fallback', True)
        
        # ICT Components (Primary)
        self.ict_strategy = ICT2022Strategy(symbol='XAUUSD')
        self.power_of_3 = PowerOf3Strategy()
        # Enable flexible mode for 24/7 trading (can be disabled in config for strict ICT)
        flexible_trading = self.config.get('ict', {}).get('flexible_mode', True)
        self.killzone_filter = ICTKillzoneFilter(flexible_mode=flexible_trading)
        self.liquidity_detector = ICTLiquidityDetector()
        self.structure_detector = ICTMarketStructure()
        self.fvg_detector = ICTFVGDetector()
        
        # Traditional Components (Fallback)
        self.indicators = AdvancedIndicators(self.config)
        self.regime_detector = MarketRegimeDetector(self.config)
        self.order_block_detector = OrderBlockDetector()
        
        # Supply/Demand Strategy
        from src.strategies.supply_demand_strategy import SupplyDemandStrategy
        self.supply_demand_strategy = SupplyDemandStrategy(
            min_zone_strength=self.config.get('supply_demand', {}).get('min_zone_strength', 5.0),
            require_htf_alignment=self.config.get('supply_demand', {}).get('require_htf_alignment', True),
            min_risk_reward=self.config.get('supply_demand', {}).get('min_risk_reward', 2.0),
            max_zone_tests=self.config.get('supply_demand', {}).get('max_zone_tests', 3)
        )
        
        # Master Strategy Manager (ALL 112+ strategies)
        from src.strategies.master_strategy_manager import MasterStrategyManager
        self.master_strategies = MasterStrategyManager(self.config)
        self.logger.info("[OK] Master Strategy Manager initialized (112+ strategies loaded)")
        
        # Risk Management
        account_info = mt5.account_info()
        self.account_balance = account_info.balance if account_info else 10000.0
        max_portfolio_risk = self.config.get('risk', {}).get('max_portfolio_risk_percent', 5.0)
        self.portfolio_risk = PortfolioRiskManager(self.account_balance, max_portfolio_risk)
        self.adaptive_sizer = AdaptivePositionSizer(self.config.get('risk', {}))
        self.psychology_monitor = PsychologyMonitor(trading_plan={})
        
        # Trade Management
        trailing_config = TrailingStopConfig(
            activation_ratio=1.0,
            trail_distance_atr_multiplier=0.5,
            trail_step_pips=5.0,
            breakeven_ratio=0.5,
            partial_exit_enabled=True
        )
        self.trade_manager = TradeManager(trailing_config)
        self.dynamic_exit_manager = DynamicExitManager()
        self.position_scaling = PositionScaling()
        
        # News Filter
        economic_calendar = EconomicCalendar()
        self.news_filter = NewsFilter(economic_calendar)
        
        # Session Trading Manager
        self.session_manager = SessionAnalyzer()
        
        # Trading State
        self.active_trades = {}
        self.daily_stats = {
            'trades': 0,
            'wins': 0,
            'losses': 0,
            'pnl': 0.0,
            'max_drawdown': 0.0
        }
        
        # AMD Cycle State
        self.amd_phase = 'UNKNOWN'  # ACCUMULATION | MANIPULATION | DISTRIBUTION
        self.asian_range_analyzed = False
        
        self.logger.info("All strategies initialized successfully")

    def _normalize_direction(self, direction: str) -> str:
        """Normalize direction aliases to LONG/SHORT for internal consistency."""
        d = (direction or '').upper()
        if d in ('LONG', 'BUY'):
            return 'LONG'
        if d in ('SHORT', 'SELL'):
            return 'SHORT'
        return ''
    
    def analyze_market_phase(self, df_asian: pd.DataFrame, 
                            df_current: pd.DataFrame) -> str:
        """
        Detect current AMD (Accumulation-Manipulation-Distribution) phase
        
        Args:
            df_asian: Asian session data for accumulation analysis
            df_current: Current session data
            
        Returns:
            'ACCUMULATION' | 'MANIPULATION' | 'DISTRIBUTION' | 'UNKNOWN'
        """
        if not self.enable_amd_detection:
            return 'UNKNOWN'
        
        current_time = datetime.now()
        current_kz = self.killzone_filter.get_current_killzone(current_time)
        
        # ACCUMULATION: Asian Session (7PM-2AM EST)
        if current_kz.name == 'Asian Session':
            # Analyze range formation
            asian_analysis = self.power_of_3.analyze_asian_session(df_asian)
            if asian_analysis['range_valid']:
                self.asian_range_analyzed = True
                return 'ACCUMULATION'
        
        # MANIPULATION: London Open (3-5AM EST) or early NY
        elif current_kz.name in ['London Open', 'NY AM Session']:
            if self.asian_range_analyzed:
                # Check for liquidity sweep (manipulation)
                manipulation = self.power_of_3.detect_manipulation(df_current)
                if manipulation:
                    self.logger.info(f"AMD: Manipulation detected - {manipulation}")
                    return 'MANIPULATION'
        
        # DISTRIBUTION: After manipulation confirmed
        if self.power_of_3.manipulation_detected:
            distribution_signal = self.power_of_3.get_distribution_signal(df_current)
            if distribution_signal:
                self.logger.info(f"AMD: Distribution phase - {distribution_signal}")
                return 'DISTRIBUTION'
        
        return 'UNKNOWN'
    
    def select_best_strategy(self, symbol: str, amd_phase: str,
                            market_regime: str) -> str:
        """
        Select optimal strategy based on market conditions
        
        Args:
            symbol: Trading symbol
            amd_phase: Current AMD phase
            market_regime: Market regime (trending/ranging)
            
        Returns:
            Strategy name to use
        """
        # During DISTRIBUTION phase, use ICT 2022
        if amd_phase == 'DISTRIBUTION':
            return 'ict_2022'
        
        # During MANIPULATION phase, wait or use Power of 3
        if amd_phase == 'MANIPULATION':
            return 'power_of_3'
        
        # Check killzone - ICT only during London/NY
        timing = self.killzone_filter.validate_trade_timing(symbol)
        if timing['allowed'] and timing['killzone_priority'] == 1:
            return 'ict_2022'
        
        # If AMD phase is UNKNOWN, use Master Strategies instead
        if amd_phase == 'UNKNOWN':
            self.logger.info("AMD phase UNKNOWN - using Master Strategy Manager")
            return 'master_all'
        
        # Check if Master Strategy Manager is enabled (runs ALL 112+ strategies)
        if self.config.get('master_strategies', {}).get('enabled', True):  # Default TRUE
            return 'master_all'
        
        # Fallback strategies based on market regime
        if self.enable_fallback_strategies:
            # Try Supply/Demand first (works in all regimes)
            if self.config.get('supply_demand', {}).get('enabled', True):
                return 'supply_demand'
            
            if market_regime == 'STRONG_TREND':
                return 'trend_following'
            elif market_regime == 'RANGING':
                return 'mean_reversion'
        
        return 'wait'  # No suitable strategy
    
    def analyze_ict_2022(self, symbol: str) -> Optional[ICTTradeSignal]:
        """
        Primary ICT 2022 Mentorship Model analysis
        
        Returns:
            ICTTradeSignal or None
        """
        # Get multi-timeframe data
        df_h4 = self._get_ohlcv(symbol, mt5.TIMEFRAME_H4, 100)
        df_h1 = self._get_ohlcv(symbol, mt5.TIMEFRAME_H1, 100)
        df_m15 = self._get_ohlcv(symbol, mt5.TIMEFRAME_M15, 200)
        
        if df_h4 is None or df_h1 is None or df_m15 is None:
            return None
        
        # Run ICT analysis
        signal = self.ict_strategy.analyze(df_h4, df_h1, df_m15)
        
        if signal and signal.confluence_score >= 70:
            self.logger.info(f"ICT Signal: {signal.direction} @ {signal.entry_price:.2f}")
            self.logger.info(f"Confluence: {signal.confluence_score:.1f}/100")
            return signal
        
        return None
    
    def analyze_power_of_3(self, symbol: str) -> Optional[Dict]:
        """
        Power of 3 (AMD) strategy analysis
        
        Returns:
            Trade signal dict or None
        """
        # Get session data
        df_m15 = self._get_ohlcv(symbol, mt5.TIMEFRAME_M15, 200)
        if df_m15 is None:
            return None
        
        # Check for distribution signal
        distribution_signal = self.power_of_3.get_distribution_signal(df_m15)
        
        if distribution_signal:
            normalized_direction = self._normalize_direction(distribution_signal)
            if not normalized_direction:
                self.logger.warning(f"Invalid Power of 3 direction for {symbol}: {distribution_signal}")
                return None

            # Calculate entry based on FVG
            self.fvg_detector.detect_fvgs(df_m15)
            current_price = df_m15.iloc[-1]['close']
            
            if normalized_direction == 'LONG':
                entry_fvg = self.fvg_detector.get_nearest_fvg(current_price, 'bullish')
            else:
                entry_fvg = self.fvg_detector.get_nearest_fvg(current_price, 'bearish')
            
            if entry_fvg:
                ote_levels = self.fvg_detector.get_ote_levels(entry_fvg)
                
                return {
                    'strategy': 'power_of_3',
                    'direction': normalized_direction,
                    'entry': ote_levels['ote_low'],
                    'stop_loss': self._calculate_amd_stop(df_m15, normalized_direction),
                    'take_profit': self._calculate_amd_target(df_m15, normalized_direction),
                    'confidence': 75  # AMD has high probability
                }
        
        return None
    
    def analyze_trend_following(self, symbol: str) -> Optional[Dict]:
        """
        Traditional trend following strategy (fallback)
        
        Uses:
        - EMA crossovers (9/21/50)
        - ADX for trend strength
        - MACD confirmation
        
        Returns:
            Trade signal dict or None
        """
        df = self._get_ohlcv(symbol, mt5.TIMEFRAME_H1, 100)
        if df is None:
            return None
        
        # Calculate EMAs
        ema_9 = df['close'].ewm(span=9, adjust=False).mean()
        ema_21 = df['close'].ewm(span=21, adjust=False).mean()
        ema_50 = df['close'].ewm(span=50, adjust=False).mean()
        
        # Calculate ADX
        adx = self._calculate_adx(df, 14)
        
        current_price = df.iloc[-1]['close']
        
        # Bullish trend: EMA 9 > 21 > 50, ADX > 25
        if (ema_9.iloc[-1] > ema_21.iloc[-1] > ema_50.iloc[-1] and 
            adx > 25):
            return {
                'strategy': 'trend_following',
                'direction': 'LONG',
                'entry': current_price,
                'stop_loss': ema_50.iloc[-1],
                'take_profit': current_price + (current_price - ema_50.iloc[-1]) * 2,
                'confidence': min(adx, 100)
            }
        
        # Bearish trend: EMA 9 < 21 < 50, ADX > 25
        elif (ema_9.iloc[-1] < ema_21.iloc[-1] < ema_50.iloc[-1] and 
              adx > 25):
            return {
                'strategy': 'trend_following',
                'direction': 'SHORT',
                'entry': current_price,
                'stop_loss': ema_50.iloc[-1],
                'take_profit': current_price - (ema_50.iloc[-1] - current_price) * 2,
                'confidence': min(adx, 100)
            }
        
        return None
    
    def analyze_mean_reversion(self, symbol: str) -> Optional[Dict]:
        """
        Mean reversion strategy for ranging markets
        
        Uses:
        - Bollinger Bands (20, 2)
        - RSI (14) extremes
        - Low ADX (<25)
        
        Returns:
            Trade signal dict or None
        """
        df = self._get_ohlcv(symbol, mt5.TIMEFRAME_M15, 100)
        if df is None:
            return None
        
        # Calculate Bollinger Bands
        bb_period = 20
        bb_std = 2
        sma = df['close'].rolling(bb_period).mean()
        std = df['close'].rolling(bb_period).std()
        upper_band = sma + (std * bb_std)
        lower_band = sma - (std * bb_std)
        
        # Calculate RSI
        rsi = self._calculate_rsi(df, 14)
        
        # Calculate ADX (should be low for ranging market)
        adx = self._calculate_adx(df, 14)
        
        current_price = df.iloc[-1]['close']
        
        # Only trade mean reversion in ranging markets
        if adx > 25:
            return None
        
        # Oversold - potential long
        if current_price < lower_band.iloc[-1] and rsi < 30:
            return {
                'strategy': 'mean_reversion',
                'direction': 'LONG',
                'entry': current_price,
                'stop_loss': lower_band.iloc[-1] - (std.iloc[-1] * 0.5),
                'take_profit': sma.iloc[-1],
                'confidence': 100 - rsi  # Lower RSI = higher confidence
            }
        
        # Overbought - potential short
        elif current_price > upper_band.iloc[-1] and rsi > 70:
            return {
                'strategy': 'mean_reversion',
                'direction': 'SHORT',
                'entry': current_price,
                'stop_loss': upper_band.iloc[-1] + (std.iloc[-1] * 0.5),
                'take_profit': sma.iloc[-1],
                'confidence': rsi - 50  # Higher RSI = higher confidence
            }
        
        return None
    
    def analyze_supply_demand(self, symbol: str) -> Optional[Dict]:
        """
        Supply & Demand zone strategy analysis
        
        Uses:
        - Drop-Base-Rally / Rally-Base-Drop patterns
        - Zone strength scoring (0-10)
        - Multi-timeframe validation
        - Rejection pattern confirmation
        
        Returns:
            Trade signal dict or None
        """
        # Get multi-timeframe data
        df_h4 = self._get_ohlcv(symbol, mt5.TIMEFRAME_H4, 100)
        df_h1 = self._get_ohlcv(symbol, mt5.TIMEFRAME_H1, 100)
        df_m15 = self._get_ohlcv(symbol, mt5.TIMEFRAME_M15, 200)
        
        if df_h4 is None or df_h1 is None or df_m15 is None:
            return None
        
        # Run Supply/Demand analysis
        sd_signal = self.supply_demand_strategy.analyze(df_h4, df_h1, df_m15)
        
        if sd_signal:
            self.logger.info(f"S/D Signal: {sd_signal.direction} @ {sd_signal.entry_price:.2f}")
            self.logger.info(f"Zone: {sd_signal.zone.zone_type.upper()}, Strength: {sd_signal.zone.strength:.1f}/10")
            self.logger.info(f"Pattern: {sd_signal.pattern}, Confidence: {sd_signal.confidence:.1f}/100")
            
            return {
                'strategy': 'supply_demand',
                'direction': sd_signal.direction,
                'entry': sd_signal.entry_price,
                'stop_loss': sd_signal.stop_loss,
                'take_profit': sd_signal.take_profit_2,  # Use TP2 (2.5:1 R:R)
                'confidence': sd_signal.confidence,
                'zone_strength': sd_signal.zone.strength,
                'zone_quality': sd_signal.zone.get_quality_rating(),
                'pattern': sd_signal.pattern,
                'position_multiplier': sd_signal.position_size_multiplier
            }
        
        return None
    
    def analyze_all_strategies_master(self, symbol: str) -> Optional[Dict]:
        """
        Run ALL 112+ strategies using Master Strategy Manager
        Returns best signal from all strategies
        
        Returns:
            Trade signal dict or None
        """
        # Get multi-timeframe data
        df_m15 = self._get_ohlcv(symbol, mt5.TIMEFRAME_M15, 200)
        df_h1 = self._get_ohlcv(symbol, mt5.TIMEFRAME_H1, 100)
        df_h4 = self._get_ohlcv(symbol, mt5.TIMEFRAME_H4, 100)
        
        if df_m15 is None:
            return None
        
        # Run all strategies
        best_signal = self.master_strategies.get_best_signal(
            symbol=symbol,
            df=df_m15,
            df_h1=df_h1,
            df_h4=df_h4,
            related_data=None  # Can add DXY, correlated pairs later
        )
        
        if best_signal:
            normalized_direction = self._normalize_direction(best_signal.direction)
            if not normalized_direction:
                self.logger.warning(
                    f"Master Strategy returned invalid direction for {symbol}: {best_signal.direction}"
                )
                return None

            self.logger.info(f"[SIGNAL] Master Strategy: {best_signal.strategy_name}")
            self.logger.info(f"   Category: {best_signal.strategy_category}")
            self.logger.info(f"   Direction: {normalized_direction}")
            self.logger.info(f"   Confidence: {best_signal.confidence:.1f}/100")
            
            return {
                'strategy': f'{best_signal.strategy_category}_{best_signal.strategy_name}',
                'direction': normalized_direction,
                'entry': best_signal.entry_price,
                'stop_loss': best_signal.stop_loss,
                'take_profit': best_signal.take_profit,
                'confidence': best_signal.confidence,
                'timeframe': best_signal.timeframe,
                'additional_info': best_signal.additional_info
            }
        
        return None
    
    def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Main analysis orchestrator - selects and runs best strategy
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Trade signal dict or None
        """
        # 1. Pre-trade filters
        if not self._pre_trade_checks(symbol):
            return None
        
        # 2. Detect AMD phase
        df_asian = self._get_session_data(symbol, 'asian')
        df_current = self._get_ohlcv(symbol, mt5.TIMEFRAME_M15, 100)
        
        self.amd_phase = self.analyze_market_phase(df_asian, df_current)
        self.logger.info(f"AMD Phase: {self.amd_phase}")
        
        # 3. Detect market regime
        df_h1 = self._get_ohlcv(symbol, mt5.TIMEFRAME_H1, 100)
        market_regime = self._detect_market_regime(df_h1)
        
        # 4. Select strategy
        selected_strategy = self.select_best_strategy(symbol, self.amd_phase, market_regime)
        self.logger.info(f"Selected Strategy: {selected_strategy}")
        
        if selected_strategy == 'wait':
            return None
        
        # 5. Execute selected strategy
        signal = None
        
        if selected_strategy == 'ict_2022':
            ict_signal = self.analyze_ict_2022(symbol)
            if ict_signal:
                signal = self._convert_ict_to_dict(ict_signal)
        
        elif selected_strategy == 'power_of_3':
            signal = self.analyze_power_of_3(symbol)
        
        elif selected_strategy == 'trend_following':
            signal = self.analyze_trend_following(symbol)
        
        elif selected_strategy == 'mean_reversion':
            signal = self.analyze_mean_reversion(symbol)
        
        elif selected_strategy == 'supply_demand':
            signal = self.analyze_supply_demand(symbol)
        
        # 7. Master Strategies (ALL 112+ strategies)
        elif selected_strategy == 'master_all':
            signal = self.analyze_all_strategies_master(symbol)
        
        # 6. Final validation
        if signal:
            normalized_direction = self._normalize_direction(signal.get('direction'))
            if not normalized_direction:
                self.logger.warning(f"Invalid signal direction for {symbol}: {signal.get('direction')}")
                return None

            signal['direction'] = normalized_direction
            signal['symbol'] = symbol
            signal['amd_phase'] = self.amd_phase
            
            # Calculate position size
            signal['lot_size'] = self._calculate_position_size(signal)
            
            # Validate risk
            if self._validate_risk(signal):
                return signal
        
        return None
    
    def execute_trade(self, signal: Dict) -> Optional[List[int]]:
        """
        Execute trade with position scaling and comprehensive risk management
        
        Args:
            signal: Trade signal dictionary
            
        Returns:
            List of order tickets or None
        """
        normalized_direction = self._normalize_direction(signal.get('direction'))
        if not normalized_direction:
            self.logger.error(
                f"Trade skipped due to invalid direction: {signal.get('direction')}"
            )
            return None
        signal['direction'] = normalized_direction

        # Check if should scale entry (multiple positions)
        should_scale, num_positions, scaling_reason = self.position_scaling.should_scale_entry(signal)
        
        if should_scale:
            self.logger.info(f"\n{'='*60}")
            self.logger.info("[SNIPER] ENTRY - SCALING POSITIONS")
            self.logger.info(f"{'='*60}")
            self.logger.info(self.position_scaling.get_scaling_summary(signal))
            
            # Execute scaled entry (multiple positions at once)
            tickets = self.position_scaling.execute_scaled_entry(signal, num_positions)
            
            if tickets:
                # Track all positions
                for ticket in tickets:
                    self.active_trades[ticket] = {
                        'symbol': signal['symbol'],
                        'direction': signal['direction'],
                        'entry': signal['entry'],
                        'sl': signal['stop_loss'],
                        'tp': signal.get('take_profit'),
                        'lot_size': signal['lot_size'] / num_positions,
                        'strategy': signal['strategy'],
                        'amd_phase': signal.get('amd_phase'),
                        'entry_time': datetime.now(),
                        'scaled_group': tickets[0]  # Group ID
                    }
                
                self.daily_stats['trades'] += 1  # Count as one setup
                self.logger.info(f"[OK] Scaled entry complete: {len(tickets)} positions")
                return tickets
        
        else:
            # Single position execution
            symbol = signal['symbol']
            direction = signal['direction']
            entry = signal['entry']
            stop_loss = signal['stop_loss']
            take_profit = signal.get('take_profit', None)
            lot_size = signal['lot_size']
            
            order_type = mt5.ORDER_TYPE_BUY if direction == 'LONG' else mt5.ORDER_TYPE_SELL
            
            # Get symbol filling mode
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                self.logger.error(f"Symbol {symbol} not found")
                return None
            
            # Determine supported filling mode
            filling_type = symbol_info.filling_mode
            if filling_type & 2:  # FOK
                type_filling = mt5.ORDER_FILLING_FOK
            elif filling_type & 1:  # IOC
                type_filling = mt5.ORDER_FILLING_IOC
            else:  # RETURN (default)
                type_filling = mt5.ORDER_FILLING_RETURN
            
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': symbol,
                'volume': lot_size,
                'type': order_type,
                'price': entry,
                'sl': stop_loss,
                'tp': take_profit if take_profit else 0,
                'deviation': 20,
                'magic': 202602,
                'comment': f"{signal['strategy']}_{signal.get('amd_phase', 'UNKNOWN')}",
                'type_time': mt5.ORDER_TIME_GTC,
                'type_filling': type_filling
            }
            
            result = mt5.order_send(request)
            
            # Check if result is None
            if result is None:
                self.logger.error(f"Trade failed: order_send returned None. Last error: {mt5.last_error()}")
                return None
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"Trade executed: {direction} {lot_size} {symbol} @ {entry}")
                self.logger.info(f"Strategy: {signal['strategy']} | AMD: {signal.get('amd_phase')}")
                
                # Track trade
                self.active_trades[result.order] = {
                    'symbol': symbol,
                    'direction': direction,
                    'entry': entry,
                    'sl': stop_loss,
                    'tp': take_profit,
                    'lot_size': lot_size,
                    'strategy': signal['strategy'],
                    'amd_phase': signal.get('amd_phase'),
                    'entry_time': datetime.now()
                }
                
                self.daily_stats['trades'] += 1
                
                # Psychology monitor
                self.psychology_monitor.record_trade_decision(
                    'OPEN',
                    signal.get('confidence', 70),
                    signal['strategy']
                )
                
                return [result.order]
            else:
                self.logger.error(f"Trade failed: {result.retcode} - {result.comment}")
                return None
    
    def monitor_active_trades(self):
        """
        Monitor all active trades for dynamic exit signals
        
        Checks for market reversals and closes positions proactively
        """
        if not self.active_trades:
            return
        
        for ticket, position_info in list(self.active_trades.items()):
            symbol = position_info['symbol']
            
            # Get current market data
            df_current = self._get_ohlcv(symbol, mt5.TIMEFRAME_M15, 50)
            
            if df_current is None:
                continue
            
            # Check for exit signal
            should_exit, reason = self.dynamic_exit_manager.check_for_exit(
                position_info, df_current
            )
            
            if should_exit:
                self.logger.warning(f"[WARN] Dynamic exit triggered for {ticket}: {reason}")
                
                # Close position
                if self.dynamic_exit_manager.close_position(ticket, reason):
                    self.logger.info(f"[OK] Position {ticket} closed successfully")
                    del self.active_trades[ticket]
    
    def _pre_trade_checks(self, symbol: str) -> bool:
        """Pre-trade validation checks"""
        # 1. Check if position already exists
        if self._has_open_position(symbol):
            return False
        
        # 2. Check daily loss limit
        if self.daily_stats['pnl'] <= -1 * (self.account_balance * 0.02):  # -2% limit
            self.logger.warning("Daily loss limit reached")
            return False
        
        # 3. Check max trades
        if self.daily_stats['trades'] >= 3:
            self.logger.warning("Max daily trades reached")
            return False
        
        # 4. News filter
        is_safe, reason = self.news_filter.is_safe_to_trade(symbol)
        if not is_safe:
            self.logger.info(f"News filter: {reason}")
            return False
        
        # 5. Psychology check
        if self.psychology_monitor.consecutive_losses >= 3:
            self.logger.warning("Psychology: Too many consecutive losses")
            return False
        
        return True
    
    def _has_open_position(self, symbol: str) -> bool:
        """Check if position exists for symbol"""
        positions = mt5.positions_get(symbol=symbol)
        return positions is not None and len(positions) > 0
    
    def _get_ohlcv(self, symbol: str, timeframe, bars: int = 100) -> Optional[pd.DataFrame]:
        """Get OHLCV data from MT5"""
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')

        # Normalize volume field for modules expecting `volume`
        if 'volume' not in df.columns:
            if 'real_volume' in df.columns and float(df['real_volume'].sum()) > 0:
                df['volume'] = df['real_volume']
            elif 'tick_volume' in df.columns:
                df['volume'] = df['tick_volume']
            else:
                df['volume'] = 0.0

        return df
    
    def _get_session_data(self, symbol: str, session: str) -> pd.DataFrame:
        """Get data for specific session"""
        # This would filter data by session time
        # For now, return recent M15 data
        return self._get_ohlcv(symbol, mt5.TIMEFRAME_M15, 50)
    
    def _detect_market_regime(self, df: pd.DataFrame) -> str:
        """Detect if market is trending or ranging"""
        if df is None or len(df) < 50:
            return 'UNKNOWN'
        
        adx = self._calculate_adx(df, 14)
        
        if adx > 30:
            return 'STRONG_TREND'
        elif adx > 20:
            return 'WEAK_TREND'
        else:
            return 'RANGING'
    
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average Directional Index"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        # Directional Movement
        up = high.diff()
        down = -low.diff()
        
        plus_dm = up.where((up > down) & (up > 0), 0)
        minus_dm = down.where((down > up) & (down > 0), 0)
        
        plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(period).mean()
        
        return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Relative Strength Index"""
        delta = df['close'].diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = -delta.where(delta < 0, 0).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def _calculate_amd_stop(self, df: pd.DataFrame, direction: str) -> float:
        """Calculate stop loss for AMD strategy"""
        direction = self._normalize_direction(direction)
        if direction == 'LONG':
            return self.power_of_3.asian_range_low - 5.0
        else:
            return self.power_of_3.asian_range_high + 5.0
    
    def _calculate_amd_target(self, df: pd.DataFrame, direction: str) -> float:
        """Calculate take profit for AMD strategy"""
        direction = self._normalize_direction(direction)
        range_size = self.power_of_3.asian_range_high - self.power_of_3.asian_range_low
        
        if direction == 'LONG':
            return self.power_of_3.asian_range_high + (range_size * 1.5)
        else:
            return self.power_of_3.asian_range_low - (range_size * 1.5)
    
    def _convert_ict_to_dict(self, ict_signal: ICTTradeSignal) -> Dict:
        """Convert ICT signal to standard dict format"""
        return {
            'strategy': 'ict_2022',
            'direction': ict_signal.direction,
            'entry': ict_signal.entry_price,
            'stop_loss': ict_signal.stop_loss,
            'take_profit': ict_signal.take_profit_1,
            'confidence': ict_signal.confluence_score,
            'ict_signal': ict_signal  # Keep full signal for reference
        }
    
    def _calculate_position_size(self, signal: Dict) -> float:
        """Calculate position size based on risk"""
        risk_pct = 0.01  # 1% risk per trade
        risk_amount = self.account_balance * risk_pct
        
        # Price distance at risk
        entry = signal['entry']
        stop_loss = signal['stop_loss']
        price_risk = abs(entry - stop_loss)
        if price_risk <= 0:
            return 0.01
        
        # Get symbol metadata
        symbol_info = mt5.symbol_info(signal['symbol'])
        if symbol_info is None:
            return 0.01  # Minimum lot
        
        tick_size = getattr(symbol_info, 'trade_tick_size', 0.0) or 0.0
        tick_value = getattr(symbol_info, 'trade_tick_value', 0.0) or 0.0

        # Robust risk-per-lot calculation
        if tick_size > 0 and tick_value > 0:
            risk_per_lot = (price_risk / tick_size) * tick_value
        else:
            # Fallback approximation if broker metadata is missing
            risk_per_lot = price_risk * 100000 * 0.10

        if risk_per_lot <= 0:
            return 0.01

        lot_size = risk_amount / risk_per_lot
        
        # Apply limits
        min_vol = getattr(symbol_info, 'volume_min', 0.01) or 0.01
        max_vol = getattr(symbol_info, 'volume_max', 100.0) or 100.0
        vol_step = getattr(symbol_info, 'volume_step', 0.01) or 0.01

        lot_size = max(min_vol, min(lot_size, max_vol))
        lot_size = round(lot_size / vol_step) * vol_step
        lot_size = max(min_vol, min(lot_size, max_vol))
        
        return round(lot_size, 2)
    
    def _validate_risk(self, signal: Dict) -> bool:
        """Validate trade meets risk requirements"""
        # Check R:R ratio
        entry = signal['entry']
        stop_loss = signal['stop_loss']
        take_profit = signal.get('take_profit')
        
        if take_profit:
            risk = abs(entry - stop_loss)
            reward = abs(take_profit - entry)
            rr_ratio = reward / risk if risk > 0 else 0
            
            if rr_ratio < 1.5:  # Minimum 1:1.5 R:R
                self.logger.info(f"R:R too low: {rr_ratio:.2f}")
                return False
        
        # Check confidence
        if signal.get('confidence', 0) < 60:
            self.logger.info(f"Confidence too low: {signal.get('confidence')}")
            return False
        
        return True
    
    def start(self, symbols: List[str], check_interval: int = 300):
        """
        Start unified trading bot with dynamic exit monitoring
        
        Args:
            symbols: List of symbols to trade
            check_interval: Seconds between analysis cycles
        """
        if not mt5.initialize():
            self.logger.error("MT5 initialization failed")
            return
        
        self.logger.info("="*80)
        self.logger.info("UNIFIED TRADING BOT STARTED")
        self.logger.info(f"Primary Strategy: {self.primary_strategy}")
        self.logger.info(f"AMD Detection: {'Enabled' if self.enable_amd_detection else 'Disabled'}")
        self.logger.info(f"Position Scaling: {'Enabled' if self.position_scaling else 'Disabled'}")
        self.logger.info(f"Dynamic Exits: {'Enabled' if self.dynamic_exit_manager else 'Disabled'}")
        self.logger.info(f"Symbols: {', '.join(symbols)}")
        self.logger.info("="*80)
        
        try:
            cycle_count = 0
            while True:
                cycle_count += 1
                
                # Monitor existing positions every cycle
                if self.dynamic_exit_manager:
                    self.monitor_active_trades()
                
                # Analyze for new trades
                for symbol in symbols:
                    try:
                        signal = self.analyze_symbol(symbol)
                        
                        if signal:
                            self.logger.info(f"\n{'='*60}")
                            self.logger.info(f"TRADE SIGNAL: {signal['strategy'].upper()}")
                            self.logger.info(f"Symbol: {symbol} | Direction: {signal['direction']}")
                            self.logger.info(f"Entry: {signal['entry']:.2f} | SL: {signal['stop_loss']:.2f}")
                            self.logger.info(f"AMD Phase: {signal.get('amd_phase', 'N/A')}")
                            self.logger.info(
                                f"Confidence: {signal.get('confidence', signal.get('confluence_score', 0)):.1f}"
                            )
                            self.logger.info(f"{'='*60}\n")
                            
                            # Execute (returns list of tickets)
                            tickets = self.execute_trade(signal)
                            if tickets:
                                self.logger.info(f"[OK] Trade executed: {len(tickets)} position(s) opened")
                                time.sleep(5)  # Brief pause after trade
                    
                    except Exception as e:
                        self.logger.error(f"Error analyzing {symbol}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue
                
                # Status update every 10 cycles
                if cycle_count % 10 == 0:
                    self.logger.info(f"Status: Cycle {cycle_count} | Active positions: {len(self.active_trades)}")
                    self.logger.info(f"Daily stats: {self.daily_stats['trades']} trades, P&L: ${self.daily_stats['pnl']:.2f}")
                
                # Wait before next cycle
                time.sleep(check_interval)
        
        except KeyboardInterrupt:
            self.logger.info("\nBot stopped by user")
        finally:
            mt5.shutdown()
            self.logger.info("MT5 connection closed")
