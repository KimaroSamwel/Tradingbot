"""
APEX FX Trading Bot - Performance Analyzer
PRD Volume II Section 15: Self-Learning Feedback Loop

Runs every Friday at 21:30 UTC. Clusters wins vs losses across 6 dimensions
and produces governed parameter micro-corrections.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
import threading
import json


class PerformanceAnalyzer:
    """
    Performance Analyzer - self-learning feedback loop.
    
    Analysis dimensions:
    - session_window (UTC 2-hour buckets)
    - vrs_level (Volatility scalar at entry)
    - adx_bucket (<20, 20-25, 25-30, 30-40, >40)
    - signal_score_band (60-69, 70-79, 80-89, 90-100)
    - day_of_week (0=Monday ... 4=Friday)
    - trade_duration_h (<4, 4-12, 12-24, 24-48, >48)
    
    Governance:
    - Max 1 parameter category per symbol per week
    - Max 15% change from current value
    - Changes only applied Sunday 22:00 UTC
    - Minimum 15 trades per symbol for actionable results
    """
    
    ANALYSIS_DIMENSIONS = [
        'session_window',
        'vrs_level',
        'adx_bucket',
        'signal_score_band',
        'day_of_week',
        'trade_duration_h',
    ]
    
    MAX_PARAM_CHANGE_PCT = 0.15
    MIN_TRADES_TO_ACT = 15
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize performance analyzer.
        
        Args:
            config: Optional configuration
            logger: Optional logger
        """
        self._lock = threading.Lock()
        self._config = config or {}
        self._logger = logger
        
        # Pending parameter changes (applied Sunday 22:00)
        self._pending_changes: Dict[str, Dict] = {}
    
    def run_weekly_analysis(self, db) -> Dict:
        """
        Main entry point.
        
        Args:
            db: Database instance
            
        Returns:
            Summary dict with analysis results
        """
        results = {
            'symbols_analyzed': [],
            'recommendations': [],
            'applied_changes': [],
            'week_ending': datetime.now(timezone.utc).isoformat()
        }
        
        with self._lock:
            # Get all symbols
            symbols = ['EURUSD', 'GBPUSD', 'USDJPY', 'USDCHF', 'USDCAD', 'XAUUSD']
            
            for symbol in symbols:
                # Get trades for last 30 days
                trades = self._get_trades_last_30_days(symbol, db)
                
                if len(trades) < self.MIN_TRADES_TO_ACT:
                    continue
                
                results['symbols_analyzed'].append(symbol)
                
                # Cluster by each dimension
                dimension_analysis = {}
                for dim in self.ANALYSIS_DIMENSIONS:
                    dimension_analysis[dim] = self._cluster_by_dimension(trades, dim)
                
                # Find underperforming buckets
                overall_win_rate = self._calculate_overall_win_rate(trades)
                underperforming = self._find_underperforming_buckets(
                    dimension_analysis, overall_win_rate
                )
                
                # Generate recommendations
                if underperforming:
                    recs = self._generate_recommendations(
                        symbol, underperforming, dimension_analysis
                    )
                    results['recommendations'].extend(recs)
            
            # Apply governance gate
            approved = self._apply_governance_gate(results['recommendations'])
            
            # Store pending changes
            for change in approved:
                self._pending_changes[change['symbol']] = change
            
            results['approved_changes'] = approved
            
            # Write weekly report
            self._write_weekly_report(results, db)
        
        return results
    
    def _get_trades_last_30_days(self, symbol: str, db) -> List[Dict]:
        """Get closed trades for symbol in last 30 days."""
        cursor = db.conn.cursor()
        
        # Get trades with their signal scores
        cursor.execute("""
            SELECT t.symbol, t.direction, t.profit, t.opened_at, t.closed_at,
                   s.total_score, s.regime_quality_score
            FROM trades t
            LEFT JOIN signal_scores s ON t.symbol = s.symbol
            WHERE t.symbol = ? AND t.status = 'CLOSED'
            AND t.closed_at >= datetime('now', '-30 days')
            ORDER BY t.closed_at DESC
        """, (symbol,))
        
        trades = []
        for row in cursor.fetchall():
            trades.append({
                'symbol': row[0],
                'direction': row[1],
                'profit': row[2] or 0,
                'opened_at': row[3],
                'closed_at': row[4],
                'signal_score': row[5] if row[5] else 70,
                'regime_quality': row[6] if row[6] else 50
            })
        
        return trades
    
    def _calculate_overall_win_rate(self, trades: List[Dict]) -> float:
        """Calculate overall win rate."""
        if not trades:
            return 0
        
        wins = sum(1 for t in trades if t['profit'] > 0)
        return wins / len(trades)
    
    def _cluster_by_dimension(
        self, 
        trades: List[Dict], 
        dimension: str
    ) -> Dict:
        """Group trades by dimension bucket."""
        buckets = {}
        
        for trade in trades:
            bucket = self._get_bucket(trade, dimension)
            
            if bucket not in buckets:
                buckets[bucket] = {'wins': 0, 'losses': 0, 'total': 0}
            
            buckets[bucket]['total'] += 1
            if trade['profit'] > 0:
                buckets[bucket]['wins'] += 1
            else:
                buckets[bucket]['losses'] += 1
        
        # Calculate win rate per bucket
        for bucket, data in buckets.items():
            data['win_rate'] = data['wins'] / data['total'] if data['total'] > 0 else 0
        
        return buckets
    
    def _get_bucket(self, trade: Dict, dimension: str) -> str:
        """Get bucket name for a trade dimension."""
        if dimension == 'session_window':
            # Extract hour from open time
            return 'LONDON'  # Simplified
        
        elif dimension == 'vrs_level':
            return 'NORMAL'  # Simplified - would come from VRS at entry
        
        elif dimension == 'adx_bucket':
            adx = trade.get('regime_quality', 50)
            if adx < 20:
                return '<20'
            elif adx < 25:
                return '20-25'
            elif adx < 30:
                return '25-30'
            elif adx < 40:
                return '30-40'
            else:
                return '>40'
        
        elif dimension == 'signal_score_band':
            score = trade.get('signal_score', 70)
            if score < 70:
                return '60-69'
            elif score < 80:
                return '70-79'
            elif score < 90:
                return '80-89'
            else:
                return '90-100'
        
        elif dimension == 'day_of_week':
            # Extract from timestamp
            return '3'  # Simplified - Wednesday
        
        elif dimension == 'trade_duration_h':
            # Calculate duration
            return '4-12'  # Simplified
        
        return 'UNKNOWN'
    
    def _find_underperforming_buckets(
        self, 
        dimension_analysis: Dict, 
        overall_win_rate: float
    ) -> List[Dict]:
        """Identify underperforming buckets (win_rate < overall - 10%)."""
        threshold = overall_win_rate - 0.10
        underperforming = []
        
        for dim_name, buckets in dimension_analysis.items():
            for bucket, data in buckets.items():
                if data['win_rate'] < threshold:
                    underperforming.append({
                        'dimension': dim_name,
                        'bucket': bucket,
                        'win_rate': data['win_rate'],
                        'threshold': threshold,
                        'trades': data['total']
                    })
        
        return underperforming
    
    def _generate_recommendations(
        self, 
        symbol: str, 
        underperforming: List[Dict],
        dimension_analysis: Dict
    ) -> List[Dict]:
        """Generate parameter adjustment recommendations."""
        recommendations = []
        
        for up in underperforming:
            # Calculate adjustment (simplified)
            # In real implementation, would map to specific parameters
            change_pct = (up['threshold'] - up['win_rate']) / up['win_rate']
            
            recommendations.append({
                'symbol': symbol,
                'parameter': up['dimension'],
                'bucket': up['bucket'],
                'current_value': 1.0,
                'suggested_change_pct': change_pct * -1,  # Reduce exposure
                'reason': f"Win rate {up['win_rate']:.1%} below threshold {up['threshold']:.1%}"
            })
        
        return recommendations
    
    def _apply_governance_gate(self, recommendations: List[Dict]) -> List[Dict]:
        """
        Governance rules:
        - Max 1 parameter category updated per symbol per week
        - Max 15% change from current value
        - Changes only applied Sunday 22:00 UTC
        """
        approved = []
        symbols_updated = set()
        
        for rec in recommendations:
            symbol = rec['symbol']
            
            # Max 1 parameter per symbol
            if symbol in symbols_updated:
                continue
            
            # Cap change at 15%
            change = abs(rec['suggested_change_pct'])
            if change > self.MAX_PARAM_CHANGE_PCT:
                rec['suggested_change_pct'] = (
                    self.MAX_PARAM_CHANGE_PCT * 
                    (1 if rec['suggested_change_pct'] > 0 else -1)
                )
            
            approved.append(rec)
            symbols_updated.add(symbol)
        
        return approved
    
    def _write_weekly_report(self, results: Dict, db) -> None:
        """Write weekly report to database."""
        cursor = db.conn.cursor()
        
        # Calculate aggregate stats
        total_trades = sum(
            len(self._get_trades_last_30_days(s, db)) 
            for s in results['symbols_analyzed']
        )
        
        cursor.execute("""
            INSERT INTO weekly_reports (
                week_ending, net_pnl, total_trades, win_rate,
                profit_factor, max_drawdown_week, peak_portfolio_heat,
                avg_bqs, report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            results['week_ending'],
            0,  # Would calculate from trades
            total_trades,
            0,  # Would calculate
            0,  # Would calculate
            0,  # Would calculate
            0,  # Would get from heat monitor
            0,  # Would get from fill analyzer
            json.dumps(results)
        ))
        db.conn.commit()
    
    def get_pending_changes(self) -> Dict:
        """Get pending parameter changes."""
        return self._pending_changes.copy()
    
    def apply_changes(self) -> List[Dict]:
        """Apply pending changes (called Sunday 22:00 UTC)."""
        with self._lock:
            applied = list(self._pending_changes.values())
            self._pending_changes.clear()
            return applied


# Global instance
_perf_analyzer = None


def get_performance_analyzer(config: Optional[Dict] = None, logger=None) -> PerformanceAnalyzer:
    """Get global performance analyzer instance."""
    global _perf_analyzer
    if _perf_analyzer is None:
        _perf_analyzer = PerformanceAnalyzer(config, logger)
    return _perf_analyzer