"""
MULTI-TRIGGER EXIT MANAGER
Smart exit system with multiple triggers and partial profit taking

Features:
- Profit target exits (TP1, TP2, TP3)
- Trailing stop management
- Time-based exits
- Technical indicator exits (RSI, MACD divergence)
- Correlation-based exits
- Partial profit taking
- Break-even management
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class ExitTrigger(Enum):
    """Exit trigger types"""
    PROFIT_TARGET = "PROFIT_TARGET"
    STOP_LOSS = "STOP_LOSS"
    STOP_ADJUSTMENT = "STOP_ADJUSTMENT"
    TRAILING_STOP = "TRAILING_STOP"
    TIME_EXIT = "TIME_EXIT"
    TECHNICAL_EXIT = "TECHNICAL_EXIT"
    CORRELATION_EXIT = "CORRELATION_EXIT"
    NEWS_EXIT = "NEWS_EXIT"
    VOLATILITY_EXIT = "VOLATILITY_EXIT"
    BREAKEVEN = "BREAKEVEN"


@dataclass
class ExitSignal:
    """Exit signal with details"""
    trigger_type: ExitTrigger
    exit_percentage: float  # 0-100 (% of position to close)
    exit_price: float
    confidence: float  # 0-100
    reason: str
    timestamp: datetime


@dataclass
class PositionExit:
    """Position exit configuration"""
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    entry_time: datetime
    
    # Exit levels
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: Optional[float]
    
    # State
    remaining_size: float  # % remaining (0-100)
    breakeven_moved: bool
    trailing_stop_active: bool
    trailing_stop_price: Optional[float]
    
    # Partial exits taken
    exits_taken: List[ExitSignal]

    # Risk context for controlled SL modifications
    initial_stop_loss: float = 0.0
    initial_risk: float = 0.0
    stop_adjustments_used: int = 0


class MultiTriggerExitManager:
    """
    Advanced exit management with multiple triggers
    Inspired by professional trading systems
    """
    
    def __init__(
        self,
        use_trailing_stops: bool = True,
        use_partial_exits: bool = True,
        max_hold_hours: int = 24,
        enable_defensive_stop_adjustment: bool = True,
        max_stop_adjustments: int = 1,
        adjustment_trigger_atr_fraction: float = 0.35,
        max_extension_r_multiple: float = 0.35,
        max_extension_atr: float = 0.60,
        min_recovery_score: float = 0.55,
        min_hold_seconds: int = 300,
    ):
        """
        Initialize exit manager
        
        Args:
            use_trailing_stops: Enable trailing stops
            use_partial_exits: Enable partial profit taking
            max_hold_hours: Maximum hours to hold position
            min_hold_seconds: Minimum seconds before technical/trailing exits fire
        """
        self.use_trailing_stops = use_trailing_stops
        self.use_partial_exits = use_partial_exits
        self.max_hold_hours = max_hold_hours
        self.min_hold_seconds = max(0, int(min_hold_seconds))
        self.enable_defensive_stop_adjustment = bool(enable_defensive_stop_adjustment)
        self.max_stop_adjustments = max(0, int(max_stop_adjustments or 0))
        self.adjustment_trigger_atr_fraction = max(0.05, float(adjustment_trigger_atr_fraction or 0.35))
        self.max_extension_r_multiple = max(0.05, float(max_extension_r_multiple or 0.35))
        self.max_extension_atr = max(0.05, float(max_extension_atr or 0.60))
        self.min_recovery_score = max(0.0, min(float(min_recovery_score or 0.55), 1.0))
        
        # Active position exits
        self.active_exits: Dict[str, PositionExit] = {}
        
    def create_exit_plan(self, symbol: str, direction: str,
                        entry_price: float, stop_loss: float,
                        atr: float, entry_time: datetime) -> PositionExit:
        """
        Create exit plan for new position
        
        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            entry_price: Entry price
            stop_loss: Stop loss price
            atr: Average True Range
            entry_time: Position entry time
            
        Returns:
            PositionExit with all levels configured
        """
        # Calculate take profit levels
        risk = abs(entry_price - stop_loss)
        
        if direction == 'BUY':
            tp1 = entry_price + (risk * 1.5)  # 1:1.5 RR
            tp2 = entry_price + (risk * 2.5)  # 1:2.5 RR
            tp3 = entry_price + (risk * 4.0)  # 1:4 RR
        else:
            tp1 = entry_price - (risk * 1.5)
            tp2 = entry_price - (risk * 2.5)
            tp3 = entry_price - (risk * 4.0)
        
        position_exit = PositionExit(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            current_price=entry_price,
            entry_time=entry_time,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            remaining_size=100.0,
            breakeven_moved=False,
            trailing_stop_active=False,
            trailing_stop_price=None,
            exits_taken=[],
            initial_stop_loss=float(stop_loss),
            initial_risk=float(max(risk, 1e-10)),
            stop_adjustments_used=0,
        )
        
        self.active_exits[symbol] = position_exit
        
        return position_exit
    
    def check_exits(self, symbol: str, current_price: float,
                   market_data: pd.DataFrame,
                   correlation_changed: bool = False) -> List[ExitSignal]:
        """
        Check all exit triggers for position
        
        Args:
            symbol: Trading symbol
            current_price: Current market price
            market_data: Recent market data
            correlation_changed: Flag if correlation significantly changed
            
        Returns:
            List of exit signals
        """
        if symbol not in self.active_exits:
            return []
        
        position = self.active_exits[symbol]
        position.current_price = current_price
        
        exit_signals = []

        # 0. Defensive stop adjustment (risk-aware SL widening before hard stop)
        adjust_signal = self._check_stop_adjustment(position, market_data)
        if adjust_signal:
            exit_signals.append(adjust_signal)
            return exit_signals
        
        # 1. Check stop loss
        sl_signal = self._check_stop_loss(position)
        if sl_signal:
            exit_signals.append(sl_signal)
            return exit_signals  # Stop loss = immediate full exit
        
        # 2. Check profit targets
        tp_signals = self._check_profit_targets(position)
        exit_signals.extend(tp_signals)
        
        # Minimum hold time gate: skip discretionary exits for very young positions
        _age_secs = (datetime.now() - position.entry_time).total_seconds()
        _past_hold_gate = _age_secs >= self.min_hold_seconds

        # 3. Check trailing stop (only after min hold)
        if self.use_trailing_stops and _past_hold_gate:
            trailing_signal = self._check_trailing_stop(position, market_data)
            if trailing_signal:
                exit_signals.append(trailing_signal)
        
        # 4. Check time-based exit
        time_signal = self._check_time_exit(position)
        if time_signal:
            exit_signals.append(time_signal)
        
        # 5. Check technical exits (only after min hold)
        if _past_hold_gate:
            tech_signals = self._check_technical_exits(position, market_data)
            exit_signals.extend(tech_signals)
        
        # 6. Check correlation exit (only after min hold)
        if correlation_changed and _past_hold_gate:
            corr_signal = self._check_correlation_exit(position)
            if corr_signal:
                exit_signals.append(corr_signal)
        
        # 7. Check volatility exit (only after min hold)
        if _past_hold_gate:
            vol_signal = self._check_volatility_exit(position, market_data)
            if vol_signal:
                exit_signals.append(vol_signal)
        
        # 8. Move to breakeven if appropriate (ATR-based threshold)
        exit_atr = None
        if market_data is not None and len(market_data) >= 14:
            try:
                _h = market_data['high'].values
                _l = market_data['low'].values
                _c = market_data['close'].values
                _tr = np.maximum(_h - _l, np.maximum(np.abs(_h - np.roll(_c, 1)), np.abs(_l - np.roll(_c, 1))))
                exit_atr = float(np.mean(_tr[-14:]))
            except Exception:
                pass
        be_signal = self._check_breakeven_move(position, atr=exit_atr)
        if be_signal:
            exit_signals.append(be_signal)
        
        return exit_signals
    
    def _check_stop_loss(self, position: PositionExit) -> Optional[ExitSignal]:
        """Check if stop loss hit"""
        current_price = position.current_price
        
        # Use trailing stop if active
        stop_price = position.trailing_stop_price if position.trailing_stop_active else position.stop_loss
        
        if position.direction == 'BUY':
            if current_price <= stop_price:
                return ExitSignal(
                    trigger_type=ExitTrigger.STOP_LOSS,
                    exit_percentage=100.0,
                    exit_price=current_price,
                    confidence=100.0,
                    reason=f"Stop loss hit at {stop_price:.5f}",
                    timestamp=datetime.now()
                )
        else:
            if current_price >= stop_price:
                return ExitSignal(
                    trigger_type=ExitTrigger.STOP_LOSS,
                    exit_percentage=100.0,
                    exit_price=current_price,
                    confidence=100.0,
                    reason=f"Stop loss hit at {stop_price:.5f}",
                    timestamp=datetime.now()
                )
        
        return None

    def _check_stop_adjustment(
        self,
        position: PositionExit,
        market_data: pd.DataFrame,
    ) -> Optional[ExitSignal]:
        """Apply one-time defensive SL widening when probability of recovery is acceptable."""
        if not self.enable_defensive_stop_adjustment:
            return None
        if self.max_stop_adjustments <= 0:
            return None
        if position.stop_adjustments_used >= self.max_stop_adjustments:
            return None
        if position.trailing_stop_active or position.breakeven_moved:
            return None
        if market_data is None or len(market_data) < 25:
            return None

        active_stop = float(position.stop_loss)
        current_price = float(position.current_price)
        if active_stop <= 0:
            return None

        atr = max(float(self._calculate_atr(market_data, period=14) or 0.0), 1e-10)
        trigger_distance = max(atr * self.adjustment_trigger_atr_fraction, abs(position.entry_price) * 0.00015)

        if position.direction == 'BUY':
            if current_price <= active_stop:
                return None
            distance_to_stop = current_price - active_stop
        else:
            if current_price >= active_stop:
                return None
            distance_to_stop = active_stop - current_price

        if distance_to_stop > trigger_distance:
            return None

        recovery_score = self._estimate_recovery_score(position, market_data)
        if recovery_score < self.min_recovery_score:
            return None

        initial_risk = float(max(position.initial_risk, 1e-10))
        extension_by_atr = atr * self.max_extension_atr
        extension_by_risk = initial_risk * self.max_extension_r_multiple
        extension = max(0.0, min(extension_by_atr, extension_by_risk))
        if extension <= 0:
            return None

        max_allowed_risk = initial_risk * (1.0 + self.max_extension_r_multiple)
        if position.direction == 'BUY':
            proposed_stop = active_stop - extension
            floor_stop = float(position.entry_price) - max_allowed_risk
            proposed_stop = max(proposed_stop, floor_stop)
            if proposed_stop >= active_stop:
                return None
        else:
            proposed_stop = active_stop + extension
            cap_stop = float(position.entry_price) + max_allowed_risk
            proposed_stop = min(proposed_stop, cap_stop)
            if proposed_stop <= active_stop:
                return None

        next_usage = int(position.stop_adjustments_used) + 1

        return ExitSignal(
            trigger_type=ExitTrigger.STOP_ADJUSTMENT,
            exit_percentage=0.0,
            exit_price=float(proposed_stop),
            confidence=float(max(0.0, min(recovery_score * 100.0, 100.0))),
            reason=(
                f"Defensive SL adjustment -> {float(proposed_stop):.5f} "
                f"(score={recovery_score:.2f}, usage={next_usage}/{self.max_stop_adjustments})"
            ),
            timestamp=datetime.now(),
        )

    def _estimate_recovery_score(self, position: PositionExit, market_data: pd.DataFrame) -> float:
        """Estimate short-term probability of bounce/recovery near stop zone (0..1)."""
        if market_data is None or len(market_data) < 25:
            return 0.0

        closes = market_data['close']
        highs = market_data['high']
        lows = market_data['low']
        opens = market_data['open'] if 'open' in market_data.columns else closes

        rsi = float(self._calculate_rsi(market_data, period=14) or 50.0)
        ema_fast = float(closes.ewm(span=9, adjust=False).mean().iloc[-1])
        ema_slow = float(closes.ewm(span=21, adjust=False).mean().iloc[-1])
        last_close = float(closes.iloc[-1])
        prev_close = float(closes.iloc[-2])
        prev2_close = float(closes.iloc[-3])
        last_open = float(opens.iloc[-1])
        last_high = float(highs.iloc[-1])
        last_low = float(lows.iloc[-1])

        body = abs(last_close - last_open)
        candle_range = max(last_high - last_low, 1e-10)
        lower_wick = min(last_open, last_close) - last_low
        upper_wick = last_high - max(last_open, last_close)

        score = 0.0
        direction = str(position.direction or '').upper()
        if direction == 'BUY':
            if rsi <= 35:
                score += 0.30
            if last_close > prev_close:
                score += 0.22
            if prev_close > prev2_close:
                score += 0.08
            if ema_fast >= ema_slow:
                score += 0.20
            if lower_wick > max(body * 1.2, candle_range * 0.20):
                score += 0.20
        else:
            if rsi >= 65:
                score += 0.30
            if last_close < prev_close:
                score += 0.22
            if prev_close < prev2_close:
                score += 0.08
            if ema_fast <= ema_slow:
                score += 0.20
            if upper_wick > max(body * 1.2, candle_range * 0.20):
                score += 0.20

        return float(max(0.0, min(score, 1.0)))
    
    def _check_profit_targets(self, position: PositionExit) -> List[ExitSignal]:
        """Check if profit targets hit"""
        if not self.use_partial_exits:
            return []
        
        signals = []
        current_price = position.current_price
        
        # Check TP1 (take 50% profit)
        tp1_taken = any(e.trigger_type == ExitTrigger.PROFIT_TARGET and 'TP1' in e.reason 
                       for e in position.exits_taken)
        
        if not tp1_taken:
            if (position.direction == 'BUY' and current_price >= position.take_profit_1) or \
               (position.direction == 'SELL' and current_price <= position.take_profit_1):
                signals.append(ExitSignal(
                    trigger_type=ExitTrigger.PROFIT_TARGET,
                    exit_percentage=50.0,
                    exit_price=position.take_profit_1,
                    confidence=100.0,
                    reason=f"TP1 hit at {position.take_profit_1:.5f}",
                    timestamp=datetime.now()
                ))
        
        # Check TP2 (take 30% more)
        tp2_taken = any(e.trigger_type == ExitTrigger.PROFIT_TARGET and 'TP2' in e.reason 
                       for e in position.exits_taken)
        
        if not tp2_taken and tp1_taken:
            if (position.direction == 'BUY' and current_price >= position.take_profit_2) or \
               (position.direction == 'SELL' and current_price <= position.take_profit_2):
                signals.append(ExitSignal(
                    trigger_type=ExitTrigger.PROFIT_TARGET,
                    exit_percentage=30.0,
                    exit_price=position.take_profit_2,
                    confidence=100.0,
                    reason=f"TP2 hit at {position.take_profit_2:.5f}",
                    timestamp=datetime.now()
                ))
        
        # Check TP3 (take remaining 20%)
        if position.take_profit_3:
            tp3_taken = any(e.trigger_type == ExitTrigger.PROFIT_TARGET and 'TP3' in e.reason 
                           for e in position.exits_taken)
            
            if not tp3_taken and tp2_taken:
                if (position.direction == 'BUY' and current_price >= position.take_profit_3) or \
                   (position.direction == 'SELL' and current_price <= position.take_profit_3):
                    signals.append(ExitSignal(
                        trigger_type=ExitTrigger.PROFIT_TARGET,
                        exit_percentage=20.0,
                        exit_price=position.take_profit_3,
                        confidence=100.0,
                        reason=f"TP3 hit at {position.take_profit_3:.5f}",
                        timestamp=datetime.now()
                    ))
        
        return signals
    
    def _check_trailing_stop(self, position: PositionExit,
                            market_data: pd.DataFrame) -> Optional[ExitSignal]:
        """
        Progressive trailing stop (inspired by GPS Robot / Waka Waka).
        Tightens the trailing distance as profit grows:
        - At 1R profit: trail at 2.0 ATR (wide, let trade breathe)
        - At 2R profit: trail at 1.5 ATR (moderate lock-in)
        - At 3R+ profit: trail at 1.0 ATR (tight, protect gains)
        """
        if len(market_data) < 14:
            return None
        
        # Calculate ATR for trailing stop distance
        atr = self._calculate_atr(market_data)
        
        current_price = position.current_price
        entry_price = position.entry_price
        initial_risk = abs(entry_price - position.initial_stop_loss)
        
        # Activate trailing stop after TP1
        tp1_taken = any(e.trigger_type == ExitTrigger.PROFIT_TARGET and 'TP1' in e.reason 
                       for e in position.exits_taken)
        
        if not tp1_taken:
            return None
        
        if not position.trailing_stop_active:
            position.trailing_stop_active = True
        
        # Calculate current profit in R-multiples
        profit_distance = abs(current_price - entry_price)
        r_multiple = (profit_distance / initial_risk) if initial_risk > 0 else 1.0
        
        # Progressive trailing: tighten as profit grows
        if r_multiple >= 3.0:
            trail_atr_mult = 1.0   # Tight: protect large gains
        elif r_multiple >= 2.0:
            trail_atr_mult = 1.5   # Moderate: good profit lock
        else:
            trail_atr_mult = 2.0   # Wide: let trade breathe
        
        trailing_distance = atr * trail_atr_mult
        
        # Update trailing stop
        if position.direction == 'BUY':
            new_stop = current_price - trailing_distance
            
            # Only move stop up, never down
            if position.trailing_stop_price is None or new_stop > position.trailing_stop_price:
                position.trailing_stop_price = new_stop
        else:
            new_stop = current_price + trailing_distance
            
            # Only move stop down, never up
            if position.trailing_stop_price is None or new_stop < position.trailing_stop_price:
                position.trailing_stop_price = new_stop
        
        return None  # Trailing stop doesn't generate exit signal, just updates stop level
    
    def _check_time_exit(self, position: PositionExit) -> Optional[ExitSignal]:
        """Check if position held too long"""
        hours_held = (datetime.now() - position.entry_time).total_seconds() / 3600
        
        if hours_held > self.max_hold_hours:
            return ExitSignal(
                trigger_type=ExitTrigger.TIME_EXIT,
                exit_percentage=100.0,
                exit_price=position.current_price,
                confidence=80.0,
                reason=f"Time exit: {hours_held:.1f} hours held (max: {self.max_hold_hours})",
                timestamp=datetime.now()
            )
        
        return None
    
    def _check_technical_exits(self, position: PositionExit,
                               market_data: pd.DataFrame) -> List[ExitSignal]:
        """Check technical indicator exit signals"""
        signals = []
        
        if len(market_data) < 20:
            return signals
        
        # RSI overbought/oversold
        rsi = self._calculate_rsi(market_data)
        
        if position.direction == 'BUY' and rsi > 75:
            signals.append(ExitSignal(
                trigger_type=ExitTrigger.TECHNICAL_EXIT,
                exit_percentage=25.0,
                exit_price=position.current_price,
                confidence=70.0,
                reason=f"RSI overbought ({rsi:.1f})",
                timestamp=datetime.now()
            ))
        elif position.direction == 'SELL' and rsi < 25:
            signals.append(ExitSignal(
                trigger_type=ExitTrigger.TECHNICAL_EXIT,
                exit_percentage=25.0,
                exit_price=position.current_price,
                confidence=70.0,
                reason=f"RSI oversold ({rsi:.1f})",
                timestamp=datetime.now()
            ))
        
        # MACD divergence
        divergence = self._check_macd_divergence(market_data, position.direction)
        if divergence:
            signals.append(ExitSignal(
                trigger_type=ExitTrigger.TECHNICAL_EXIT,
                exit_percentage=30.0,
                exit_price=position.current_price,
                confidence=75.0,
                reason="MACD divergence detected",
                timestamp=datetime.now()
            ))
        
        return signals
    
    def _check_correlation_exit(self, position: PositionExit) -> Optional[ExitSignal]:
        """Exit if correlation structure changed"""
        return ExitSignal(
            trigger_type=ExitTrigger.CORRELATION_EXIT,
            exit_percentage=50.0,
            exit_price=position.current_price,
            confidence=60.0,
            reason="Correlation structure changed",
            timestamp=datetime.now()
        )
    
    def _check_volatility_exit(self, position: PositionExit,
                               market_data: pd.DataFrame) -> Optional[ExitSignal]:
        """Exit if volatility spikes abnormally"""
        if len(market_data) < 20:
            return None
        
        current_atr = self._calculate_atr(market_data, period=5)  # Recent ATR
        avg_atr = self._calculate_atr(market_data, period=20)  # Average ATR
        
        # If current volatility > 2x average
        if current_atr > avg_atr * 2:
            return ExitSignal(
                trigger_type=ExitTrigger.VOLATILITY_EXIT,
                exit_percentage=40.0,
                exit_price=position.current_price,
                confidence=65.0,
                reason=f"Volatility spike: {current_atr/avg_atr:.1f}x normal",
                timestamp=datetime.now()
            )
        
        return None
    
    def _check_breakeven_move(self, position: PositionExit, atr: Optional[float] = None) -> Optional[ExitSignal]:
        """Move stop to breakeven after certain profit"""
        if position.breakeven_moved:
            return None
        
        current_price = position.current_price
        entry_price = position.entry_price
        stop_distance = abs(entry_price - position.initial_stop_loss)
        
        # CRITICAL: Use ATR-based or risk-based threshold instead of hardcoded pips
        # Trigger breakeven after 0.5R (half of initial risk) or 1.0 ATR, whichever is available
        breakeven_threshold = 0.0
        
        if atr is not None and atr > 0:
            # ATR-based: move to breakeven after 1.0 ATR profit
            breakeven_threshold = atr * 1.0
        elif stop_distance > 0:
            # Risk-based: move to breakeven after 0.5R profit (half of initial risk)
            breakeven_threshold = stop_distance * 0.5
        else:
            # Fallback: use current price distance (50% of stop distance)
            breakeven_threshold = abs(current_price - entry_price) * 0.5
        
        profit_distance = abs(current_price - entry_price)
        
        # Move to breakeven if profit exceeds threshold
        if profit_distance > breakeven_threshold:
            if position.direction == 'BUY':
                if current_price > entry_price:
                    return ExitSignal(
                        trigger_type=ExitTrigger.BREAKEVEN,
                        exit_percentage=0.0,  # Don't exit, just move stop
                        exit_price=entry_price,
                        confidence=100.0,
                        reason=f"Stop moved to breakeven at {entry_price:.5f}",
                        timestamp=datetime.now()
                    )
            else:
                if current_price < entry_price:
                    return ExitSignal(
                        trigger_type=ExitTrigger.BREAKEVEN,
                        exit_percentage=0.0,
                        exit_price=entry_price,
                        confidence=100.0,
                        reason=f"Stop moved to breakeven at {entry_price:.5f}",
                        timestamp=datetime.now()
                    )
        
        return None
    
    def execute_exit(self, symbol: str, exit_signal: ExitSignal):
        """Execute exit and update position state"""
        if symbol not in self.active_exits:
            return
        
        position = self.active_exits[symbol]
        
        # Record exit
        position.exits_taken.append(exit_signal)

        # Non-closing stop adjustment applies updated SL without reducing position size.
        if exit_signal.trigger_type in (ExitTrigger.STOP_ADJUSTMENT, ExitTrigger.BREAKEVEN):
            position.stop_loss = float(exit_signal.exit_price)
            if exit_signal.trigger_type == ExitTrigger.STOP_ADJUSTMENT:
                position.stop_adjustments_used += 1
            else:
                position.breakeven_moved = True
            return
        
        # Update remaining size with validation to prevent negative values
        if exit_signal.exit_percentage > 0:
            # CRITICAL: Ensure remaining size never goes negative
            position.remaining_size = max(0.0, position.remaining_size - exit_signal.exit_percentage)
        
        # Remove if fully closed
        if position.remaining_size <= 5:  # Close position if < 5% remaining
            del self.active_exits[symbol]
    
    # Helper methods
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr.iloc[-1] if not pd.isna(atr.iloc[-1]) else 0
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def _check_macd_divergence(self, df: pd.DataFrame, direction: str) -> bool:
        """Check for MACD divergence"""
        if len(df) < 50:
            return False
        
        # Calculate MACD
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        
        # Simplified divergence check
        # Price making higher highs but MACD making lower highs = bearish divergence
        if direction == 'BUY':
            price_higher_high = df['high'].iloc[-1] > df['high'].iloc[-10:].max()
            macd_lower_high = macd.iloc[-1] < macd.iloc[-10:-1].max()
            
            return price_higher_high and macd_lower_high
        
        # Price making lower lows but MACD making higher lows = bullish divergence
        else:
            price_lower_low = df['low'].iloc[-1] < df['low'].iloc[-10:].min()
            macd_higher_low = macd.iloc[-1] > macd.iloc[-10:-1].min()
            
            return price_lower_low and macd_higher_low
    
    def get_exit_summary(self, symbol: str) -> Optional[Dict]:
        """Get exit plan summary for symbol"""
        if symbol not in self.active_exits:
            return None
        
        position = self.active_exits[symbol]
        
        return {
            'symbol': symbol,
            'direction': position.direction,
            'entry_price': position.entry_price,
            'current_price': position.current_price,
            'remaining_size': position.remaining_size,
            'stop_loss': position.trailing_stop_price if position.trailing_stop_active else position.stop_loss,
            'stop_adjustments_used': position.stop_adjustments_used,
            'breakeven_moved': position.breakeven_moved,
            'trailing_active': position.trailing_stop_active,
            'exits_taken': len(position.exits_taken),
            'profit_targets': {
                'tp1': position.take_profit_1,
                'tp2': position.take_profit_2,
                'tp3': position.take_profit_3
            }
        }
