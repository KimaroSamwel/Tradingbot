"""
SMART TRADE FILTER
Research-based intelligent trade filtering inspired by top trading bots.

Implements features from:
- Forex Fury: Low-volatility session filtering, trade frequency limits
- Waka Waka EA: Adaptive risk scaling, drawdown recovery mode
- GPS Forex Robot: Session-aware strategy confidence
- ODIN: Multi-pair daily trade distribution
- Tickeron: Performance-adaptive thresholds

Features:
1. Trade frequency limiter (max trades per day/session)
2. Adaptive risk scaling (reduce after losses, recover after wins)
3. Volatility regime filter (optimal volatility windows only)
4. Post-loss cooldown (anti-revenge trading)
5. Session performance tracking
6. Equity curve-based position sizing
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class TradeRecord:
    """Lightweight record of a recent trade for filtering decisions."""
    symbol: str
    direction: str
    timestamp: datetime
    pnl: float = 0.0
    closed: bool = False
    strategy: str = ""


@dataclass
class SessionStats:
    """Track per-session trading statistics."""
    trades_opened: int = 0
    wins: int = 0
    losses: int = 0
    total_pnl: float = 0.0
    last_trade_time: Optional[datetime] = None
    consecutive_losses: int = 0
    consecutive_wins: int = 0


class SmartTradeFilter:
    """
    Intelligent pre-trade filter that applies research-based rules
    from top trading bots to improve win rate and prevent overtrading.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.logger = logging.getLogger('SmartTradeFilter')
        cfg = config or {}

        # ── Trade Frequency Limits (Forex Fury: 0-7 trades per session) ──
        self.max_trades_per_day = int(cfg.get('max_trades_per_day', 20))
        self.max_trades_per_session = int(cfg.get('max_trades_per_session', 12))
        self.max_trades_per_symbol_per_day = int(cfg.get('max_trades_per_symbol_per_day', 5))

        # ── Post-Loss Cooldown (Anti-revenge trading) ──
        self.post_loss_cooldown_minutes = int(cfg.get('post_loss_cooldown_minutes', 15))
        self.consecutive_loss_cooldown_minutes = int(cfg.get('consecutive_loss_cooldown_minutes', 45))
        self.max_consecutive_losses_before_pause = int(cfg.get('max_consecutive_losses_before_pause', 3))

        # ── Adaptive Risk Scaling (Waka Waka stability) ──
        self.enable_adaptive_scaling = bool(cfg.get('enable_adaptive_scaling', True))
        self.base_risk_multiplier = 1.0
        self.min_risk_multiplier = float(cfg.get('min_risk_multiplier', 0.25))
        self.max_risk_multiplier = float(cfg.get('max_risk_multiplier', 1.5))
        self.loss_scale_factor = float(cfg.get('loss_scale_factor', 0.7))
        self.win_recovery_factor = float(cfg.get('win_recovery_factor', 1.15))

        # ── Volatility Regime Filter (Forex Fury: low-vol only) ──
        self.enable_volatility_filter = bool(cfg.get('enable_volatility_filter', True))
        self.optimal_vol_min = float(cfg.get('optimal_volatility_min', 0.3))
        self.optimal_vol_max = float(cfg.get('optimal_volatility_max', 2.5))

        # ── Equity Curve Filter ──
        self.enable_equity_curve_filter = bool(cfg.get('enable_equity_curve_filter', True))
        self.equity_sma_period = int(cfg.get('equity_sma_period', 10))

        # ── Session Definitions (broker time UTC+3) ──
        self.sessions = {
            'ASIAN': {'start': 0, 'end': 8, 'quality': 'LOW'},
            'LONDON': {'start': 8, 'end': 16, 'quality': 'HIGH'},
            'NEW_YORK': {'start': 13, 'end': 21, 'quality': 'HIGH'},
            'OVERLAP': {'start': 13, 'end': 16, 'quality': 'BEST'},
            'OFF_HOURS': {'start': 21, 'end': 24, 'quality': 'LOW'},
        }

        # ── State Tracking ──
        self.today_trades: List[TradeRecord] = []
        self.session_stats: Dict[str, SessionStats] = defaultdict(SessionStats)
        self.symbol_trades_today: Dict[str, int] = defaultdict(int)
        self.last_loss_time: Optional[datetime] = None
        self.consecutive_losses = 0
        self.consecutive_wins = 0
        self.current_risk_multiplier = 1.0
        self.equity_history: List[float] = []
        self.last_reset_date: Optional[datetime] = None

        self.enabled = bool(cfg.get('enabled', True))

    def can_trade(self, symbol: str, direction: str,
                  strategy: str = "",
                  volatility_ratio: float = 1.0,
                  current_equity: float = 0.0,
                  is_synthetic: bool = False) -> Tuple[bool, str, float]:
        """
        Main filter method. Returns (allowed, reason, risk_multiplier).
        
        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            strategy: Strategy name
            volatility_ratio: Current fast_ATR / slow_ATR ratio
            current_equity: Current account equity
            is_synthetic: Whether this is a synthetic index
            
        Returns:
            (can_trade, reason_if_blocked, risk_multiplier)
        """
        if not self.enabled:
            return True, 'filter_disabled', 1.0

        self._auto_reset_daily()

        now = datetime.now(timezone.utc) + timedelta(hours=3)  # Broker time

        # 1. Trade frequency check
        freq_ok, freq_reason = self._check_trade_frequency(symbol, now)
        if not freq_ok:
            return False, freq_reason, 0.0

        # 2. Post-loss cooldown
        cool_ok, cool_reason = self._check_post_loss_cooldown(now)
        if not cool_ok:
            return False, cool_reason, 0.0

        # 3. Consecutive loss pause
        if self.consecutive_losses >= self.max_consecutive_losses_before_pause:
            cooldown_end = (
                self.last_loss_time + timedelta(minutes=self.consecutive_loss_cooldown_minutes)
                if self.last_loss_time else now
            )
            if now < cooldown_end:
                remaining = (cooldown_end - now).total_seconds() / 60
                return False, (
                    f"consecutive_loss_pause:{self.consecutive_losses}_losses:"
                    f"{remaining:.0f}min_remaining"
                ), 0.0

        # 4. Volatility regime filter (skip for synthetics - different dynamics)
        if self.enable_volatility_filter and not is_synthetic:
            vol_ok, vol_reason = self._check_volatility_regime(volatility_ratio)
            if not vol_ok:
                return False, vol_reason, 0.0

        # 5. Equity curve filter
        if self.enable_equity_curve_filter and current_equity > 0:
            eq_ok, eq_reason = self._check_equity_curve(current_equity)
            if not eq_ok:
                return False, eq_reason, 0.0

        # 6. Calculate adaptive risk multiplier
        risk_mult = self._get_adaptive_risk_multiplier(volatility_ratio, now)

        return True, 'pass', risk_mult

    def record_trade_opened(self, symbol: str, direction: str,
                            strategy: str = ""):
        """Record that a new trade was opened."""
        now = datetime.now(timezone.utc) + timedelta(hours=3)
        self.today_trades.append(TradeRecord(
            symbol=symbol,
            direction=direction,
            timestamp=now,
            strategy=strategy,
        ))
        self.symbol_trades_today[symbol] = self.symbol_trades_today.get(symbol, 0) + 1

        session = self._get_current_session(now)
        stats = self.session_stats[session]
        stats.trades_opened += 1
        stats.last_trade_time = now

    def record_trade_closed(self, symbol: str, pnl: float):
        """Record trade result for adaptive scaling and cooldown logic."""
        now = datetime.now(timezone.utc) + timedelta(hours=3)

        if pnl < 0:
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.last_loss_time = now

            # Adaptive scaling: reduce risk after loss
            if self.enable_adaptive_scaling:
                self.current_risk_multiplier = max(
                    self.min_risk_multiplier,
                    self.current_risk_multiplier * self.loss_scale_factor
                )
                self.logger.info(
                    f"Loss recorded ({symbol} PnL={pnl:.2f}). "
                    f"Risk multiplier reduced to {self.current_risk_multiplier:.2f}x "
                    f"(consecutive losses: {self.consecutive_losses})"
                )
        else:
            self.consecutive_losses = 0
            self.consecutive_wins += 1

            # Adaptive scaling: gradually recover risk after wins
            if self.enable_adaptive_scaling:
                self.current_risk_multiplier = min(
                    self.max_risk_multiplier,
                    self.current_risk_multiplier * self.win_recovery_factor
                )
                self.logger.info(
                    f"Win recorded ({symbol} PnL=+{pnl:.2f}). "
                    f"Risk multiplier recovered to {self.current_risk_multiplier:.2f}x "
                    f"(consecutive wins: {self.consecutive_wins})"
                )

        session = self._get_current_session(now)
        stats = self.session_stats[session]
        stats.total_pnl += pnl
        if pnl >= 0:
            stats.wins += 1
            stats.consecutive_losses = 0
            stats.consecutive_wins += 1
        else:
            stats.losses += 1
            stats.consecutive_wins = 0
            stats.consecutive_losses += 1

    def record_equity(self, equity: float):
        """Track equity for equity curve filter."""
        self.equity_history.append(equity)
        # Keep only recent history
        if len(self.equity_history) > 100:
            self.equity_history = self.equity_history[-100:]

    # ─── Internal Checks ──────────────────────────────────────────

    def _check_trade_frequency(self, symbol: str,
                               now: datetime) -> Tuple[bool, str]:
        """Enforce trade frequency limits (Forex Fury: max 7 per session)."""
        # Daily limit
        day_count = len(self.today_trades)
        if day_count >= self.max_trades_per_day:
            return False, f"daily_trade_limit:{day_count}/{self.max_trades_per_day}"

        # Per-symbol daily limit
        sym_count = self.symbol_trades_today.get(symbol, 0)
        if sym_count >= self.max_trades_per_symbol_per_day:
            return False, f"symbol_daily_limit:{symbol}:{sym_count}/{self.max_trades_per_symbol_per_day}"

        # Per-session limit (scaled by session quality)
        session = self._get_current_session(now)
        session_count = self.session_stats[session].trades_opened
        quality = self.sessions.get(session, {}).get('quality', 'LOW')
        if quality == 'BEST':
            effective_session_limit = self.max_trades_per_session
        elif quality == 'HIGH':
            effective_session_limit = int(self.max_trades_per_session * 0.8)
        else:
            effective_session_limit = int(self.max_trades_per_session * 0.6)
        effective_session_limit = max(effective_session_limit, 3)  # always allow at least 3
        if session_count >= effective_session_limit:
            return False, f"session_trade_limit:{session}:{session_count}/{effective_session_limit}"

        return True, 'ok'

    def _check_post_loss_cooldown(self, now: datetime) -> Tuple[bool, str]:
        """Enforce cooldown after a losing trade (anti-revenge trading)."""
        if self.last_loss_time is None:
            return True, 'no_recent_loss'

        cooldown = timedelta(minutes=self.post_loss_cooldown_minutes)
        cooldown_end = self.last_loss_time + cooldown

        if now < cooldown_end:
            remaining = (cooldown_end - now).total_seconds() / 60
            return False, f"post_loss_cooldown:{remaining:.0f}min_remaining"

        return True, 'cooldown_expired'

    def _check_volatility_regime(self,
                                 volatility_ratio: float) -> Tuple[bool, str]:
        """
        Filter trades by volatility regime.
        Forex Fury's key: only trade during LOW volatility.
        We allow a wider range but block extremes.
        """
        if volatility_ratio < self.optimal_vol_min:
            return False, (
                f"volatility_too_low:{volatility_ratio:.2f}<{self.optimal_vol_min:.2f}"
            )

        if volatility_ratio > self.optimal_vol_max:
            return False, (
                f"volatility_too_high:{volatility_ratio:.2f}>{self.optimal_vol_max:.2f}"
            )

        return True, 'ok'

    def _check_equity_curve(self, current_equity: float) -> Tuple[bool, str]:
        """
        Equity curve filter: reduce trading when equity is below its SMA.
        Don't block entirely, but flag it (actual blocking controlled by risk multiplier).
        """
        if len(self.equity_history) < self.equity_sma_period:
            return True, 'insufficient_equity_history'

        equity_sma = sum(self.equity_history[-self.equity_sma_period:]) / self.equity_sma_period

        # Adaptive tolerance: micro accounts need wider band because one trade's
        # spread can move equity 5-10% relative to its SMA.
        if equity_sma < 50:
            _tolerance = 0.85   # Micro (<$50): 15% below SMA
        elif equity_sma < 200:
            _tolerance = 0.90   # Small (<$200): 10% below SMA
        else:
            _tolerance = 0.95   # Standard: 5% below SMA

        if current_equity < equity_sma * _tolerance:
            return False, (
                f"equity_below_sma:${current_equity:.2f}<${equity_sma:.2f}*{_tolerance}"
            )

        return True, 'ok'

    def _get_adaptive_risk_multiplier(self, volatility_ratio: float,
                                      now: datetime) -> float:
        """
        Calculate adaptive risk multiplier based on:
        - Recent win/loss streak (Waka Waka stability)
        - Current session quality
        - Volatility regime
        """
        multiplier = self.current_risk_multiplier

        # Session quality adjustment
        session = self._get_current_session(now)
        session_info = self.sessions.get(session, {})
        quality = session_info.get('quality', 'LOW')

        if quality == 'BEST':
            multiplier *= 1.1  # Slight boost during London-NY overlap
        elif quality == 'LOW':
            multiplier *= 0.7  # Reduce during Asian/off-hours

        # Volatility adjustment: reduce in high vol, normal in optimal
        if volatility_ratio > 2.0:
            multiplier *= 0.6
        elif volatility_ratio > 1.5:
            multiplier *= 0.8

        # Clamp
        multiplier = max(self.min_risk_multiplier, min(self.max_risk_multiplier, multiplier))

        return round(multiplier, 3)

    def _get_current_session(self, now: datetime) -> str:
        """Determine current trading session from broker hour."""
        hour = now.hour
        if 13 <= hour < 16:
            return 'OVERLAP'
        if 8 <= hour < 16:
            return 'LONDON'
        if 13 <= hour < 21:
            return 'NEW_YORK'
        if 0 <= hour < 8:
            return 'ASIAN'
        return 'OFF_HOURS'

    def _auto_reset_daily(self):
        """Reset daily counters at start of new trading day."""
        now = datetime.now(timezone.utc) + timedelta(hours=3)
        today = now.date()

        if self.last_reset_date != today:
            self.today_trades = []
            self.symbol_trades_today = defaultdict(int)
            self.session_stats = defaultdict(SessionStats)
            self.last_reset_date = today
            self.logger.info("Smart Trade Filter: daily counters reset")

    # ─── Status / Diagnostics ─────────────────────────────────────

    def get_status(self) -> Dict:
        """Get current filter status for dashboard/logging."""
        now = datetime.now(timezone.utc) + timedelta(hours=3)
        session = self._get_current_session(now)

        return {
            'enabled': self.enabled,
            'current_session': session,
            'session_quality': self.sessions.get(session, {}).get('quality', 'UNKNOWN'),
            'trades_today': len(self.today_trades),
            'max_trades_per_day': self.max_trades_per_day,
            'consecutive_losses': self.consecutive_losses,
            'consecutive_wins': self.consecutive_wins,
            'risk_multiplier': round(self.current_risk_multiplier, 3),
            'adaptive_multiplier': round(
                self._get_adaptive_risk_multiplier(1.0, now), 3
            ),
            'post_loss_cooldown_active': (
                self.last_loss_time is not None and
                (now - self.last_loss_time).total_seconds() < self.post_loss_cooldown_minutes * 60
            ),
            'session_stats': {
                k: {
                    'trades': v.trades_opened,
                    'wins': v.wins,
                    'losses': v.losses,
                    'pnl': round(v.total_pnl, 2),
                }
                for k, v in self.session_stats.items()
            },
            'symbol_trades': dict(self.symbol_trades_today),
        }

    def snapshot(self) -> Dict:
        """Compact snapshot for telemetry."""
        return self.get_status()
