"""
TRADING CIRCUIT BREAKER
Safety system to halt trading during adverse conditions

Features:
- Consecutive loss detection
- Daily loss limit enforcement
- Unusual volatility detection
- Major news event detection
- Spread widening detection
- Automatic position closure
- Configurable pause durations
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, time as dt_time
from enum import Enum


class TriggerType(Enum):
    """Circuit breaker trigger types"""
    CONSECUTIVE_LOSSES = "CONSECUTIVE_LOSSES"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    HIGH_VOLATILITY = "HIGH_VOLATILITY"
    MAJOR_NEWS = "MAJOR_NEWS"
    WIDE_SPREAD = "WIDE_SPREAD"
    DRAWDOWN_LIMIT = "DRAWDOWN_LIMIT"
    RAPID_LOSSES = "RAPID_LOSSES"
    SYSTEM_ERROR = "SYSTEM_ERROR"


@dataclass
class CircuitBreakerTrigger:
    """Circuit breaker trigger information"""
    trigger_type: TriggerType
    value: float
    threshold: float
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    timestamp: datetime


class TradingCircuitBreaker:
    """
    Safety system to halt trading during adverse conditions
    """
    
    def __init__(self, account_balance: float,
                 config: Optional[Dict] = None):
        """
        Initialize circuit breaker
        
        Args:
            account_balance: Current account balance
            config: Configuration dictionary
        """
        self.initial_balance = account_balance
        self.account_balance = account_balance
        self.get_live_equity_callback = None  # Will be set by orchestrator for live equity queries
        
        # Load configuration
        config = config or {}
        
        # Loss tracking
        self.consecutive_losses = 0
        self.daily_loss = 0
        self.daily_trades = []
        self.current_drawdown = 0
        self.peak_balance = account_balance
        
        # CORRECTED Thresholds (realistic for retail)
        self.max_consecutive_losses = config.get('max_consecutive_losses', 5)  # 5 not 3
        self.max_daily_loss_pct = config.get('max_daily_loss_pct', 0.03)  # 3% not 2%
        self.min_daily_loss_amount_usd = config.get('min_daily_loss_amount_usd', 3.0)  # Absolute floor for micro accounts
        self.max_drawdown_pct = config.get('max_drawdown_pct', 0.20)  # 20% not 15%
        self.min_drawdown_amount_usd = config.get('min_drawdown_amount_usd', 5.0)  # Absolute floor for micro accounts
        self.rapid_loss_threshold = config.get('rapid_loss_threshold', 6)  # 6 losses in 1 hour
        
        # ADAPTIVE ACTIONS: Don't just pause, reduce size
        self.consecutive_loss_action = config.get('consecutive_loss_action', 'reduce_size_50%')
        self.size_reduction_factor = 0.5  # Reduce to 50% after consecutive losses
        
        # Volatility thresholds
        self.normal_volatility_max = config.get('normal_volatility_max', 2.0)
        self.extreme_volatility_threshold = config.get(
            'extreme_volatility_threshold',
            config.get('extreme_volatility', 3.0)
        )
        
        # Spread thresholds (pips or points)
        # CRITICAL: Default spreads must be realistic for each instrument type
        self.normal_spread = config.get('normal_spread', {
            # Forex majors: 2-3 pips
            'EURUSD': 2.0,
            'GBPUSD': 3.0,
            'USDJPY': 2.0,
            'USDCHF': 3.0,
            'USDCAD': 3.0,
            'AUDUSD': 2.5,
            'NZDUSD': 3.0,
            # Forex crosses: 3-5 pips
            'EURGBP': 3.0,
            'EURJPY': 3.5,
            'GBPJPY': 4.0,
            # Metals: 20-50 pips (NOT 0.50!)
            'XAUUSD': 50.0,  # Gold
            'XAGUSD': 30.0,  # Silver
        })
        self.spread_multiplier_threshold = config.get(
            'spread_multiplier_threshold',
            config.get('spread_multiplier', 3.0)
        )
        
        # Pause durations (hours) - CORRECTED
        pause_durations_raw = config.get('pause_durations', {
            'CONSECUTIVE_LOSSES': 2,      # 2 hours (reduce size, limited pause)
            'DAILY_LOSS_LIMIT': 24,       # Full day pause
            'HIGH_VOLATILITY': 1,         # 1 hour (was 2)
            'MAJOR_NEWS': 0.5,            # 30 min
            'WIDE_SPREAD': 0.25,          # 15 min
            'DRAWDOWN_LIMIT': 48,         # 48 hours (was 24)
            'RAPID_LOSSES': 3,            # 3 hours (was 4)
            'SYSTEM_ERROR': 0.5
        })

        # Support YAML keys in lowercase/uppercase (e.g., consecutive_losses)
        self.pause_durations = {
            str(key).upper(): value
            for key, value in pause_durations_raw.items()
        }
        
        # State
        self.is_active = False
        self.pause_until = None
        self.active_triggers = []
        self.trigger_history = []
        
    def check_circuit_breaker(self, trade_result: Optional[Dict] = None,
                             market_data: Optional[Dict] = None,
                             current_spread: Optional[float] = None) -> Tuple[bool, List[CircuitBreakerTrigger]]:
        """
        Check if circuit breaker should trigger
        
        Args:
            trade_result: Latest trade result (if any)
            market_data: Current market data
            current_spread: Current spread
            
        Returns:
            (should_halt_trading, list_of_triggers)
        """
        # Check if currently paused
        if self.is_active and self.pause_until:
            if datetime.now() < self.pause_until:
                return True, self.active_triggers
            else:
                # Pause expired, reset
                self._reset_circuit_breaker()
        
        triggers = []
        
        # Update state from trade result
        if trade_result:
            self._update_state(trade_result)
        
        # 1. Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            triggers.append(CircuitBreakerTrigger(
                trigger_type=TriggerType.CONSECUTIVE_LOSSES,
                value=self.consecutive_losses,
                threshold=self.max_consecutive_losses,
                severity='HIGH',
                timestamp=datetime.now()
            ))
        
        # 2. Check daily loss limit (require both percentage AND absolute amount for micro accounts)
        daily_loss_abs = sum(abs(t['pnl']) for t in self.daily_trades if t['pnl'] < 0)
        if self.daily_loss >= self.max_daily_loss_pct and daily_loss_abs >= self.min_daily_loss_amount_usd:
            triggers.append(CircuitBreakerTrigger(
                trigger_type=TriggerType.DAILY_LOSS_LIMIT,
                value=self.daily_loss * 100,
                threshold=self.max_daily_loss_pct * 100,
                severity='CRITICAL',
                timestamp=datetime.now()
            ))
        
        # 3. Check drawdown (require both percentage AND absolute amount for micro accounts)
        drawdown_pct = self._calculate_drawdown()
        drawdown_abs = max(0.0, self.peak_balance - self.account_balance)
        if drawdown_pct >= self.max_drawdown_pct and drawdown_abs >= self.min_drawdown_amount_usd:
            triggers.append(CircuitBreakerTrigger(
                trigger_type=TriggerType.DRAWDOWN_LIMIT,
                value=drawdown_pct * 100,
                threshold=self.max_drawdown_pct * 100,
                severity='CRITICAL',
                timestamp=datetime.now()
            ))
        
        # 4. Check rapid losses
        rapid_losses = self._count_rapid_losses()
        if rapid_losses >= self.rapid_loss_threshold:
            triggers.append(CircuitBreakerTrigger(
                trigger_type=TriggerType.RAPID_LOSSES,
                value=rapid_losses,
                threshold=self.rapid_loss_threshold,
                severity='HIGH',
                timestamp=datetime.now()
            ))
        
        # 5. Check unusual volatility
        if market_data:
            volatility = market_data.get('volatility', 0)
            if volatility > self.extreme_volatility_threshold:
                triggers.append(CircuitBreakerTrigger(
                    trigger_type=TriggerType.HIGH_VOLATILITY,
                    value=volatility,
                    threshold=self.extreme_volatility_threshold,
                    severity='MEDIUM',
                    timestamp=datetime.now()
                ))
        
        # 6. Check major news events
        if self._is_major_news_event():
            triggers.append(CircuitBreakerTrigger(
                trigger_type=TriggerType.MAJOR_NEWS,
                value=1.0,
                threshold=1.0,
                severity='MEDIUM',
                timestamp=datetime.now()
            ))
        
        # 7. Check spread widening
        if current_spread:
            spread_trigger = self._check_spread_widening(current_spread, market_data)
            if spread_trigger:
                triggers.append(spread_trigger)
        
        # Activate circuit breaker if any triggers
        if triggers:
            self._activate_circuit_breaker(triggers)
            return True, triggers
        
        return False, []
    
    def _update_state(self, trade_result: Dict):
        """Update internal state from trade result"""
        pnl = trade_result.get('pnl', 0)
        pnl_pct = trade_result.get('pnl_pct', 0)
        
        # CRITICAL: Query live equity if callback available, otherwise use manual tracking
        if self.get_live_equity_callback is not None:
            try:
                live_equity = self.get_live_equity_callback()
                if live_equity > 0:
                    self.account_balance = live_equity
                    # Update peak if new high
                    if self.account_balance > self.peak_balance:
                        self.peak_balance = self.account_balance
                else:
                    # Fallback to manual tracking if query fails
                    self.account_balance += pnl
            except Exception:
                # Fallback to manual tracking on error
                self.account_balance += pnl
        else:
            # Manual balance tracking (fallback)
            self.account_balance += pnl
        
        # Update consecutive losses
        if pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0
        
        # Update daily loss
        self.daily_loss += abs(pnl_pct) if pnl < 0 else 0
        
        # Add to daily trades
        self.daily_trades.append({
            'timestamp': datetime.now(),
            'pnl': pnl,
            'pnl_pct': pnl_pct
        })
        
        # Clean old trades (older than 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        self.daily_trades = [t for t in self.daily_trades 
                           if t['timestamp'] > cutoff]
        
        # Recalculate daily loss from recent trades
        self.daily_loss = sum(abs(t['pnl_pct']) for t in self.daily_trades 
                            if t['pnl'] < 0)
    
    def _calculate_drawdown(self) -> float:
        """Calculate current drawdown from peak"""
        import logging
        logger = logging.getLogger('SNIPER_PRO_2024')
        
        # CRITICAL: Query live equity for accurate drawdown calculation
        current_balance = self.account_balance
        if self.get_live_equity_callback is not None:
            try:
                live_equity = self.get_live_equity_callback()
                if live_equity > 0:
                    current_balance = live_equity
                    # Update tracking
                    self.account_balance = current_balance
                    if current_balance > self.peak_balance:
                        self.peak_balance = current_balance
            except Exception as e:
                # FIX: Log exceptions instead of silent pass
                logger.warning(f"Circuit breaker equity callback failed: {e}. Using tracked balance.")
        
        if current_balance >= self.peak_balance:
            self.current_drawdown = 0
            return 0
        
        drawdown_pct = 1 - (current_balance / self.peak_balance)
        self.current_drawdown = drawdown_pct
        
        return drawdown_pct
    
    def _count_rapid_losses(self, window_hours: int = 1) -> int:
        """Count losses in recent window"""
        cutoff = datetime.now() - timedelta(hours=window_hours)
        
        rapid_losses = sum(1 for t in self.daily_trades 
                         if t['timestamp'] > cutoff and t['pnl'] < 0)
        
        return rapid_losses
    
    def _is_major_news_event(self) -> bool:
        """
        Check if major news event is happening
        
        Uses real economic calendar integration when available.
        Falls back to time-based detection for major known events.
        """
        import logging
        logger = logging.getLogger('SNIPER_PRO_2024')
        
        try:
            # Try to use real news filter from news_filter.py
            from src.data.news_filter import EconomicCalendar, NewsFilter
            
            calendar = EconomicCalendar(timezone='Africa/Nairobi')
            news_filter = NewsFilter(calendar, buffer_minutes_before=30, buffer_minutes_after=15)
            
            # Check if it's safe to trade (USD is most important for forex)
            can_trade, reason = news_filter.can_trade('EURUSD')
            
            if not can_trade:
                logger.info(f"News event detected: {reason}")
                return True
            
            return False
            
        except ImportError:
            # Fallback: Use time-based detection
            current_time = datetime.now()
            current_time_only = current_time.time()
            
            # Major news times (GMT+3 for Nairobi) - US news events
            news_times = [
                (dt_time(15, 30), dt_time(15, 45)),  # US Retail Sales
                (dt_time(16, 0), dt_time(16, 15)),  # US CPI/PPI
                (dt_time(17, 0), dt_time(17, 15)),  # US GDP
                (dt_time(18, 0), dt_time(18, 15)),  # US NFP (non-farm payrolls)
                (dt_time(19, 0), dt_time(19, 15)),  # US FOMC/Interest Rate Decision
            ]
            
            for start, end in news_times:
                if start <= current_time_only <= end:
                    logger.info(f"Major news event detected at {current_time_only}")
                    return True
            
            # Check if it's first Friday of month (NFP - most important)
            if current_time.weekday() == 4:  # Friday
                if 1 <= current_time.day <= 7:  # First week
                    if dt_time(18, 0) <= current_time_only <= dt_time(19, 0):
                        logger.info(f"NFP news event detected at {current_time_only}")
                        return True
            
            # Check for FOMC meeting weeks (March, June, September, December)
            if current_time.month in [3, 6, 9, 12]:
                if current_time.day >= 15 and current_time.day <= 21:
                    if current_time.weekday() in [1, 2, 3]:  # Tue-Thu
                        if dt_time(19, 0) <= current_time_only <= dt_time(20, 0):
                            logger.info(f"FOMC news event detected at {current_time_only}")
                            return True
            
            return False
    
    def _check_spread_widening(self, current_spread: float,
                               market_data: Optional[Dict]) -> Optional[CircuitBreakerTrigger]:
        """Check if spread is abnormally wide"""
        symbol = market_data.get('symbol', 'EURUSD') if market_data else 'EURUSD'
        
        normal_spread = self.normal_spread.get(symbol, 2.0)
        
        if current_spread > normal_spread * self.spread_multiplier_threshold:
            return CircuitBreakerTrigger(
                trigger_type=TriggerType.WIDE_SPREAD,
                value=current_spread,
                threshold=normal_spread * self.spread_multiplier_threshold,
                severity='LOW',
                timestamp=datetime.now()
            )
        
        return None
    
    def _activate_circuit_breaker(self, triggers: List[CircuitBreakerTrigger]):
        """Activate circuit breaker with appropriate pause"""
        self.is_active = True
        self.active_triggers = triggers
        
        # Store in history
        for trigger in triggers:
            self.trigger_history.append(trigger)
        
        # Keep only last 1000 triggers
        if len(self.trigger_history) > 1000:
            self.trigger_history = self.trigger_history[-1000:]
        
        # Determine pause duration based on severity
        max_pause_hours = 0
        
        for trigger in triggers:
            pause_hours = self.pause_durations.get(
                trigger.trigger_type.value, 
                1
            )
            
            # Increase pause for higher severity
            if trigger.severity == 'CRITICAL':
                pause_hours *= 2
            elif trigger.severity == 'HIGH':
                pause_hours *= 1.5
            
            max_pause_hours = max(max_pause_hours, pause_hours)
        
        # Set pause duration
        self.pause_until = datetime.now() + timedelta(hours=max_pause_hours)
        
        # Log activation
        self._log_activation(triggers, max_pause_hours)
    
    def _reset_circuit_breaker(self):
        """Reset circuit breaker after pause expires"""
        self.is_active = False
        self.active_triggers = []
        self.pause_until = None
        
        # Don't reset counters - they should naturally decay
    
    def _log_activation(self, triggers: List[CircuitBreakerTrigger], 
                       pause_hours: float):
        """Log circuit breaker activation"""
        print("\n" + "="*80)
        print("!!! CIRCUIT BREAKER ACTIVATED !!!")
        print("="*80)
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Pause Duration: {pause_hours:.1f} hours")
        print(f"Resume Trading: {self.pause_until.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\nTriggered by {len(triggers)} condition(s):")
        
        for i, trigger in enumerate(triggers, 1):
            print(f"\n{i}. {trigger.trigger_type.value}")
            print(f"   Severity: {trigger.severity}")
            print(f"   Current Value: {trigger.value:.2f}")
            print(f"   Threshold: {trigger.threshold:.2f}")
        
        print("\n" + "="*80)
        print("All open positions will be closed.")
        print("Trading will automatically resume after pause period.")
        print("="*80 + "\n")
    
    def force_activate(self, reason: str, pause_hours: float = 1.0):
        """Manually activate circuit breaker"""
        trigger = CircuitBreakerTrigger(
            trigger_type=TriggerType.SYSTEM_ERROR,
            value=1.0,
            threshold=1.0,
            severity='HIGH',
            timestamp=datetime.now()
        )
        
        self._activate_circuit_breaker([trigger])
        
        # Override pause duration
        self.pause_until = datetime.now() + timedelta(hours=pause_hours)
        
        print(f"\n[MANUAL CIRCUIT BREAKER] {reason}")
        print(f"Trading paused for {pause_hours:.1f} hours\n")
    
    def can_trade(self) -> Tuple[bool, Optional[str]]:
        """
        Check if trading is allowed
        
        Returns:
            (allowed, reason_if_not_allowed)
        """
        if not self.is_active:
            return True, None
        
        if self.pause_until and datetime.now() >= self.pause_until:
            self._reset_circuit_breaker()
            return True, None
        
        # Still paused
        remaining = self.pause_until - datetime.now()
        remaining_minutes = remaining.total_seconds() / 60
        
        reason = f"Circuit breaker active. Resume in {remaining_minutes:.0f} minutes."
        
        if self.active_triggers:
            trigger_names = [t.trigger_type.value for t in self.active_triggers]
            reason += f" Triggers: {', '.join(trigger_names)}"
        
        return False, reason
    
    def get_status(self) -> Dict:
        """Get current circuit breaker status"""
        can_trade, reason = self.can_trade()
        
        return {
            'active': self.is_active,
            'can_trade': can_trade,
            'reason': reason,
            'consecutive_losses': self.consecutive_losses,
            'daily_loss_pct': self.daily_loss * 100,
            'current_drawdown_pct': self.current_drawdown * 100,
            'pause_until': self.pause_until.isoformat() if self.pause_until else None,
            'active_triggers': [t.trigger_type.value for t in self.active_triggers],
            'total_triggers_today': len([t for t in self.trigger_history 
                                        if t.timestamp.date() == datetime.now().date()])
        }
    
    def reset_daily_counters(self):
        """Reset daily counters (call at start of new day)"""
        self.daily_loss = 0
        self.daily_trades = []
        self.consecutive_losses = 0
    
    def get_statistics(self) -> Dict:
        """Get circuit breaker statistics"""
        if not self.trigger_history:
            return {
                'total_activations': 0,
                'activation_rate': 0,
                'most_common_trigger': 'N/A',
                'avg_pause_hours': 0
            }
        
        # Count by trigger type
        trigger_counts = {}
        for trigger in self.trigger_history:
            trigger_type = trigger.trigger_type.value
            trigger_counts[trigger_type] = trigger_counts.get(trigger_type, 0) + 1
        
        most_common = max(trigger_counts.items(), key=lambda x: x[1])[0]
        
        # Calculate average pause
        total_activations = len(set(t.timestamp for t in self.trigger_history))
        
        return {
            'total_activations': total_activations,
            'trigger_counts': trigger_counts,
            'most_common_trigger': most_common,
            'last_24h_activations': len([t for t in self.trigger_history
                                        if t.timestamp > datetime.now() - timedelta(hours=24)])
        }
    
    def print_status(self):
        """Print current status in readable format"""
        status = self.get_status()
        
        print("\n" + "="*80)
        print("CIRCUIT BREAKER STATUS")
        print("="*80)
        print(f"Active: {'YES' if status['active'] else 'NO'}")
        print(f"Can Trade: {'YES' if status['can_trade'] else 'NO'}")
        
        if not status['can_trade']:
            print(f"\nReason: {status['reason']}")
        
        print(f"\nCurrent Metrics:")
        print(f"  Consecutive Losses: {status['consecutive_losses']} / {self.max_consecutive_losses}")
        print(f"  Daily Loss: {status['daily_loss_pct']:.2f}% / {self.max_daily_loss_pct * 100:.2f}%")
        print(f"  Current Drawdown: {status['current_drawdown_pct']:.2f}% / {self.max_drawdown_pct * 100:.2f}%")
        
        if status['active_triggers']:
            print(f"\nActive Triggers: {', '.join(status['active_triggers'])}")
        
        print(f"\nTotal Activations Today: {status['total_triggers_today']}")
        print("="*80 + "\n")
