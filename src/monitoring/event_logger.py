"""
Event Logger - Structured Event Log for Zone 7
PRD Volume III Section 6.3

Records all trading decisions, pre-trade check pipeline steps,
and system events for observability and debugging.
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional, List, Dict
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.database import get_db


class EventLogger:
    """Structured event logging for trading decisions"""
    
    EVENT_TYPES = [
        'SIGNAL_DETECTED', 'CHECK_PASSED', 'CHECK_FAILED', 'CHECK_SKIPPED',
        'ORDER_PLACED', 'ORDER_MODIFIED', 'ORDER_CLOSED', 'ORDER_REJECTED',
        'CIRCUIT_BREAKER', 'RDD_UPDATE', 'HEARTBEAT', 'SYSTEM_ERROR',
        'PAPER_TRADE', 'DEMO_TRADE', 'LIVE_TRADE'
    ]
    
    SEVERITY_LEVELS = ['INFO', 'WARNING', 'CRITICAL', 'EMERGENCY']
    
    def __init__(self):
        self.db = get_db()
        self._init_database()
    
    def _init_database(self):
        """Initialize event_log and readiness_log tables"""
        cursor = self.db.conn.cursor()
        
        # Event log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT,
                event_type TEXT NOT NULL,
                check_step INTEGER,
                severity TEXT DEFAULT 'INFO',
                details TEXT NOT NULL,
                signal_id INTEGER,
                raw_data TEXT,
                mode TEXT DEFAULT 'DEMO'
            )
        """)
        
        # Readiness log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS readiness_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                condition_name TEXT NOT NULL,
                requirement TEXT NOT NULL,
                current_value TEXT NOT NULL,
                is_met INTEGER NOT NULL,
                snapshot_week TEXT
            )
        """)
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_timestamp 
            ON event_log(timestamp DESC)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_symbol 
            ON event_log(symbol)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_event_log_type 
            ON event_log(event_type)
        """)
        
        self.db.conn.commit()
    
    def log_event(self, event_type: str, details: str, symbol: Optional[str] = None,
                  check_step: Optional[int] = None, severity: str = 'INFO',
                  signal_id: Optional[int] = None, raw_data: Optional[Dict] = None,
                  mode: str = 'DEMO') -> int:
        """Log a single event"""
        if event_type not in self.EVENT_TYPES:
            event_type = 'SYSTEM_EVENT'
        if severity not in self.SEVERITY_LEVELS:
            severity = 'INFO'
        
        now = datetime.now(timezone.utc).isoformat()
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO event_log (timestamp, symbol, event_type, check_step, 
                                   severity, details, signal_id, raw_data, mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (now, symbol, event_type, check_step, severity, details,
              signal_id, json.dumps(raw_data) if raw_data else None, mode))
        
        self.db.conn.commit()
        return cursor.lastrowid
    
    def log_signal_detected(self, symbol: str, direction: str, raw_score: float,
                            regime: str, mode: str = 'DEMO') -> int:
        """Log signal detection event"""
        details = f"Direction: {direction} — Raw Score: {raw_score:.0f} — Regime: {regime}"
        return self.log_event('SIGNAL_DETECTED', details, symbol, 
                              check_step=0, severity='INFO', mode=mode)
    
    def log_check_step(self, symbol: str, step: int, passed: bool, 
                       reason: str, details: Optional[str] = None,
                       mode: str = 'DEMO') -> int:
        """Log a pre-trade check step"""
        event_type = 'CHECK_PASSED' if passed else ('CHECK_FAILED' if step else 'CHECK_SKIPPED')
        severity = 'INFO' if passed else 'WARNING'
        
        full_details = f"CHECK {step} {'PASSED' if passed else 'FAILED'} — {reason}"
        if details:
            full_details += f" — {details}"
        
        return self.log_event(event_type, full_details, symbol, 
                              check_step=step, severity=severity, mode=mode)
    
    def log_order_placed(self, symbol: str, direction: str, lots: float,
                         entry_price: float, sl: float, tp: float,
                         ticket: Optional[int] = None, latency_ms: int = 0,
                         mode: str = 'DEMO') -> int:
        """Log order placed event"""
        details = f"Ticket: {ticket or 'N/A'} — {direction} {lots:.2f} lots @ {entry_price:.5f}"
        details += f" — SL: {sl:.5f} — TP: {tp:.5f} — Latency: {latency_ms}ms"
        
        raw_data = {
            'direction': direction, 'lots': lots, 'entry': entry_price,
            'sl': sl, 'tp': tp, 'ticket': ticket, 'latency_ms': latency_ms
        }
        
        event_type = 'DEMO_TRADE' if mode == 'DEMO' else ('PAPER_TRADE' if mode == 'PAPER' else 'LIVE_TRADE')
        
        return self.log_event(event_type, details, symbol, 
                              check_step=15, severity='INFO', raw_data=raw_data, mode=mode)
    
    def log_order_closed(self, symbol: str, ticket: int, reason: str,
                         pnl: float, close_price: float, mode: str = 'DEMO') -> int:
        """Log order closed event"""
        details = f"Ticket: {ticket} — Closed: {reason} — P&L: ${pnl:.2f} @ {close_price:.5f}"
        return self.log_event('ORDER_CLOSED', details, symbol, severity='INFO',
                              raw_data={'ticket': ticket, 'pnl': pnl, 'close_price': close_price}, mode=mode)
    
    def log_heartbeat(self, status: str = 'OK') -> int:
        """Log system heartbeat"""
        return self.log_event('HEARTBEAT', f"System status: {status}", severity='INFO')
    
    def log_circuit_breaker(self, reason: str, until: Optional[str] = None) -> int:
        """Log circuit breaker activation"""
        details = f"Circuit Breaker ACTIVATED — {reason}"
        if until:
            details += f" — Until: {until}"
        return self.log_event('CIRCUIT_BREAKER', details, severity='CRITICAL',
                              raw_data={'reason': reason, 'until': until})
    
    def get_events(self, limit: int = 100, symbol: Optional[str] = None,
                    event_type: Optional[str] = None, 
                    severity: Optional[str] = None) -> List[Dict]:
        """Get recent events with optional filters"""
        cursor = self.db.conn.cursor()
        
        query = "SELECT * FROM event_log WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        events = []
        for row in cursor.fetchall():
            events.append({
                'id': row[0],
                'timestamp': row[1],
                'symbol': row[2],
                'event_type': row[3],
                'check_step': row[4],
                'severity': row[5],
                'details': row[6],
                'signal_id': row[7],
                'raw_data': json.loads(row[8]) if row[8] else None,
                'mode': row[9]
            })
        
        return events
    
    def get_signal_pipeline(self, signal_id: int) -> List[Dict]:
        """Get all events for a specific signal's pipeline"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT * FROM event_log 
            WHERE signal_id = ? 
            ORDER BY timestamp ASC
        """, (signal_id,))
        
        events = []
        for row in cursor.fetchall():
            events.append({
                'timestamp': row[1],
                'symbol': row[2],
                'event_type': row[3],
                'check_step': row[4],
                'severity': row[5],
                'details': row[6],
                'raw_data': json.loads(row[8]) if row[8] else None
            })
        
        return events
    
    def log_readiness_condition(self, condition_name: str, requirement: str,
                                 current_value: str, is_met: bool) -> int:
        """Log a readiness check condition"""
        now = datetime.now(timezone.utc)
        week = now.isocalendar()[0:2]  # (year, week)
        snapshot_week = f"{week[0]}-W{week[1]:02d}"
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO readiness_log (timestamp, condition_name, requirement, 
                                       current_value, is_met, snapshot_week)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (now.isoformat(), condition_name, requirement, current_value,
              1 if is_met else 0, snapshot_week))
        
        self.db.conn.commit()
        return cursor.lastrowid
    
    def get_readiness_status(self) -> List[Dict]:
        """Get latest readiness check status for all conditions"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT condition_name, requirement, current_value, is_met, snapshot_week
            FROM readiness_log
            WHERE id IN (
                SELECT MAX(id) FROM readiness_log 
                GROUP BY condition_name
            )
            ORDER BY condition_name
        """)
        
        conditions = []
        for row in cursor.fetchall():
            conditions.append({
                'condition_name': row[0],
                'requirement': row[1],
                'current_value': row[2],
                'is_met': bool(row[3]),
                'snapshot_week': row[4]
            })
        
        return conditions


# Singleton instance
_event_logger = None


def get_event_logger() -> EventLogger:
    """Get event logger singleton"""
    global _event_logger
    if _event_logger is None:
        _event_logger = EventLogger()
    return _event_logger