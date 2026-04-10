"""
APEX FX Trading Bot - Kelly Sizer
PRD Volume II Section 12: Kelly Criterion Position Sizing

Computes fractional Kelly risk percentage based on rolling live trade performance.
Only activates after minimum trade count threshold per instrument.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import threading


class KellySizer:
    """
    Kelly Sizer - computes fractional Kelly risk percentage.
    
    Instrument parameters (per PRD Vol II):
    - lookback: Number of trades to consider
    - min_floor: Minimum risk % (cannot go below this)
    - max_cap: Maximum risk % (cannot exceed this)
    - activation_trades: Minimum trades before Kelly activates
    
    Uses 25% fractional Kelly (conservative).
    """
    
    INSTRUMENT_PARAMS = {
        'EURUSD': {'lookback': 50, 'min_floor': 0.5, 'max_cap': 2.0, 'activation_trades': 30},
        'GBPUSD': {'lookback': 50, 'min_floor': 0.4, 'max_cap': 1.8, 'activation_trades': 30},
        'USDJPY': {'lookback': 50, 'min_floor': 0.5, 'max_cap': 2.0, 'activation_trades': 30},
        'USDCHF': {'lookback': 40, 'min_floor': 0.3, 'max_cap': 1.5, 'activation_trades': 25},
        'USDCAD': {'lookback': 50, 'min_floor': 0.4, 'max_cap': 1.8, 'activation_trades': 30},
        'XAUUSD': {'lookback': 30, 'min_floor': 0.25, 'max_cap': 1.0, 'activation_trades': 20},
    }
    
    KELLY_FRACTION = 0.25  # Use 25% of full Kelly — conservative fractional Kelly
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize Kelly sizer.
        
        Args:
            config: Optional configuration
            logger: Optional logger
        """
        self._lock = threading.Lock()
        self._config = config or {}
        self._logger = logger
        
        # Cold streak tracking
        self._consecutive_losses: Dict[str, int] = {}
        self._ladder_trades_remaining: Dict[str, int] = {}
    
    def get_effective_risk_pct(
        self, 
        symbol: str, 
        db
    ) -> float:
        """
        Compute effective risk % for next trade on symbol.
        
        If live trade count < activation_trades: return Vol I fixed risk.
        Otherwise: compute Kelly from last N trades, apply 25% fraction,
        clamp to floor/cap.
        
        Args:
            symbol: Trading symbol
            db: Database instance
            
        Returns:
            Effective risk percentage
        """
        params = self.INSTRUMENT_PARAMS.get(symbol, self.INSTRUMENT_PARAMS['EURUSD'])
        
        # Get recent trades for this symbol
        with self._lock:
            trades = self._get_recent_trades(symbol, params['lookback'], db)
            
            if len(trades) < params['activation_trades']:
                # Use fixed risk from Vol I
                fixed_risks = {
                    'EURUSD': 1.5, 'GBPUSD': 1.2, 'USDJPY': 1.5,
                    'USDCHF': 1.0, 'USDCAD': 1.2, 'XAUUSD': 0.75
                }
                return fixed_risks.get(symbol, 1.0)
            
            # Compute Kelly
            win_rate, avg_win_r, avg_loss_r = self._calculate_stats(trades)
            
            if win_rate <= 0 or avg_loss_r <= 0:
                return params['min_floor']
            
            full_kelly = self._compute_kelly(win_rate, avg_win_r, avg_loss_r)
            
            if full_kelly <= 0:
                return params['min_floor']
            
            # Apply fractional Kelly
            fractional_kelly = full_kelly * self.KELLY_FRACTION
            
            # Clamp to floor/cap
            effective_risk = max(params['min_floor'], min(params['max_cap'], fractional_kelly))
            
            return effective_risk
    
    def _get_recent_trades(
        self, 
        symbol: str, 
        lookback: int, 
        db
    ) -> list:
        """Get recent closed trades for symbol."""
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT profit, status FROM trades 
            WHERE symbol = ? AND status = 'CLOSED'
            ORDER BY closed_at DESC LIMIT ?
        """, (symbol, lookback))
        
        return cursor.fetchall()
    
    def _calculate_stats(self, trades: list) -> Tuple[float, float, float]:
        """
        Calculate win rate, avg win R, avg loss R from trades.
        
        Returns:
            Tuple of (win_rate, avg_win_r, avg_loss_r)
        """
        if not trades:
            return 0.0, 0.0, 0.0
        
        wins = []
        losses = []
        
        for trade in trades:
            profit = trade[0] if trade[0] else 0
            if profit > 0:
                wins.append(profit)
            elif profit < 0:
                losses.append(abs(profit))
        
        total = len(wins) + len(losses)
        if total == 0:
            return 0.0, 0.0, 0.0
        
        win_rate = len(wins) / total
        
        avg_win_r = sum(wins) / len(wins) if wins else 0
        avg_loss_r = sum(losses) / len(losses) if losses else 0
        
        return win_rate, avg_win_r, avg_loss_r
    
    def _compute_kelly(
        self, 
        win_rate: float, 
        avg_win_r: float, 
        avg_loss_r: float
    ) -> float:
        """
        Kelly formula: f* = (W * R - (1 - W)) / R
        where W=win_rate, R=avg_win/avg_loss (reward:risk ratio).
        
        Returns 0.0 if result is negative (negative edge).
        """
        if avg_loss_r <= 0:
            return 0.0
        
        win_rate_decimal = win_rate
        reward_risk_ratio = avg_win_r / avg_loss_r if avg_loss_r > 0 else 0
        
        kelly = (win_rate_decimal * reward_risk_ratio - (1 - win_rate_decimal)) / reward_risk_ratio
        
        return max(0, kelly)
    
    def recalculate_and_store(
        self, 
        symbol: str, 
        db
    ) -> Dict:
        """
        Run weekly recalculation and write result to kelly_history table.
        
        Args:
            symbol: Trading symbol
            db: Database instance
            
        Returns:
            Dict with Kelly calculation results
        """
        params = self.INSTRUMENT_PARAMS.get(symbol, self.INSTRUMENT_PARAMS['EURUSD'])
        
        trades = self._get_recent_trades(symbol, params['lookback'], db)
        
        if len(trades) < params['activation_trades']:
            return {'status': 'insufficient_trades', 'count': len(trades)}
        
        win_rate, avg_win_r, avg_loss_r = self._calculate_stats(trades)
        
        full_kelly = self._compute_kelly(win_rate, avg_win_r, avg_loss_r)
        fractional_kelly = full_kelly * self.KELLY_FRACTION
        effective_risk = max(params['min_floor'], min(params['max_cap'], fractional_kelly))
        
        # Store in database
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO kelly_history (
                calculated_at, symbol, lookback_trades, win_rate, 
                avg_win_r, avg_loss_r, full_kelly, fractional_kelly, effective_risk_pct
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            symbol,
            len(trades),
            win_rate,
            avg_win_r,
            avg_loss_r,
            full_kelly,
            fractional_kelly,
            effective_risk
        ))
        db.conn.commit()
        
        return {
            'status': 'success',
            'symbol': symbol,
            'lookback_trades': len(trades),
            'win_rate': win_rate,
            'full_kelly': full_kelly,
            'fractional_kelly': fractional_kelly,
            'effective_risk_pct': effective_risk
        }
    
    def apply_cold_streak_ladder(
        self, 
        symbol: str, 
        base_risk_pct: float, 
        db
    ) -> float:
        """
        Cold streak ladder from PRD Vol II Section 12.3:
        - 3 consecutive losses: * 0.75 for 5 trades
        - 5 consecutive losses: * 0.50 for 8 trades
        - 7+ consecutive losses: pair suspended — return 0.0
        
        Args:
            symbol: Trading symbol
            base_risk_pct: Base risk percentage
            db: Database instance
            
        Returns:
            Adjusted risk percentage
        """
        with self._lock:
            # Check if we're in a ladder period
            if symbol in self._ladder_trades_remaining:
                self._ladder_trades_remaining[symbol] -= 1
                if self._ladder_trades_remaining[symbol] <= 0:
                    del self._ladder_trades_remaining[symbol]
                return base_risk_pct
            
            # Get recent trades to check for consecutive losses
            trades = self._get_recent_trades(symbol, 10, db)
            
            consecutive_losses = 0
            for trade in trades:
                if (trade[0] or 0) < 0:
                    consecutive_losses += 1
                else:
                    break
            
            # Apply ladder
            if consecutive_losses >= 7:
                return 0.0  # Suspend pair
            elif consecutive_losses >= 5:
                self._ladder_trades_remaining[symbol] = 8
                return base_risk_pct * 0.50
            elif consecutive_losses >= 3:
                self._ladder_trades_remaining[symbol] = 5
                return base_risk_pct * 0.75
            
            return base_risk_pct


# Global instance
_kelly_sizer = None


def get_kelly_sizer(config: Optional[Dict] = None, logger=None) -> KellySizer:
    """Get global Kelly sizer instance."""
    global _kelly_sizer
    if _kelly_sizer is None:
        _kelly_sizer = KellySizer(config, logger)
    return _kelly_sizer