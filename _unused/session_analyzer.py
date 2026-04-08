"""
Session-Aware Trading Logic
Adapts strategies based on Asian, London, and New York sessions
"""

from datetime import datetime, timezone
from typing import Dict, Tuple
from dataclasses import dataclass
from enum import Enum


class TradingSession(Enum):
    ASIAN = "ASIAN"
    LONDON = "LONDON"
    NEW_YORK = "NEW_YORK"
    LONDON_NY_OVERLAP = "LONDON_NY_OVERLAP"
    OFF_HOURS = "OFF_HOURS"


@dataclass
class SessionAnalysis:
    current_session: TradingSession
    volatility_expected: str  # LOW, MEDIUM, HIGH
    liquidity_level: str  # LOW, MEDIUM, HIGH
    preferred_style: str  # BREAKOUT, MEAN_REVERSION, TREND
    size_multiplier: float
    spread_tolerance: int
    trade_frequency: str  # LOW, MEDIUM, HIGH


class SessionAnalyzer:
    """
    Professional session detection and strategy adaptation
    """
    
    def __init__(self):
        # Session definitions (GMT/UTC)
        self.sessions = {
            'ASIAN': {
                'start': 0,
                'end': 8,
                'description': 'Tokyo/Hong Kong/Singapore',
                'characteristics': {
                    'volatility': 'LOW',
                    'liquidity': 'MEDIUM',
                    'style': 'MEAN_REVERSION',
                    'size_multiplier': 0.7,
                    'spread_tolerance': 15,
                    'trade_frequency': 'LOW'
                }
            },
            'LONDON': {
                'start': 8,
                'end': 16,
                'description': 'London session',
                'characteristics': {
                    'volatility': 'HIGH',
                    'liquidity': 'HIGH',
                    'style': 'BREAKOUT',
                    'size_multiplier': 1.0,
                    'spread_tolerance': 20,
                    'trade_frequency': 'HIGH'
                }
            },
            'NEW_YORK': {
                'start': 13,
                'end': 21,
                'description': 'New York session',
                'characteristics': {
                    'volatility': 'HIGH',
                    'liquidity': 'HIGH',
                    'style': 'TREND',
                    'size_multiplier': 1.0,
                    'spread_tolerance': 20,
                    'trade_frequency': 'HIGH'
                }
            },
            'OVERLAP': {
                'start': 13,
                'end': 16,
                'description': 'London-New York overlap',
                'characteristics': {
                    'volatility': 'VERY_HIGH',
                    'liquidity': 'VERY_HIGH',
                    'style': 'BREAKOUT',
                    'size_multiplier': 1.2,
                    'spread_tolerance': 25,
                    'trade_frequency': 'VERY_HIGH'
                }
            }
        }
        
        # Asset-specific session behavior
        self.asset_preferences = {
            'EURUSD': ['LONDON', 'OVERLAP', 'NEW_YORK'],
            'GBPUSD': ['LONDON', 'OVERLAP', 'NEW_YORK'],
            'USDJPY': ['ASIAN', 'NEW_YORK', 'OVERLAP'],
            'AUDUSD': ['ASIAN', 'LONDON'],
            'XAUUSD': ['LONDON', 'OVERLAP', 'NEW_YORK'],  # Gold
            'XAGUSD': ['LONDON', 'OVERLAP', 'NEW_YORK']   # Silver
        }
    
    def analyze_session(
        self,
        symbol: str,
        current_time: datetime = None
    ) -> SessionAnalysis:
        """
        Analyze current session and return trading parameters
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        hour_gmt = current_time.hour
        
        # Determine session
        session = self._identify_session(hour_gmt)
        
        # Get session characteristics
        characteristics = self._get_session_characteristics(session, symbol)
        
        # Asset-specific adjustments
        adjusted_chars = self._adjust_for_asset(symbol, session, characteristics)
        
        return SessionAnalysis(
            current_session=session,
            volatility_expected=adjusted_chars['volatility'],
            liquidity_level=adjusted_chars['liquidity'],
            preferred_style=adjusted_chars['style'],
            size_multiplier=adjusted_chars['size_multiplier'],
            spread_tolerance=adjusted_chars['spread_tolerance'],
            trade_frequency=adjusted_chars['trade_frequency']
        )
    
    def _identify_session(self, hour_gmt: int) -> TradingSession:
        """Identify which session we're in"""
        # London-NY Overlap (highest priority)
        if 13 <= hour_gmt < 16:
            return TradingSession.LONDON_NY_OVERLAP
        
        # London
        if 8 <= hour_gmt < 16:
            return TradingSession.LONDON
        
        # New York
        if 13 <= hour_gmt < 21:
            return TradingSession.NEW_YORK
        
        # Asian
        if 0 <= hour_gmt < 8:
            return TradingSession.ASIAN
        
        # Off hours
        return TradingSession.OFF_HOURS
    
    def _get_session_characteristics(
        self,
        session: TradingSession,
        symbol: str
    ) -> Dict:
        """Get base characteristics for session"""
        session_map = {
            TradingSession.ASIAN: self.sessions['ASIAN']['characteristics'],
            TradingSession.LONDON: self.sessions['LONDON']['characteristics'],
            TradingSession.NEW_YORK: self.sessions['NEW_YORK']['characteristics'],
            TradingSession.LONDON_NY_OVERLAP: self.sessions['OVERLAP']['characteristics'],
            TradingSession.OFF_HOURS: {
                'volatility': 'VERY_LOW',
                'liquidity': 'LOW',
                'style': 'NONE',
                'size_multiplier': 0.3,
                'spread_tolerance': 10,
                'trade_frequency': 'NONE'
            }
        }
        
        return session_map.get(session, session_map[TradingSession.OFF_HOURS]).copy()
    
    def _adjust_for_asset(
        self,
        symbol: str,
        session: TradingSession,
        characteristics: Dict
    ) -> Dict:
        """
        Adjust session characteristics based on asset type
        """
        # Clean symbol
        clean_symbol = symbol.replace('.', '').replace('_', '').upper()
        
        # Gold and Silver adjustments
        if 'XAU' in clean_symbol or 'GOLD' in clean_symbol:
            return self._adjust_for_gold(session, characteristics)
        
        if 'XAG' in clean_symbol or 'SILVER' in clean_symbol:
            return self._adjust_for_silver(session, characteristics)
        
        # JPY pairs during Asian session
        if 'JPY' in clean_symbol and session == TradingSession.ASIAN:
            characteristics['volatility'] = 'MEDIUM'
            characteristics['liquidity'] = 'HIGH'
            characteristics['size_multiplier'] = 0.9
        
        # GBP pairs during London
        if 'GBP' in clean_symbol and session in [TradingSession.LONDON, TradingSession.LONDON_NY_OVERLAP]:
            characteristics['volatility'] = 'VERY_HIGH'
            characteristics['size_multiplier'] = 0.9  # Reduce size due to high volatility
        
        # EUR pairs during overlap
        if 'EUR' in clean_symbol and session == TradingSession.LONDON_NY_OVERLAP:
            characteristics['liquidity'] = 'VERY_HIGH'
            characteristics['style'] = 'TREND'
        
        return characteristics
    
    def _adjust_for_gold(self, session: TradingSession, chars: Dict) -> Dict:
        """Gold-specific session adjustments"""
        # Gold is most active during London and NY
        if session == TradingSession.LONDON_NY_OVERLAP:
            chars['volatility'] = 'VERY_HIGH'
            chars['liquidity'] = 'VERY_HIGH'
            chars['style'] = 'MOMENTUM'
            chars['size_multiplier'] = 0.7  # Reduce size due to high volatility
            chars['spread_tolerance'] = 30
            chars['trade_frequency'] = 'HIGH'
        
        elif session == TradingSession.LONDON:
            chars['volatility'] = 'HIGH'
            chars['liquidity'] = 'HIGH'
            chars['style'] = 'BREAKOUT'
            chars['size_multiplier'] = 0.8
            chars['spread_tolerance'] = 25
        
        elif session == TradingSession.NEW_YORK:
            chars['volatility'] = 'HIGH'
            chars['liquidity'] = 'HIGH'
            chars['style'] = 'TREND'
            chars['size_multiplier'] = 0.8
            chars['spread_tolerance'] = 25
        
        elif session == TradingSession.ASIAN:
            chars['volatility'] = 'LOW'
            chars['liquidity'] = 'MEDIUM'
            chars['style'] = 'MEAN_REVERSION'
            chars['size_multiplier'] = 0.5
            chars['spread_tolerance'] = 20
            chars['trade_frequency'] = 'VERY_LOW'
        
        else:  # OFF_HOURS
            chars['volatility'] = 'VERY_LOW'
            chars['liquidity'] = 'VERY_LOW'
            chars['style'] = 'NONE'
            chars['size_multiplier'] = 0.0
            chars['trade_frequency'] = 'NONE'
        
        return chars
    
    def _adjust_for_silver(self, session: TradingSession, chars: Dict) -> Dict:
        """Silver-specific session adjustments"""
        # Silver follows similar pattern to gold but more volatile
        if session == TradingSession.LONDON_NY_OVERLAP:
            chars['volatility'] = 'EXTREME'
            chars['liquidity'] = 'HIGH'
            chars['style'] = 'BREAKOUT'
            chars['size_multiplier'] = 0.5  # Very aggressive, reduce size
            chars['spread_tolerance'] = 40
        
        elif session in [TradingSession.LONDON, TradingSession.NEW_YORK]:
            chars['volatility'] = 'VERY_HIGH'
            chars['liquidity'] = 'MEDIUM'
            chars['style'] = 'MOMENTUM'
            chars['size_multiplier'] = 0.6
            chars['spread_tolerance'] = 35
        
        else:
            # Avoid silver during low liquidity sessions
            chars['size_multiplier'] = 0.3
            chars['trade_frequency'] = 'NONE'
        
        return chars
    
    def is_session_optimal(self, symbol: str, session_analysis: SessionAnalysis) -> bool:
        """
        Check if current session is optimal for the asset
        """
        clean_symbol = symbol.replace('.', '').replace('_', '').upper()
        
        # Get preferred sessions for this asset
        for key in self.asset_preferences:
            if key in clean_symbol:
                session_name = session_analysis.current_session.name
                return session_name in self.asset_preferences[key]
        
        # Default: allow London, Overlap, and NY
        return session_analysis.current_session in [
            TradingSession.LONDON,
            TradingSession.LONDON_NY_OVERLAP,
            TradingSession.NEW_YORK
        ]
    
    def get_session_risk_adjustment(self, session_analysis: SessionAnalysis) -> float:
        """
        Get risk multiplier based on session quality
        """
        multiplier_map = {
            TradingSession.LONDON_NY_OVERLAP: 1.0,
            TradingSession.LONDON: 0.9,
            TradingSession.NEW_YORK: 0.9,
            TradingSession.ASIAN: 0.6,
            TradingSession.OFF_HOURS: 0.3
        }
        
        return multiplier_map.get(
            session_analysis.current_session,
            0.5
        ) * session_analysis.size_multiplier
