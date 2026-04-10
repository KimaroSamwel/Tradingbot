"""
APEX FX Trading Bot - Regime Drift Detector
PRD Volume II Section 14: RDD (Regime Drift Detection)

Runs every Friday at 21:00 UTC. Compares rolling live performance against
backtest baseline for each instrument and triggers automated responses.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import threading


class RegimeDriftDetector:
    """
    Regime Drift Detector - monitors live vs backtest performance.
    
    Status rules:
    - GREEN (ratio >= 0.70): No action
    - AMBER (0.50 <= ratio < 0.70): Reduce size 60%
    - RED (0 < ratio < 0.50): Suspend pair + re-optimization
    - CRITICAL (ratio = 0 or override): Immediate suspend
    
    Critical override: current week loss > 2x worst backtest week.
    """
    
    STATUS_RULES = {
        'GREEN': {'min_ratio': 0.70, 'action': None},
        'AMBER': {'min_ratio': 0.50, 'action': 'reduce_size_60pct'},
        'RED': {'min_ratio': 0.00, 'action': 'suspend_pair'},
        'CRITICAL': {'min_ratio': 0.00, 'action': 'immediate_suspend'},
    }
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize RDD.
        
        Args:
            config: Optional configuration with 'rdd_baselines'
            logger: Optional logger
        """
        self._lock = threading.Lock()
        self._config = config or {}
        self._logger = logger
        
        # Load baseline profit factors from config
        self._baselines = self._config.get('rdd_baselines', {
            'EURUSD': 1.5, 'GBPUSD': 1.4, 'USDJPY': 1.3,
            'USDCHF': 1.2, 'USDCAD': 1.4, 'XAUUSD': 1.6
        })
        
        # Track suspended symbols
        self._suspended: Dict[str, bool] = {}
        self._size_modifiers: Dict[str, float] = {}
    
    def run_weekly_check(self, db) -> Dict[str, Dict]:
        """
        For each symbol, compute rolling 30-trade profit factor.
        Compare against baseline. Determine status. Execute response.
        
        Args:
            db: Database instance
            
        Returns:
            Dict: {symbol: {status, live_pf, baseline_pf, ratio, action}}
        """
        results = {}
        
        with self._lock:
            for symbol, baseline_pf in self._baselines.items():
                # Skip if already suspended
                if self._suspended.get(symbol, False):
                    results[symbol] = {
                        'status': 'SUSPENDED',
                        'live_pf': 0,
                        'baseline_pf': baseline_pf,
                        'ratio': 0,
                        'action': 'pair_suspended'
                    }
                    continue
                
                # Get rolling profit factor
                live_pf = self._get_rolling_profit_factor(symbol, 30, db)
                
                # Calculate ratio
                ratio = live_pf / baseline_pf if baseline_pf > 0 else 0
                
                # Determine status
                status = self._determine_status(ratio)
                
                # Check critical override
                if self._check_critical_override(symbol, db):
                    status = 'CRITICAL'
                
                # Execute automated response
                action = self._execute_response(symbol, status, self._config)
                
                # Log to database
                self._log_status(symbol, live_pf, baseline_pf, ratio, status, action, db)
                
                results[symbol] = {
                    'status': status,
                    'live_pf': round(live_pf, 3),
                    'baseline_pf': baseline_pf,
                    'ratio': round(ratio, 3),
                    'action': action
                }
        
        return results
    
    def _get_rolling_profit_factor(
        self, 
        symbol: str, 
        last_n: int, 
        db
    ) -> float:
        """
        Sum of winning trade profits / sum of losing trade losses.
        """
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT profit FROM trades
            WHERE symbol = ? AND status = 'CLOSED'
            ORDER BY closed_at DESC LIMIT ?
        """, (symbol, last_n))
        
        trades = cursor.fetchall()
        
        total_wins = 0.0
        total_losses = 0.0
        
        for trade in trades:
            profit = trade[0] or 0
            if profit > 0:
                total_wins += profit
            elif profit < 0:
                total_losses += abs(profit)
        
        if total_losses <= 0:
            return 2.0  # No losses = excellent
        
        return total_wins / total_losses
    
    def _determine_status(self, ratio: float) -> str:
        """Determine status based on ratio."""
        if ratio >= self.STATUS_RULES['GREEN']['min_ratio']:
            return 'GREEN'
        elif ratio >= self.STATUS_RULES['AMBER']['min_ratio']:
            return 'AMBER'
        elif ratio > 0:
            return 'RED'
        else:
            return 'CRITICAL'
    
    def _execute_response(
        self, 
        symbol: str, 
        status: str, 
        config: Dict
    ) -> str:
        """
        Execute automated response based on status.
        """
        if status == 'GREEN':
            self._size_modifiers[symbol] = 1.0
            return 'no_action'
        
        elif status == 'AMBER':
            self._size_modifiers[symbol] = 0.60
            return 'reduced_size_60pct'
        
        elif status == 'RED':
            self._suspended[symbol] = True
            self._size_modifiers[symbol] = 0
            return 'suspended_pair'
        
        elif status == 'CRITICAL':
            self._suspended[symbol] = True
            self._size_modifiers[symbol] = 0
            return 'immediate_suspend'
        
        return 'unknown'
    
    def _check_critical_override(
        self, 
        symbol: str, 
        db
    ) -> bool:
        """
        Critical override: current week loss > 2x worst backtest week.
        """
        cursor = db.conn.cursor()
        
        # Get this week's total P&L
        week_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        # Find Monday of this week
        weekday = week_start.weekday()
        monday = week_start.replace(day=week_start.day - weekday)
        
        cursor.execute("""
            SELECT COALESCE(SUM(profit), 0) FROM trades
            WHERE symbol = ? AND closed_at >= ?
        """, (symbol, monday.isoformat()))
        
        row = cursor.fetchone()
        weekly_loss = abs(min(0, row[0] if row else 0))
        
        # Compare to worst backtest week (assume 3% of account as proxy)
        # In production, this would come from backtest data
        worst_backtest_loss = 100  # Placeholder - would be configurable
        
        return weekly_loss > (worst_backtest_loss * 2)
    
    def _log_status(
        self,
        symbol: str,
        live_pf: float,
        baseline_pf: float,
        ratio: float,
        status: str,
        action: str,
        db
    ) -> None:
        """Log RDD status to database."""
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO rdd_status (
                checked_at, symbol, status, live_profit_factor,
                baseline_profit_factor, performance_ratio, action_taken
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            symbol,
            status,
            live_pf,
            baseline_pf,
            ratio,
            action
        ))
        db.conn.commit()
    
    def is_suspended(self, symbol: str) -> bool:
        """Check if symbol is suspended."""
        return self._suspended.get(symbol, False)
    
    def get_size_modifier(self, symbol: str) -> float:
        """Get current size modifier for symbol."""
        return self._size_modifiers.get(symbol, 1.0)
    
    def reset_symbol(self, symbol: str) -> bool:
        """
        Manual reset of suspended symbol.
        
        Args:
            symbol: Symbol to reset
            
        Returns:
            True if successful
        """
        with self._lock:
            if symbol in self._suspended:
                del self._suspended[symbol]
                self._size_modifiers[symbol] = 1.0
                return True
            return False
    
    def get_all_status(self) -> Dict:
        """Get current status of all symbols."""
        return {
            'suspended': list(self._suspended.keys()),
            'modifiers': self._size_modifiers.copy()
        }


# Global instance
_rdd = None


def get_regime_drift_detector(config: Optional[Dict] = None, logger=None) -> RegimeDriftDetector:
    """Get global RDD instance."""
    global _rdd
    if _rdd is None:
        _rdd = RegimeDriftDetector(config, logger)
    return _rdd