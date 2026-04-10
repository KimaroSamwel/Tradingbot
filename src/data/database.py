"""
APEX FX Trading Bot - Database Manager
SQLite database for storing all trading data
"""

import sqlite3
import json
import pandas as pd
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional


class Database:
    """SQLite database manager for trading data"""
    
    def __init__(self, db_path: str = "apex_trading.db"):
        self.base_dir = Path(__file__).parent.parent.parent
        self.db_path = self.base_dir / db_path
        self.conn = None
        self._connect()
        self._init_tables()
    
    def _connect(self):
        """Connect to SQLite database"""
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
    
    def _init_tables(self):
        """Initialize all database tables"""
        cursor = self.conn.cursor()
        
        # Account table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT UNIQUE,
                broker TEXT,
                balance REAL,
                equity REAL,
                currency TEXT,
                leverage INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Trades table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_id TEXT UNIQUE,
                account_id TEXT,
                symbol TEXT,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                volume REAL,
                sl_price REAL,
                tp_price REAL,
                status TEXT,
                profit REAL,
                commission REAL,
                swap REAL,
                strategy TEXT,
                notes TEXT,
                opened_at TIMESTAMP,
                closed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Signals table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT UNIQUE,
                symbol TEXT,
                strategy TEXT,
                direction TEXT,
                entry_price REAL,
                sl_price REAL,
                tp_price REAL,
                confidence REAL,
                indicators TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Performance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id TEXT,
                date DATE,
                trades_count INTEGER,
                wins INTEGER,
                losses INTEGER,
                total_profit REAL,
                drawdown REAL,
                metrics TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Backtest results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backtests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                backtest_id TEXT UNIQUE,
                strategy TEXT,
                symbol TEXT,
                start_date DATE,
                end_date DATE,
                initial_balance REAL,
                final_balance REAL,
                total_trades INTEGER,
                win_rate REAL,
                profit_factor REAL,
                max_drawdown REAL,
                results TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Fill quality table (PRD Vol II)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fill_quality (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                ticket INTEGER,
                expected_price REAL,
                actual_fill_price REAL,
                execution_shortfall_pips REAL,
                spread_at_submission REAL,
                spread_at_fill REAL,
                fill_latency_ms REAL,
                was_requoted INTEGER DEFAULT 0,
                was_partial_fill INTEGER DEFAULT 0
            )
        """)
        
        # Signal scores table (PRD Vol II)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                trend_alignment_score REAL,
                momentum_score REAL,
                regime_quality_score REAL,
                session_timing_score REAL,
                execution_quality_score REAL,
                cot_bonus REAL DEFAULT 0,
                total_score REAL NOT NULL,
                grade TEXT NOT NULL,
                position_modifier REAL NOT NULL,
                trade_opened INTEGER DEFAULT 0,
                outcome_pips REAL
            )
        """)
        
        # Kelly history table (PRD Vol II)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kelly_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                calculated_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                lookback_trades INTEGER,
                win_rate REAL,
                avg_win_r REAL,
                avg_loss_r REAL,
                full_kelly REAL,
                fractional_kelly REAL,
                effective_risk_pct REAL
            )
        """)
        
        # Portfolio heat log table (PRD Vol II)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_heat_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                heat_pct REAL NOT NULL,
                heat_level TEXT NOT NULL,
                open_positions_count INTEGER,
                action_taken TEXT
            )
        """)
        
        # RDD status table (PRD Vol II)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rdd_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checked_at TEXT NOT NULL,
                symbol TEXT NOT NULL,
                status TEXT NOT NULL,
                live_profit_factor REAL,
                baseline_profit_factor REAL,
                performance_ratio REAL,
                action_taken TEXT
            )
        """)
        
        # COT data table (PRD Vol II)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cot_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                net_speculative_position REAL,
                cot_index REAL,
                direction TEXT,
                is_extreme INTEGER DEFAULT 0
            )
        """)
        
        # Weekly reports table (PRD Vol II)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS weekly_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_ending TEXT NOT NULL,
                net_pnl REAL,
                total_trades INTEGER,
                win_rate REAL,
                profit_factor REAL,
                max_drawdown_week REAL,
                peak_portfolio_heat REAL,
                avg_bqs REAL,
                report_json TEXT
            )
        """)
        
        self.conn.commit()
    
    def insert_trade(self, trade_data: Dict[str, Any]) -> int:
        """Insert a trade record"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO trades (
                trade_id, account_id, symbol, direction, entry_price, exit_price,
                volume, sl_price, tp_price, status, profit, commission, swap,
                strategy, notes, opened_at, closed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trade_data.get('trade_id'),
            trade_data.get('account_id'),
            trade_data.get('symbol'),
            trade_data.get('direction'),
            trade_data.get('entry_price'),
            trade_data.get('exit_price'),
            trade_data.get('volume'),
            trade_data.get('sl_price'),
            trade_data.get('tp_price'),
            trade_data.get('status', 'OPEN'),
            trade_data.get('profit', 0),
            trade_data.get('commission', 0),
            trade_data.get('swap', 0),
            trade_data.get('strategy'),
            trade_data.get('notes'),
            trade_data.get('opened_at'),
            trade_data.get('closed_at')
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def update_trade(self, trade_id: str, updates: Dict[str, Any]):
        """Update a trade record"""
        cursor = self.conn.cursor()
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [trade_id]
        cursor.execute(f"UPDATE trades SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE trade_id = ?", values)
        self.conn.commit()
    
    def get_trades(self, account_id: str = None, status: str = None, 
                   from_date: str = None, to_date: str = None) -> List[Dict]:
        """Get trades with filters"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM trades WHERE 1=1"
        params = []
        
        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if from_date:
            query += " AND opened_at >= ?"
            params.append(from_date)
        if to_date:
            query += " AND opened_at <= ?"
            params.append(to_date)
        
        query += " ORDER BY opened_at DESC"
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_open_positions(self, account_id: str = None) -> List[Dict]:
        """Get all open positions"""
        return self.get_trades(account_id=account_id, status='OPEN')
    
    def insert_signal(self, signal_data: Dict[str, Any]) -> int:
        """Insert a signal record"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO signals (
                    signal_id, symbol, strategy, direction, entry_price, sl_price, 
                    tp_price, confidence, indicators, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                signal_data.get('signal_id') or f"SIG_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                signal_data.get('symbol', ''),
                signal_data.get('strategy', ''),
                signal_data.get('direction', ''),
                signal_data.get('entry_price') or 0,
                signal_data.get('sl_price') or 0,
                signal_data.get('tp_price') or 0,
                signal_data.get('confidence', 0),
                json.dumps(signal_data.get('indicators', {})),
                signal_data.get('status', 'NEW'),
                signal_data.get('created_at') or datetime.now().isoformat()
            ))
            self.conn.commit()
            return cursor.lastrowid
        except Exception as e:
            print(f"Insert signal error: {e}")
            return -1
    
    def get_signals(self, symbol: str = None, status: str = None, limit: int = 50) -> List[Dict]:
        """Get signals with filters"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM signals WHERE 1=1"
        params = []
        
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)
        if status:
            query += " AND status = ?"
            params.append(status)
        
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        results = [dict(row) for row in cursor.fetchall()]
        for r in results:
            if r.get('indicators'):
                r['indicators'] = json.loads(r['indicators'])
        return results
    
    def update_performance(self, account_id: str, date: str, metrics: Dict[str, Any]):
        """Update performance metrics"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO performance (
                account_id, date, trades_count, wins, losses, total_profit, 
                drawdown, metrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account_id, date,
            metrics.get('trades_count', 0),
            metrics.get('wins', 0),
            metrics.get('losses', 0),
            metrics.get('total_profit', 0),
            metrics.get('drawdown', 0),
            json.dumps(metrics)
        ))
        self.conn.commit()
    
    def get_performance(self, account_id: str, days: int = 30) -> List[Dict]:
        """Get performance history"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM performance 
            WHERE account_id = ? AND date >= date('now', '-' || ? || ' days')
            ORDER BY date DESC
        """, (account_id, days))
        results = [dict(row) for row in cursor.fetchall()]
        for r in results:
            if r.get('metrics'):
                r['metrics'] = json.loads(r['metrics'])
        return results
    
    def save_setting(self, key: str, value: str):
        """Save a setting"""
        cursor = self.conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        self.conn.commit()
    
    def get_setting(self, key: str, default: str = None) -> Optional[str]:
        """Get a setting"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        return result['value'] if result else default
    
    def get_stats(self, account_id: str = None) -> Dict[str, Any]:
        """Get trading statistics"""
        cursor = self.conn.cursor()
        
        query = """
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit < 0 THEN 1 ELSE 0 END) as losses,
                SUM(profit) as total_profit,
                AVG(profit) as avg_profit,
                MAX(profit) as max_profit,
                MIN(profit) as min_profit
            FROM trades
            WHERE status = 'CLOSED'
        """
        params = []
        if account_id:
            query += " AND account_id = ?"
            params.append(account_id)
        
        cursor.execute(query, params)
        row = cursor.fetchone()
        stats = dict(row) if row else {}
        
        if stats.get('total_trades', 0) > 0:
            stats['win_rate'] = round(stats['wins'] / stats['total_trades'] * 100, 2)
        else:
            stats['win_rate'] = 0
            
        return stats
    
    def get_daily_realised_pnl(self, symbol: str) -> float:
        """
        Sum P&L of all closed trades for symbol since UTC midnight today.
        Used for per-pair daily loss tracking.
        """
        today_midnight = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).isoformat()
        
        cursor = self.conn.cursor()
        cursor.execute(
            '''SELECT COALESCE(SUM(profit), 0) FROM trades 
               WHERE symbol = ? AND closed_at >= ? AND status = 'CLOSED' ''',
            (symbol, today_midnight)
        )
        row = cursor.fetchone()
        return row[0] if row else 0.0
    
    def log_missed_signal(self, symbol: str, direction: str, lots: float, reason: str) -> None:
        """Log a missed trading signal due to order failure."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
        """, (f"missed_signal_{datetime.now().strftime('%Y%m%d%H%M%S')}",
              json.dumps({'symbol': symbol, 'direction': direction, 'lots': lots, 'reason': reason})))
        self.conn.commit()
    
    def log_signal_score(self, score_result: Dict, ticket: int = None) -> int:
        """Log signal score to signal_scores table."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO signal_scores (
                timestamp, symbol, direction, trend_alignment_score, momentum_score,
                regime_quality_score, session_timing_score, execution_quality_score,
                cot_bonus, total_score, grade, position_modifier, trade_opened, outcome_pips
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            score_result.get('symbol', ''),
            score_result.get('direction', ''),
            score_result.get('trend_alignment_score', 0),
            score_result.get('momentum_score', 0),
            score_result.get('regime_quality_score', 0),
            score_result.get('session_timing_score', 0),
            score_result.get('execution_quality_score', 0),
            score_result.get('cot_adjustment', 0),
            score_result.get('total_score', 0),
            score_result.get('grade', 'REJECT'),
            score_result.get('position_modifier', 0),
            1 if ticket else 0,
            score_result.get('outcome_pips')
        ))
        self.conn.commit()
        return cursor.lastrowid
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()


# Global database instance
db = Database()


def get_db() -> Database:
    """Get global database instance"""
    return db