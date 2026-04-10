"""
Paper Trading Engine - Full Virtual Execution System
PRD Volume III Section 5.2

This module provides a 100% faithful simulation of live trading.
All pre-trade checks, signal scoring, and risk filters run identically
to live trading - only the execution is virtual.
"""

import os
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, List, Tuple
import json
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.data.database import get_db
from src.config import get_config


class PaperEngine:
    """Paper Trading Engine - Virtual Execution System"""
    
    DEFAULT_STARTING_BALANCE = 10000.0
    DEFAULT_LEVERAGE = 100
    DEFAULT_SPEED = 1  # 1x to 1000x for offline replay
    
    # Slippage defaults (pips) - can be overridden per symbol
    DEFAULT_SLIPPAGE = {
        'XAUUSD': 0.5,
        'EURUSD': 0.2,
        'GBPUSD': 0.3,
        'USDJPY': 0.3,
        'USDCHF': 0.3,
        'USDCAD': 0.3,
        'AUDUSD': 0.3
    }
    
    # Commission per lot (USD)
    DEFAULT_COMMISSION = 7.0
    
    def __init__(self):
        self.db = get_db()
        self.config = get_config()
        self._init_database()
        
    def _init_database(self):
        """Initialize paper trading database tables"""
        cursor = self.db.conn.cursor()
        
        # Paper account table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_account (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                balance REAL NOT NULL,
                equity REAL NOT NULL,
                floating_pnl REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                total_trades INTEGER DEFAULT 0,
                reset_count INTEGER DEFAULT 0
            )
        """)
        
        # Paper positions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket TEXT NOT NULL UNIQUE,
                symbol TEXT NOT NULL,
                direction TEXT NOT NULL,
                lot_size REAL NOT NULL,
                open_time TEXT NOT NULL,
                open_price REAL NOT NULL,
                simulated_spread REAL,
                simulated_commission REAL,
                stop_loss REAL NOT NULL,
                take_profit REAL NOT NULL,
                trailing_stop_active INTEGER DEFAULT 0,
                trailing_stop_price REAL,
                signal_score REAL,
                kelly_risk_pct REAL,
                vrs_scalar REAL,
                regime TEXT,
                current_price REAL,
                floating_pnl REAL DEFAULT 0,
                status TEXT DEFAULT 'OPEN',
                close_time TEXT,
                close_price REAL,
                realized_pnl REAL
            )
        """)
        
        # Paper trades log (audit trail)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS paper_trades_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                ticket TEXT,
                symbol TEXT,
                direction TEXT,
                lot_size REAL,
                price REAL,
                pnl REAL,
                reason TEXT,
                metadata TEXT
            )
        """)
        
        # Initialize paper account if not exists
        cursor.execute("SELECT COUNT(*) FROM paper_account")
        if cursor.fetchone()[0] == 0:
            self._create_account()
        
        self.db.conn.commit()
    
    def _create_account(self):
        """Create initial paper account"""
        starting_balance = self.config.get('paper.starting_balance') or self.DEFAULT_STARTING_BALANCE
        now = datetime.now(timezone.utc).isoformat()
        
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO paper_account (timestamp, balance, equity, floating_pnl, realized_pnl, total_trades, reset_count)
            VALUES (?, ?, ?, 0, 0, 0, 0)
        """, (now, starting_balance, starting_balance))
        self.db.conn.commit()
    
    def get_account(self) -> Dict:
        """Get current paper account state"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT timestamp, balance, equity, floating_pnl, realized_pnl, total_trades, reset_count
            FROM paper_account
            ORDER BY id DESC
            LIMIT 1
        """)
        row = cursor.fetchone()
        
        if row:
            return {
                'timestamp': row[0],
                'balance': row[1],
                'equity': row[2],
                'floating_pnl': row[3],
                'realized_pnl': row[4],
                'total_trades': row[5],
                'reset_count': row[6]
            }
        return self._create_account_dict()
    
    def _create_account_dict(self) -> Dict:
        """Create default account dict"""
        starting = self.config.get('paper.starting_balance') or self.DEFAULT_STARTING_BALANCE
        return {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'balance': starting,
            'equity': starting,
            'floating_pnl': 0,
            'realized_pnl': 0,
            'total_trades': 0,
            'reset_count': 0
        }
    
    def get_positions(self) -> List[Dict]:
        """Get all open paper positions"""
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT id, ticket, symbol, direction, lot_size, open_time, open_price,
                   stop_loss, take_profit, trailing_stop_active, trailing_stop_price,
                   signal_score, kelly_risk_pct, vrs_scalar, regime, current_price,
                   floating_pnl, status
            FROM paper_positions
            WHERE status = 'OPEN'
            ORDER BY open_time DESC
        """)
        
        positions = []
        rows = cursor.fetchall()
        if not rows:
            return positions
            
        for row in rows:
            if len(row) < 18:
                continue
            positions.append({
                'id': row[0],
                'ticket': row[1],
                'symbol': row[2],
                'direction': row[3],
                'lot_size': row[4],
                'open_time': row[5],
                'open_price': row[6],
                'stop_loss': row[7],
                'take_profit': row[8],
                'trailing_stop_active': bool(row[9]),
                'trailing_stop_price': row[10],
                'signal_score': row[11],
                'kelly_risk_pct': row[12],
                'vrs_scalar': row[13],
                'regime': row[14],
                'current_price': row[15],
                'floating_pnl': row[16],
                'status': row[17]
            })
        return positions
        return positions
    
    def _generate_ticket(self) -> str:
        """Generate unique paper ticket"""
        date_str = datetime.now().strftime('%Y%m%d')
        cursor = self.db.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM paper_positions
            WHERE ticket LIKE 'PAPER-%'
        """)
        count = cursor.fetchone()[0] + 1
        return f"PAPER-{date_str}-{count:03d}"
    
    def _get_slippage(self, symbol: str) -> float:
        """Get slippage for symbol"""
        return self.DEFAULT_SLIPPAGE.get(symbol, 0.3)
    
    def _get_commission(self, lot_size: float) -> float:
        """Calculate commission for lot size"""
        return lot_size * self.DEFAULT_COMMISSION
    
    def _apply_slippage(self, price: float, direction: str, symbol: str) -> float:
        """Apply simulated slippage to price"""
        slippage_pips = self._get_slippage(symbol)
        
        # Convert pips to price (for forex: 0.0001, for XAU: 0.01)
        if symbol == 'XAUUSD':
            pip_value = 0.01
        else:
            pip_value = 0.0001
        
        slippage_price = slippage_pips * pip_value
        
        # Negative slippage for BUY (price goes up), positive for SELL (price goes down)
        if direction == 'BUY':
            return price + slippage_price
        else:
            return price - slippage_price
    
    def open_position(self, symbol: str, direction: str, lot_size: float,
                      entry_price: float, stop_loss: float, take_profit: float,
                      signal_score: float = 0, kelly_risk_pct: float = 0,
                      vrs_scalar: float = 1.0, regime: str = 'T') -> Dict:
        """Open a virtual paper position"""
        
        # Get current spread
        spread = self._get_spread(symbol)
        
        # Apply spread to entry price
        if direction == 'BUY':
            adjusted_entry = entry_price + spread
        else:
            adjusted_entry = entry_price - spread
        
        # Apply slippage
        fill_price = self._apply_slippage(adjusted_entry, direction, symbol)
        
        # Calculate commission
        commission = self._get_commission(lot_size)
        
        # Calculate required margin
        margin_required = lot_size * fill_price / self.DEFAULT_LEVERAGE
        
        # Get account
        account = self.get_account()
        
        # Check margin
        available_margin = account['balance'] - margin_required
        if available_margin < 0:
            return {
                'success': False,
                'error': 'Insufficient virtual margin',
                'ticket': None
            }
        
        # Generate ticket
        ticket = self._generate_ticket()
        now = datetime.now(timezone.utc).isoformat()
        
        # Insert position
        cursor = self.db.conn.cursor()
        cursor.execute("""
            INSERT INTO paper_positions (
                ticket, symbol, direction, lot_size, open_time, open_price,
                simulated_spread, simulated_commission, stop_loss, take_profit,
                signal_score, kelly_risk_pct, vrs_scalar, regime, current_price,
                floating_pnl, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 'OPEN')
        """, (ticket, symbol, direction, lot_size, now, fill_price, spread,
              commission, stop_loss, take_profit, signal_score, kelly_risk_pct,
              vrs_scalar, regime, fill_price))
        
        # Deduct commission from balance
        new_balance = account['balance'] - commission
        self._update_account(new_balance)
        
        # Log event
        self._log_event('POSITION_OPENED', ticket, symbol, direction, lot_size,
                        fill_price, 0, f"Opened {direction} {lot_size} lots at {fill_price}")
        
        self.db.conn.commit()
        
        return {
            'success': True,
            'ticket': ticket,
            'fill_price': fill_price,
            'spread': spread,
            'commission': commission
        }
    
    def _get_spread(self, symbol: str) -> float:
        """Get spread for symbol (in price units)"""
        spreads = {
            'XAUUSD': 0.30,   # 30 cents
            'EURUSD': 0.00015,  # 1.5 pips
            'GBPUSD': 0.00020,  # 2 pips
            'USDJPY': 0.015,    # 1.5 pips
            'USDCHF': 0.00020,
            'USDCAD': 0.00020,
            'AUDUSD': 0.00025
        }
        return spreads.get(symbol, 0.00020)
    
    def _update_account(self, balance: float, floating_pnl: float = 0):
        """Update paper account balance and equity"""
        cursor = self.db.conn.cursor()
        
        account = self.get_account()
        realized_pnl = account.get('realized_pnl', 0)
        equity = balance + floating_pnl + realized_pnl
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT INTO paper_account (timestamp, balance, equity, floating_pnl, realized_pnl, total_trades, reset_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (now, balance, equity, floating_pnl, realized_pnl, account['total_trades'], account['reset_count']))
        self.db.conn.commit()
    
    def close_position(self, ticket: str, reason: str = 'MANUAL', close_price: Optional[float] = None) -> Dict:
        """Close a paper position"""
        cursor = self.db.conn.cursor()
        
        # Get position
        cursor.execute("SELECT * FROM paper_positions WHERE ticket = ? AND status = 'OPEN'", (ticket,))
        row = cursor.fetchone()
        
        if not row:
            return {'success': False, 'error': 'Position not found'}
        
        position = {
            'id': row[0], 'ticket': row[1], 'symbol': row[2], 'direction': row[3],
            'lot_size': row[4], 'open_time': row[5], 'open_price': row[6],
            'simulated_spread': row[7], 'simulated_commission': row[8],
            'stop_loss': row[9], 'take_profit': row[10],
            'trailing_stop_active': bool(row[11]), 'trailing_stop_price': row[12],
            'signal_score': row[13], 'kelly_risk_pct': row[14],
            'vrs_scalar': row[15], 'regime': row[16], 'current_price': row[17]
        }
        
        # Determine close price
        if close_price is None:
            # Get current price from MT5 or use last known
            try:
                from src.data.mt5_connector import get_mt5
                mt5 = get_mt5()
                if mt5.is_connected():
                    latest = mt5.get_latest_price(position['symbol'])
                    close_price = latest.get('bid' if position['direction'] == 'BUY' else 'ask', position['current_price'])
                else:
                    close_price = position['current_price']
            except:
                close_price = position['current_price']
        
        # Apply slippage
        close_price = self._apply_slippage(close_price, position['direction'], position['symbol'])
        
        # Calculate P&L
        if position['direction'] == 'BUY':
            pnl = (close_price - position['open_price']) * position['lot_size'] * 100  # XAU: 100oz per lot
            if position['symbol'] != 'XAUUSD':
                pnl = (close_price - position['open_price']) * position['lot_size'] * 100000  # Forex: 100k units
        else:
            pnl = (position['open_price'] - close_price) * position['lot_size'] * 100
            if position['symbol'] != 'XAUUSD':
                pnl = (position['open_price'] - close_price) * position['lot_size'] * 100000
        
        # Subtract commission
        commission = self._get_commission(position['lot_size'])
        net_pnl = pnl - commission
        
        # Update position
        now = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            UPDATE paper_positions
            SET status = ?, close_time = ?, close_price = ?, realized_pnl = ?
            WHERE ticket = ?
        """, (f'CLOSED_{reason}', now, close_price, net_pnl, ticket))
        
        # Update account
        account = self.get_account()
        new_balance = account['balance'] + net_pnl
        new_total_trades = account['total_trades'] + 1
        self._update_account(new_balance, 0, new_total_trades, account['reset_count'])
        
        # Log event
        self._log_event('POSITION_CLOSED', ticket, position['symbol'],
                        position['direction'], position['lot_size'], close_price,
                        net_pnl, f"Closed: {reason}")
        
        self.db.conn.commit()
        
        return {
            'success': True,
            'ticket': ticket,
            'close_price': close_price,
            'pnl': net_pnl,
            'reason': reason
        }
    
    def close_position_by_symbol(self, symbol: str, close_price: Optional[float] = None) -> Dict:
        """Close the first open position for a symbol"""
        cursor = self.db.conn.cursor()
        
        # Get first open position for symbol
        cursor.execute("SELECT ticket FROM paper_positions WHERE symbol = ? AND status = 'OPEN' ORDER BY open_time ASC LIMIT 1", (symbol,))
        row = cursor.fetchone()
        
        if not row:
            return {'success': False, 'error': 'No open position for symbol'}
        
        return self.close_position(row[0], 'SIGNAL_REVERSE', close_price)
    
    def _update_account(self, balance: float, floating_pnl: float = 0,
                        total_trades: Optional[int] = None, reset_count: Optional[int] = None):
        """Update paper account (internal)"""
        cursor = self.db.conn.cursor()
        
        account = self.get_account()
        if total_trades is None:
            total_trades = account.get('total_trades', 0)
        if reset_count is None:
            reset_count = account.get('reset_count', 0)
        
        realized_pnl = account.get('realized_pnl', 0)
        equity = balance + floating_pnl + realized_pnl
        now = datetime.now(timezone.utc).isoformat()
        
        cursor.execute("""
            INSERT INTO paper_account (timestamp, balance, equity, floating_pnl, realized_pnl, total_trades, reset_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (now, balance, equity, floating_pnl, realized_pnl, total_trades, reset_count))
        self.db.conn.commit()
    
    def check_stop_loss_take_profit(self, symbol: str, current_price: float,
                                    high_price: float, low_price: float) -> List[Dict]:
        """Check SL/TP conditions and close positions if triggered"""
        closed_positions = []
        cursor = self.db.conn.cursor()
        
        cursor.execute("""
            SELECT ticket, direction, stop_loss, take_profit
            FROM paper_positions
            WHERE symbol = ? AND status = 'OPEN'
        """, (symbol,))
        
        for row in cursor.fetchall():
            ticket, direction, sl, tp = row[0], row[1], row[2], row[3]
            
            triggered = None
            close_price = None
            
            if direction == 'BUY':
                if sl and low_price <= sl:
                    triggered = 'SL'
                    close_price = sl
                elif tp and high_price >= tp:
                    triggered = 'TP'
                    close_price = tp
            else:  # SELL
                if sl and high_price >= sl:
                    triggered = 'SL'
                    close_price = sl
                elif tp and low_price <= tp:
                    triggered = 'TP'
                    close_price = tp
            
            if triggered:
                result = self.close_position(ticket, triggered, close_price)
                closed_positions.append(result)
        
        return closed_positions
    
    def update_positions_prices(self, prices: Dict[str, Dict]):
        """Update current prices and floating P&L for all positions"""
        cursor = self.db.conn.cursor()
        
        for position in self.get_positions():
            symbol = position['symbol']
            if symbol in prices:
                current_price = prices[symbol].get('bid', prices[symbol].get('close', 0))
                
                # Calculate floating P&L
                direction = position['direction']
                lot_size = position['lot_size']
                open_price = position['open_price']
                
                if direction == 'BUY':
                    pnl = (current_price - open_price) * lot_size * 100
                    if symbol != 'XAUUSD':
                        pnl = (current_price - open_price) * lot_size * 100000
                else:
                    pnl = (open_price - current_price) * lot_size * 100
                    if symbol != 'XAUUSD':
                        pnl = (open_price - current_price) * lot_size * 100000
                
                # Update position
                cursor.execute("""
                    UPDATE paper_positions
                    SET current_price = ?, floating_pnl = ?
                    WHERE ticket = ?
                """, (current_price, pnl, position['ticket']))
        
        # Update floating P&L in account
        total_floating = sum(p['floating_pnl'] for p in self.get_positions())
        account = self.get_account()
        self._update_account(account['balance'], total_floating)
        
        self.db.conn.commit()
    
    def reset_account(self) -> Dict:
        """Reset paper account to starting balance"""
        cursor = self.db.conn.cursor()
        
        # Get current account
        account = self.get_account()
        
        # Archive current state
        now = datetime.now(timezone.utc).isoformat()
        
        # Get new starting balance
        starting_balance = self.config.get('paper.starting_balance') or self.DEFAULT_STARTING_BALANCE
        new_reset_count = account.get('reset_count', 0) + 1
        
        # Clear all positions (archive old ones first)
        cursor.execute("UPDATE paper_positions SET status = 'ARCHIVED' WHERE status = 'OPEN'")
        
        # Delete closed positions older than 30 days
        cursor.execute("DELETE FROM paper_positions WHERE status != 'OPEN' AND datetime(close_time) < datetime('now', '-30 days')")
        
        # Create new account entry
        cursor.execute("""
            INSERT INTO paper_account (timestamp, balance, equity, floating_pnl, realized_pnl, total_trades, reset_count)
            VALUES (?, ?, ?, 0, 0, 0, ?)
        """, (now, starting_balance, starting_balance, new_reset_count))
        
        # Log event
        self._log_event('ACCOUNT_RESET', None, None, None, None, None, 0,
                        f"Reset #{new_reset_count} to ${starting_balance}")
        
        self.db.conn.commit()
        
        return {
            'success': True,
            'balance': starting_balance,
            'reset_count': new_reset_count
        }
    
    def _log_event(self, event_type: str, ticket: Optional[str], symbol: Optional[str],
                   direction: Optional[str], lot_size: Optional[float], price: Optional[float],
                   pnl: float, reason: str):
        """Log paper trade event"""
        cursor = self.db.conn.cursor()
        now = datetime.now(timezone.utc).isoformat()
        
        metadata = json.dumps({
            'reason': reason
        })
        
        cursor.execute("""
            INSERT INTO paper_trades_log (timestamp, event_type, ticket, symbol, direction, lot_size, price, pnl, reason, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (now, event_type, ticket, symbol, direction, lot_size, price, pnl, reason, metadata))
        self.db.conn.commit()
    
    def get_stats(self, days: int = 30) -> Dict:
        """Get paper trading statistics"""
        cursor = self.db.conn.cursor()
        
        # Get closed positions in last N days
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
            SELECT COUNT(*), SUM(realized_pnl), AVG(realized_pnl)
            FROM paper_positions
            WHERE status != 'OPEN' AND close_time > ?
        """, (cutoff,))
        
        row = cursor.fetchone()
        total_trades = row[0] or 0
        total_pnl = row[1] or 0
        avg_pnl = row[2] or 0
        
        # Win rate
        cursor.execute("""
            SELECT COUNT(*) FROM paper_positions
            WHERE status != 'OPEN' AND realized_pnl > 0 AND close_time > ?
        """, (cutoff,))
        wins = cursor.fetchone()[0] or 0
        
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        # Daily P&L
        cursor.execute("""
            SELECT date(close_time) as day, SUM(realized_pnl) as daily_pnl
            FROM paper_positions
            WHERE status != 'OPEN' AND close_time > ?
            GROUP BY day
            ORDER BY day DESC
        """, (cutoff,))
        
        daily_pnl = {}
        for row in cursor.fetchall():
            daily_pnl[row[0]] = row[1]
        
        return {
            'total_trades': total_trades,
            'total_pnl': total_pnl,
            'avg_pnl': avg_pnl,
            'win_rate': win_rate,
            'daily_pnl': daily_pnl
        }
    
    def close_all_positions(self) -> int:
        """Close all open paper positions"""
        count = 0
        for position in self.get_positions():
            result = self.close_position(position['ticket'], 'EMERGENCY_STOP')
            if result['success']:
                count += 1
        return count


# Singleton instance
_paper_engine = None


def get_paper_engine() -> PaperEngine:
    """Get paper engine singleton"""
    global _paper_engine
    if _paper_engine is None:
        _paper_engine = PaperEngine()
    return _paper_engine