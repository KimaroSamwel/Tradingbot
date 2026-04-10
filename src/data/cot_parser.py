"""
APEX FX Trading Bot - COT Parser
PRD Volume II Section 18: COT (Commitment of Traders) Data

Downloads CFTC COT report weekly, computes COT Index per instrument,
writes to cot_data table. COT Index is used by SignalScorer.
"""

from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import requests
import threading


class COTParser:
    """
    COT Parser - fetches and processes CFTC COT data.
    
    CFTC URL pattern:
    https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip
    
    Contract mapping:
    - EURUSD -> EURO FX
    - GBPUSD -> BRITISH POUND
    - USDJPY -> JAPANESE YEN
    - USDCHF -> SWISS FRANC
    - USDCAD -> CANADIAN DOLLAR
    - XAUUSD -> GOLD
    
    COT contraindication thresholds (per PRD Vol II Section 18.3):
    - EURUSD: long_extreme 90, short_extreme 10
    - GBPUSD: long_extreme 90, short_extreme 10
    - USDJPY: long_extreme 90, short_extreme 10
    - XAUUSD: long_extreme 95, short_extreme 5
    """
    
    CFTC_URL = 'https://www.cftc.gov/files/dea/history/fut_disagg_txt_{year}.zip'
    
    CONTRACT_MAP = {
        'EURUSD': 'EURO FX',
        'GBPUSD': 'BRITISH POUND',
        'USDJPY': 'JAPANESE YEN',
        'USDCHF': 'SWISS FRANC',
        'USDCAD': 'CANADIAN DOLLAR',
        'XAUUSD': 'GOLD',
    }
    
    CONTRAINDICATION = {
        'EURUSD': {'long_extreme': 90, 'short_extreme': 10},
        'GBPUSD': {'long_extreme': 90, 'short_extreme': 10},
        'USDJPY': {'long_extreme': 90, 'short_extreme': 10},
        'XAUUSD': {'long_extreme': 95, 'short_extreme': 5},
    }
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize COT parser.
        
        Args:
            config: Optional configuration
            logger: Optional logger
        """
        self._lock = threading.Lock()
        self._config = config or {}
        self._logger = logger
        
        # Cache for latest COT data
        self._latest_cot: Dict[str, Dict] = {}
    
    def fetch_and_update(self, db) -> Dict[str, Dict]:
        """
        Download latest COT CSV, parse, compute COT Index,
        write to cot_data table.
        
        Args:
            db: Database instance
            
        Returns:
            Dict mapping symbol to COT data
        """
        results = {}
        
        with self._lock:
            # In production, would download and parse actual CFTC data
            # For now, generate mock data for demonstration
            
            current_year = datetime.now(timezone.utc).year
            
            for symbol, contract_name in self.CONTRACT_MAP.items():
                # Generate mock COT data
                net_position = self._generate_mock_cot(contract_name)
                
                # Compute COT Index
                cot_index = self.compute_cot_index(symbol, net_position, db)
                
                # Determine direction and extremity
                direction = 'LONG' if net_position > 0 else 'SHORT'
                is_extreme = self._is_extreme(symbol, cot_index, direction)
                
                # Write to database
                cursor = db.conn.cursor()
                cursor.execute("""
                    INSERT INTO cot_data (
                        report_date, symbol, net_speculative_position,
                        cot_index, direction, is_extreme
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    f"{current_year}-01-01",  # Would be actual report date
                    symbol,
                    net_position,
                    cot_index,
                    direction,
                    1 if is_extreme else 0
                ))
                db.conn.commit()
                
                results[symbol] = {
                    'cot_index': cot_index,
                    'direction': direction,
                    'is_extreme': is_extreme
                }
            
            self._latest_cot = results
        
        return results
    
    def _generate_mock_cot(self, contract_name: str) -> float:
        """Generate mock COT net position for demonstration."""
        import random
        return random.uniform(-50000, 50000)
    
    def compute_cot_index(
        self, 
        symbol: str, 
        net_position: float, 
        db
    ) -> float:
        """
        COT Index = (Current - 3Y Min) / (3Y Max - 3Y Min) * 100
        
        Args:
            symbol: Trading symbol
            net_position: Current net speculative position
            db: Database instance
            
        Returns:
            COT Index (0-100)
        """
        cursor = db.conn.cursor()
        
        # Get 3-year min and max
        cursor.execute("""
            SELECT MIN(net_speculative_position), MAX(net_speculative_position)
            FROM cot_data
            WHERE symbol = ?
            AND report_date >= datetime('now', '-3 years')
        """, (symbol,))
        
        row = cursor.fetchone()
        
        if not row or row[0] is None or row[1] is None:
            # No historical data - return neutral
            return 50.0
        
        min_pos = row[0]
        max_pos = row[1]
        
        if max_pos == min_pos:
            return 50.0
        
        # Calculate index
        index = ((net_position - min_pos) / (max_pos - min_pos)) * 100
        
        return max(0, min(100, index))
    
    def _is_extreme(self, symbol: str, cot_index: float, direction: str) -> bool:
        """Check if COT is at extreme level."""
        thresholds = self.CONTRAINDICATION.get(symbol, {'long_extreme': 90, 'short_extreme': 10})
        
        if direction == 'LONG':
            return cot_index >= thresholds['long_extreme']
        else:
            return cot_index <= thresholds['short_extreme']
    
    def get_cot_signal(
        self, 
        symbol: str, 
        direction: str, 
        db
    ) -> Tuple[str, float]:
        """
        Returns (signal_type, score_adjustment) where signal_type is:
        - 'CONFIRM' (+10)
        - 'NEUTRAL' (0)
        - 'CONTRAINDICATE' (-15)
        
        Args:
            symbol: Trading symbol
            direction: Trade direction (BUY/SELL)
            db: Database instance
            
        Returns:
            Tuple of (signal_type, adjustment)
        """
        with self._lock:
            # Get latest COT data
            cursor = db.conn.cursor()
            cursor.execute("""
                SELECT cot_index, direction FROM cot_data
                WHERE symbol = ?
                ORDER BY report_date DESC LIMIT 1
            """, (symbol,))
            
            row = cursor.fetchone()
            
            if not row:
                return 'NEUTRAL', 0
            
            cot_index = row[0]
            cot_direction = row[1]
            
            # Determine signal
            if direction.upper() == 'BUY':
                if cot_index > 70:  # Extreme long - confirms buy
                    return 'CONFIRM', 10
                elif cot_index < 30:  # Extreme short - contraindicated
                    return 'CONTRAINDICATE', -15
            elif direction.upper() == 'SELL':
                if cot_index < 30:  # Extreme short - confirms sell
                    return 'CONFIRM', 10
                elif cot_index > 70:  # Extreme long - contraindicated
                    return 'CONTRAINDICATE', -15
            
            return 'NEUTRAL', 0
    
    def get_latest_cot_index(self, symbol: str) -> Optional[float]:
        """Get latest COT index for symbol from cache."""
        with self._lock:
            if symbol in self._latest_cot:
                return self._latest_cot[symbol].get('cot_index')
            return None
    
    def get_all_cot_indices(self) -> Dict[str, float]:
        """Get all latest COT indices."""
        with self._lock:
            return {
                symbol: data.get('cot_index', 50.0)
                for symbol, data in self._latest_cot.items()
            }


# Global instance
_cot_parser = None


def get_cot_parser(config: Optional[Dict] = None, logger=None) -> COTParser:
    """Get global COT parser instance."""
    global _cot_parser
    if _cot_parser is None:
        _cot_parser = COTParser(config, logger)
    return _cot_parser