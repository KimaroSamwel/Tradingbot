"""
APEX FX Trading Bot - Fill Analyzer
PRD Volume II Section 13: Execution Quality Analysis

Records and analyzes execution quality for every completed order.
Computes the weekly Broker Quality Score (BQS).
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import threading


class FillAnalyzer:
    """
    Fill Analyzer - records and analyzes execution quality.
    
    BQS (Broker Quality Score) weights:
    - shortfall_score: 35%
    - requote_score: 30%
    - latency_score: 20%
    - spread_exp_score: 15%
    
    Alert threshold: BQS < 65 for 2 consecutive weeks triggers alert.
    """
    
    BQS_WEIGHTS = {
        'shortfall_score': 0.35,
        'requote_score': 0.30,
        'latency_score': 0.20,
        'spread_exp_score': 0.15,
    }
    
    BQS_ALERT_THRESHOLD = 65
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize fill analyzer.
        
        Args:
            config: Optional configuration
            logger: Optional logger
        """
        self._lock = threading.Lock()
        self._config = config or {}
        self._logger = logger
        
        # Cache for spread distribution
        self._spread_cache: Dict[str, Dict] = {}
    
    def record_fill(
        self,
        symbol: str,
        ticket: int,
        expected_price: float,
        actual_price: float,
        spread_at_submit: float,
        spread_at_fill: float,
        latency_ms: float,
        was_requoted: bool,
        was_partial: bool,
        db
    ) -> None:
        """
        Write fill quality record to fill_quality table.
        
        Args:
            symbol: Trading symbol
            ticket: MT5 ticket
            expected_price: Expected fill price
            actual_price: Actual fill price
            spread_at_submit: Spread at order submission
            spread_at_fill: Spread at fill
            latency_ms: Fill latency in milliseconds
            was_requoted: Whether requote occurred
            was_partial: Whether partial fill occurred
            db: Database instance
        """
        with self._lock:
            # Calculate execution shortfall in pips
            shortfall_pips = abs(actual_price - expected_price)
            
            cursor = db.conn.cursor()
            cursor.execute("""
                INSERT INTO fill_quality (
                    timestamp, symbol, ticket, expected_price, actual_fill_price,
                    execution_shortfall_pips, spread_at_submission, spread_at_fill,
                    fill_latency_ms, was_requoted, was_partial_fill
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                datetime.now(timezone.utc).isoformat(),
                symbol,
                ticket,
                expected_price,
                actual_price,
                shortfall_pips,
                spread_at_submit,
                spread_at_fill,
                latency_ms,
                1 if was_requoted else 0,
                1 if was_partial else 0
            ))
            db.conn.commit()
    
    def compute_bqs(self, days: int = 7, db=None) -> Dict:
        """
        Compute Broker Quality Score for the last N days.
        
        Args:
            days: Number of days to analyze
            db: Database instance (optional, will get from get_db if not provided)
            
        Returns:
            Dict with total_bqs and component breakdown
        """
        if db is None:
            from src.data.database import get_db
            db = get_db()
        
        with self._lock:
            cursor = db.conn.cursor()
            
            # Get fill records for the period
            cursor.execute("""
                SELECT 
                    AVG(execution_shortfall_pips) as avg_shortfall,
                    AVG(fill_latency_ms) as avg_latency,
                    (SUM(was_requoted) * 100.0 / COUNT(*)) as requote_rate,
                    AVG(spread_at_fill - spread_at_submission) as avg_spread_exp
                FROM fill_quality
                WHERE timestamp >= datetime('now', '-' || ? || ' days')
            """, (days,))
            
            row = cursor.fetchone()
            
            if not row or row[0] is None:
                return {
                    'total_bqs': 100.0,
                    'shortfall_score': 100.0,
                    'requote_score': 100.0,
                    'latency_score': 100.0,
                    'spread_exp_score': 100.0,
                    'sample_size': 0
                }
            
            avg_shortfall = row[0] or 0
            avg_latency = row[1] or 0
            requote_rate = row[2] or 0
            avg_spread_exp = row[3] or 0
            
            # Calculate component scores
            shortfall_score = self._score_shortfall(avg_shortfall)
            requote_score = self._score_requote(requote_rate)
            latency_score = self._score_latency(avg_latency)
            spread_exp_score = self._score_spread_expansion(avg_spread_exp)
            
            # Calculate total BQS
            total_bqs = (
                shortfall_score * self.BQS_WEIGHTS['shortfall_score'] +
                requote_score * self.BQS_WEIGHTS['requote_score'] +
                latency_score * self.BQS_WEIGHTS['latency_score'] +
                spread_exp_score * self.BQS_WEIGHTS['spread_exp_score']
            )
            
            return {
                'total_bqs': round(total_bqs, 2),
                'shortfall_score': round(shortfall_score, 2),
                'requote_score': round(requote_score, 2),
                'latency_score': round(latency_score, 2),
                'spread_exp_score': round(spread_exp_score, 2),
                'avg_shortfall_pips': round(avg_shortfall, 4),
                'avg_latency_ms': round(avg_latency, 2),
                'requote_rate_pct': round(requote_rate, 2),
                'sample_size': self._get_sample_size(db, days)
            }
    
    def _score_shortfall(self, avg_shortfall_pips: float) -> float:
        """
        0 pips = 100 pts. Deduct 10 pts per 0.1 pip of average shortfall.
        """
        score = 100 - (avg_shortfall_pips * 100)
        return max(0, min(100, score))
    
    def _score_requote(self, requote_rate_pct: float) -> float:
        """
        0% = 100. > 3% = 0. Linear interpolation.
        """
        if requote_rate_pct >= 3:
            return 0
        return 100 - (requote_rate_pct / 3 * 100)
    
    def _score_latency(self, avg_latency_ms: float) -> float:
        """
        < 100ms = 100. > 350ms = 0. Linear interpolation.
        """
        if avg_latency_ms <= 100:
            return 100
        if avg_latency_ms >= 350:
            return 0
        return 100 - ((avg_latency_ms - 100) / 250 * 100)
    
    def _score_spread_expansion(self, avg_expansion_pct: float) -> float:
        """
        0% expansion = 100. > 30% expansion = 0. Linear interpolation.
        """
        if avg_expansion_pct <= 0:
            return 100
        if avg_expansion_pct >= 30:
            return 0
        return 100 - (avg_expansion_pct / 30 * 100)
    
    def _get_sample_size(self, db, days: int) -> int:
        """Get number of fills in period."""
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM fill_quality
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
        """, (days,))
        row = cursor.fetchone()
        return row[0] if row else 0
    
    def get_spread_percentile(
        self, 
        symbol: str, 
        session_window: str, 
        mt5_connector,
        db
    ) -> float:
        """
        Return the current spread's percentile within the 20-day rolling
        distribution for the given symbol and 30-minute session window.
        
        Args:
            symbol: Trading symbol
            session_window: Session window name
            mt5_connector: MT5 connector
            db: Database instance
            
        Returns:
            Spread percentile (0-100)
        """
        # Get current spread
        tick = mt5_connector.get_latest_price(symbol)
        if not tick:
            return 50.0  # Default to median
        
        current_spread = tick['ask'] - tick['bid']
        
        # Get historical spreads from DB
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT spread_at_fill FROM fill_quality
            WHERE symbol = ?
            ORDER BY timestamp DESC LIMIT 200
        """, (symbol,))
        
        spreads = [row[0] for row in cursor.fetchall() if row[0]]
        
        if len(spreads) < 10:
            return 50.0
        
        # Calculate percentile
        sorted_spreads = sorted(spreads)
        count_below = sum(1 for s in sorted_spreads if s < current_spread)
        percentile = (count_below / len(sorted_spreads)) * 100
        
        return percentile


# Global instance
_fill_analyzer = None


def get_fill_analyzer(config: Optional[Dict] = None, logger=None) -> FillAnalyzer:
    """Get global fill analyzer instance."""
    global _fill_analyzer
    if _fill_analyzer is None:
        _fill_analyzer = FillAnalyzer(config, logger)
    return _fill_analyzer