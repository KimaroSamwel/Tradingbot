"""
APEX FX Trading Bot - Portfolio Heat Monitor
PRD Volume II Section 9: Portfolio Heat Management

Computes and enforces portfolio heat — the sum of potential loss across
all open positions if every stop-loss is hit simultaneously.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timezone
import threading


@dataclass
class PositionRisk:
    """Risk information for a single position"""
    ticket: int
    symbol: str
    direction: str
    volume: float
    entry_price: float
    current_price: float
    stop_loss: float
    risk_amount: float  # Potential loss in account currency


class PortfolioHeatMonitor:
    """
    Portfolio Heat Monitor - computes and enforces heat limits.
    
    Heat levels:
    - COLD (0-2%): All pairs trade freely
    - WARM (2-3%): New entries only if signal score >= 80
    - HOT (3-4%): No new positions
    - CRITICAL (>4%): No new positions + partial close lowest conviction
    """
    
    HEAT_LEVELS = {
        'COLD': {'max_pct': 2.0, 'rule': 'All pairs trade freely'},
        'WARM': {'max_pct': 3.0, 'rule': 'New entries only if signal score >= 80'},
        'HOT': {'max_pct': 4.0, 'rule': 'No new positions'},
        'CRITICAL': {'max_pct': 999, 'rule': 'No new positions + partial close lowest conviction'},
    }
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize the heat monitor.
        
        Args:
            config: Optional configuration dict
            logger: Optional logger instance
        """
        self._lock = threading.Lock()
        self._config = config or {}
        self._logger = logger
        
        # Store signal scores for positions (ticket -> score)
        self._position_scores: Dict[int, float] = {}
        
        # Heat state
        self._last_heat_pct: float = 0.0
        self._last_heat_level: str = 'COLD'
    
    def calculate_heat(self, positions: List[Dict], account_equity: float) -> Tuple[float, str]:
        """
        Compute total portfolio heat as % of equity.
        
        For each position: risk = abs(current_price - stop_loss) * lots * pip_value_per_lot
        Sum all risks, divide by equity.
        
        Args:
            positions: List of position dicts from MT5
            account_equity: Current account equity
            
        Returns:
            Tuple of (heat_pct, heat_level_name)
        """
        with self._lock:
            total_risk = 0.0
            
            for pos in positions:
                symbol = pos.get('symbol', '')
                direction = pos.get('type', '')
                volume = pos.get('volume', 0)
                current_price = pos.get('price_current', 0)
                stop_loss = pos.get('sl', 0)
                
                if stop_loss <= 0:
                    continue
                
                # Calculate risk per position
                risk = self._calculate_position_risk(
                    symbol, direction, volume, current_price, stop_loss
                )
                total_risk += risk
            
            # Calculate heat as percentage of equity
            heat_pct = (total_risk / account_equity * 100) if account_equity > 0 else 0
            
            # Determine heat level
            heat_level = self._get_heat_level(heat_pct)
            
            self._last_heat_pct = heat_pct
            self._last_heat_level = heat_level
            
            return heat_pct, heat_level
    
    def _calculate_position_risk(
        self, 
        symbol: str, 
        direction: str, 
        volume: float, 
        current_price: float, 
        stop_loss: float
    ) -> float:
        """
        Calculate the risk amount for a single position.
        
        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            volume: Position volume in lots
            current_price: Current market price
            stop_loss: Stop loss price
            
        Returns:
            Risk amount in account currency
        """
        # Price distance to stop loss
        price_distance = abs(current_price - stop_loss)
        
        # Pip value per lot (simplified - in real implementation, fetch from MT5)
        pip_value = self._get_pip_value(symbol)
        
        # Risk = price_distance * volume * pip_value
        risk = price_distance * volume * pip_value
        
        return risk
    
    def _get_pip_value(self, symbol: str) -> float:
        """
        Get pip value per lot for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Pip value in account currency per lot
        """
        pip_values = {
            'EURUSD': 100000,
            'GBPUSD': 100000,
            'USDJPY': 100000,
            'USDCHF': 100000,
            'USDCAD': 100000,
            'XAUUSD': 100,  # Gold is quoted in USD per oz
        }
        return pip_values.get(symbol, 100000)
    
    def _get_heat_level(self, heat_pct: float) -> str:
        """
        Determine heat level based on heat percentage.
        
        Args:
            heat_pct: Current heat percentage
            
        Returns:
            Heat level name
        """
        if heat_pct <= self.HEAT_LEVELS['COLD']['max_pct']:
            return 'COLD'
        elif heat_pct <= self.HEAT_LEVELS['WARM']['max_pct']:
            return 'WARM'
        elif heat_pct <= self.HEAT_LEVELS['HOT']['max_pct']:
            return 'HOT'
        else:
            return 'CRITICAL'
    
    def can_open_new_position(
        self, 
        current_heat: float, 
        signal_score: float
    ) -> Tuple[bool, str]:
        """
        Returns (allowed, reason) based on current heat level and signal score.
        
        Args:
            current_heat: Current portfolio heat percentage
            signal_score: Signal score for the new trade (0-100)
            
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        with self._lock:
            heat_level = self._get_heat_level(current_heat)
            
            if heat_level == 'COLD':
                return True, 'Heat is COLD - trading allowed'
            
            elif heat_level == 'WARM':
                if signal_score >= 80:
                    return True, 'Heat is WARM but signal score >= 80'
                else:
                    return False, f'Heat is WARM but signal score {signal_score} < 80'
            
            elif heat_level == 'HOT':
                return False, 'Heat is HOT - no new positions allowed'
            
            else:  # CRITICAL
                return False, 'Heat is CRITICAL - no new positions allowed'
    
    def store_signal_score(self, ticket: int, score: float) -> None:
        """
        Store the signal score for a position.
        
        Args:
            ticket: MT5 position ticket
            score: Signal score at entry
        """
        with self._lock:
            self._position_scores[ticket] = score
    
    def get_partial_close_candidate(
        self, 
        positions: List[Dict], 
        signal_scores: Optional[Dict[int, float]] = None
    ) -> Optional[int]:
        """
        When heat is CRITICAL, return the ticket of the lowest-conviction
        open trade (lowest signal score at entry).
        
        Args:
            positions: List of open positions
            signal_scores: Optional dict mapping ticket to signal score
            
        Returns:
            Ticket of lowest conviction position, or None
        """
        scores = signal_scores or self._position_scores
        
        if not scores:
            return None
        
        # Find position with lowest score
        lowest_ticket = None
        lowest_score = float('inf')
        
        for pos in positions:
            ticket = pos.get('ticket')
            if ticket in scores:
                if scores[ticket] < lowest_score:
                    lowest_score = scores[ticket]
                    lowest_ticket = ticket
        
        return lowest_ticket
    
    def log_heat_state(
        self, 
        db, 
        open_positions_count: int, 
        action_taken: Optional[str] = None
    ) -> None:
        """
        Log current heat state to database.
        
        Args:
            db: Database instance
            open_positions_count: Number of open positions
            action_taken: Optional action taken (e.g., 'partial_close')
        """
        with self._lock:
            try:
                cursor = db.conn.cursor()
                cursor.execute("""
                    INSERT INTO portfolio_heat_log (
                        timestamp, heat_pct, heat_level, open_positions_count, action_taken
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    datetime.now(timezone.utc).isoformat(),
                    self._last_heat_pct,
                    self._last_heat_level,
                    open_positions_count,
                    action_taken
                ))
                db.conn.commit()
            except Exception as e:
                if self._logger:
                    self._logger.error('heat_log_error', error=str(e))
    
    def get_current_heat(self) -> Tuple[float, str]:
        """
        Get the last calculated heat state.
        
        Returns:
            Tuple of (heat_pct, heat_level)
        """
        with self._lock:
            return self._last_heat_pct, self._last_heat_level


# Global instance
_heat_monitor = None


def get_heat_monitor(config: Optional[Dict] = None, logger=None) -> PortfolioHeatMonitor:
    """Get global portfolio heat monitor instance."""
    global _heat_monitor
    if _heat_monitor is None:
        _heat_monitor = PortfolioHeatMonitor(config, logger)
    return _heat_monitor