"""
ICT KILLZONE SESSION FILTER
Time-based filtering for highest probability trading windows

Killzones are specific hourly windows when institutional traders are most active.
Trading outside these windows dramatically reduces win rate.

For XAUUSD (Gold):
- London Open: 3:00-5:00 AM EST (Highest priority)
- NY AM Session: 8:00 AM-12:00 PM EST (High priority)
- Silver Bullet: 10:00-11:00 AM EST (Precision window)
- NY PM: 2:00-3:00 PM EST (Lower priority)
"""

import pandas as pd
from datetime import datetime, time, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pytz


class KillzoneType(Enum):
    """Trading session types"""
    ASIAN = "asian"
    LONDON = "london"
    NY_AM = "ny_am"
    NY_PM = "ny_pm"
    SILVER_BULLET = "silver_bullet"
    OFF_HOURS = "off_hours"


@dataclass
class Killzone:
    """Killzone session definition"""
    name: str
    zone_type: KillzoneType
    start_hour: int  # EST hour (0-23)
    start_minute: int
    end_hour: int
    end_minute: int
    priority: int  # 1=Highest, 3=Lowest
    allow_trades: bool
    description: str


class ICTKillzoneFilter:
    """
    Filter trades based on ICT Killzone timing
    
    Critical Rules:
    1. ONLY trade during London or NY sessions for Gold
    2. Silver Bullet (10-11 AM) is highest probability
    3. Asian session = Range marking only, NO trades
    4. After 3 PM EST = STOP trading (low liquidity)
    """
    
    def __init__(self, broker_timezone: str = 'Africa/Nairobi', flexible_mode: bool = False):
        """
        Args:
            broker_timezone: Broker server timezone (default GMT+3 for Nairobi)
            flexible_mode: If True, allows trading 24/7 (for testing or aggressive trading)
        """
        self.broker_tz = pytz.timezone(broker_timezone)
        self.flexible_mode = flexible_mode  # Allows 24/7 trading if True
        
        # Convert EST times to broker timezone
        # EST = GMT-5, Nairobi = GMT+3, difference = +8 hours
        est_tz = pytz.timezone('America/New_York')
        
        def convert_est_to_broker(est_hour: int, est_minute: int = 0):
            """Convert EST time to broker timezone"""
            # Create a datetime in EST
            from datetime import datetime
            est_time = est_tz.localize(datetime(2024, 1, 1, est_hour, est_minute))
            # Convert to broker timezone
            broker_time = est_time.astimezone(self.broker_tz)
            return broker_time.hour, broker_time.minute
        
        # Define killzones (times converted from EST to broker timezone)
        # London Open: 3-5 AM EST = 11 AM-1 PM GMT+3
        london_start = convert_est_to_broker(3, 0)
        london_end = convert_est_to_broker(5, 0)
        
        # NY Session: 8 AM-5 PM EST = 4 PM-1 AM GMT+3 (next day)
        ny_start = convert_est_to_broker(8, 0)
        ny_end = convert_est_to_broker(17, 0)
        
        # Silver Bullet: 10-11 AM EST = 6-7 PM GMT+3
        sb_start = convert_est_to_broker(10, 0)
        sb_end = convert_est_to_broker(11, 0)
        
        # Asian: 7 PM-2 AM EST = 3 AM-10 AM GMT+3
        asian_start = convert_est_to_broker(19, 0)
        asian_end = convert_est_to_broker(2, 0)
        
        # NY PM: 2-3 PM EST = 10-11 PM GMT+3
        nypm_start = convert_est_to_broker(14, 0)
        nypm_end = convert_est_to_broker(15, 0)
        
        self.killzones = {
            'asian': Killzone(
                name='Asian Session',
                zone_type=KillzoneType.ASIAN,
                start_hour=asian_start[0], start_minute=asian_start[1],
                end_hour=asian_end[0], end_minute=asian_end[1],
                priority=3,
                allow_trades=False,  # Range marking only
                description='Low liquidity - Mark range, no trades'
            ),
            'london': Killzone(
                name='London Open',
                zone_type=KillzoneType.LONDON,
                start_hour=london_start[0], start_minute=london_start[1],
                end_hour=london_end[0], end_minute=london_end[1],
                priority=1,
                allow_trades=True,
                description='Highest priority - Initial trend moves'
            ),
            'ny_am': Killzone(
                name='NY Session (Full)',
                zone_type=KillzoneType.NY_AM,
                start_hour=ny_start[0], start_minute=ny_start[1],
                end_hour=ny_end[0], end_minute=ny_end[1],
                priority=1,
                allow_trades=True,
                description='Full NY session - High liquidity until close'
            ),
            'silver_bullet': Killzone(
                name='Silver Bullet',
                zone_type=KillzoneType.SILVER_BULLET,
                start_hour=sb_start[0], start_minute=sb_start[1],
                end_hour=sb_end[0], end_minute=sb_end[1],
                priority=1,
                allow_trades=True,
                description='HIGHEST precision - 70-80% win rate'
            ),
            'ny_pm': Killzone(
                name='NY PM Session',
                zone_type=KillzoneType.NY_PM,
                start_hour=nypm_start[0], start_minute=nypm_start[1],
                end_hour=nypm_end[0], end_minute=nypm_end[1],
                priority=2,
                allow_trades=True,
                description='Medium priority - Late reversal only'
            )
        }
        
        self.current_killzone: Optional[Killzone] = None
        self.session_stats = {
            'london': {'trades': 0, 'wins': 0},
            'ny_am': {'trades': 0, 'wins': 0},
            'silver_bullet': {'trades': 0, 'wins': 0},
            'ny_pm': {'trades': 0, 'wins': 0}
        }
    
    def get_current_killzone(self, current_time: Optional[datetime] = None) -> Killzone:
        """
        Get current killzone based on time
        
        Args:
            current_time: Time to check (defaults to now)
            
        Returns:
            Current Killzone object
        """
        if current_time is None:
            current_time = datetime.now(self.broker_tz)
        
        # Ensure timezone aware
        if current_time.tzinfo is None:
            current_time = self.broker_tz.localize(current_time)
        
        current_hour = current_time.hour
        current_minute = current_time.minute
        
        # Check each killzone
        for kz_name, kz in self.killzones.items():
            if self._is_time_in_killzone(current_hour, current_minute, kz):
                self.current_killzone = kz
                return kz
        
        # Default: Off hours
        self.current_killzone = Killzone(
            name='Off Hours',
            zone_type=KillzoneType.OFF_HOURS,
            start_hour=0, start_minute=0,
            end_hour=0, end_minute=0,
            priority=99,
            allow_trades=False,
            description='Outside trading hours - DO NOT TRADE'
        )
        return self.current_killzone
    
    def _is_time_in_killzone(self, hour: int, minute: int, kz: Killzone) -> bool:
        """Check if time falls within killzone"""
        current_minutes = hour * 60 + minute
        start_minutes = kz.start_hour * 60 + kz.start_minute
        end_minutes = kz.end_hour * 60 + kz.end_minute
        
        # Handle overnight sessions (e.g., Asian 19:00-02:00)
        if end_minutes < start_minutes:
            # Session crosses midnight
            return current_minutes >= start_minutes or current_minutes < end_minutes
        else:
            return start_minutes <= current_minutes < end_minutes
    
    def is_trading_allowed(self, current_time: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Check if trading is allowed at current time
        
        Args:
            current_time: Time to check
            
        Returns:
            (is_allowed, reason)
        """
        # If flexible mode enabled, allow trading 24/7
        if self.flexible_mode:
            return (True, "Flexible mode - 24/7 trading enabled")
        
        kz = self.get_current_killzone(current_time)
        
        if kz.allow_trades:
            return (True, f"{kz.name} - {kz.description}")
        else:
            return (False, f"{kz.name} - Trading not allowed")
    
    def get_killzone_priority(self, current_time: Optional[datetime] = None) -> int:
        """
        Get priority of current killzone (1=Highest)
        
        Args:
            current_time: Time to check
            
        Returns:
            Priority level (1-3)
        """
        kz = self.get_current_killzone(current_time)
        return kz.priority
    
    def is_silver_bullet_window(self, current_time: Optional[datetime] = None) -> bool:
        """
        Check if currently in Silver Bullet window (10-11 AM EST)
        
        This is the HIGHEST probability trading window
        
        Args:
            current_time: Time to check
            
        Returns:
            True if Silver Bullet active
        """
        kz = self.get_current_killzone(current_time)
        return kz.zone_type == KillzoneType.SILVER_BULLET
    
    def is_london_session(self, current_time: Optional[datetime] = None) -> bool:
        """Check if London Open killzone is active"""
        kz = self.get_current_killzone(current_time)
        return kz.zone_type == KillzoneType.LONDON
    
    def is_ny_session(self, current_time: Optional[datetime] = None) -> bool:
        """Check if any NY session is active"""
        kz = self.get_current_killzone(current_time)
        return kz.zone_type in [KillzoneType.NY_AM, KillzoneType.NY_PM, KillzoneType.SILVER_BULLET]
    
    def get_next_killzone(self, current_time: Optional[datetime] = None) -> Tuple[Killzone, int]:
        """
        Get next upcoming killzone and minutes until start
        
        Args:
            current_time: Current time
            
        Returns:
            (next_killzone, minutes_until)
        """
        if current_time is None:
            current_time = datetime.now(self.broker_tz)
        
        current_minutes = current_time.hour * 60 + current_time.minute
        
        # Build list of all killzone start times
        kz_times = []
        for kz_name, kz in self.killzones.items():
            if kz.allow_trades:  # Only tradeable sessions
                start_minutes = kz.start_hour * 60 + kz.start_minute
                kz_times.append((start_minutes, kz))
        
        # Sort by start time
        kz_times.sort(key=lambda x: x[0])
        
        # Find next upcoming
        for start_min, kz in kz_times:
            if start_min > current_minutes:
                minutes_until = start_min - current_minutes
                return (kz, minutes_until)
        
        # If none found, next is tomorrow's first session
        first_kz = kz_times[0][1]
        minutes_until = (24 * 60) - current_minutes + kz_times[0][0]
        return (first_kz, minutes_until)
    
    def get_session_stats(self) -> Dict:
        """Get trading statistics by session"""
        stats = {}
        for session, data in self.session_stats.items():
            if data['trades'] > 0:
                win_rate = (data['wins'] / data['trades']) * 100
            else:
                win_rate = 0.0
            
            stats[session] = {
                'trades': data['trades'],
                'wins': data['wins'],
                'losses': data['trades'] - data['wins'],
                'win_rate': win_rate
            }
        
        return stats
    
    def record_trade_result(self, session_name: str, won: bool) -> None:
        """
        Record trade result for session tracking
        
        Args:
            session_name: 'london', 'ny_am', 'silver_bullet', 'ny_pm'
            won: True if trade won
        """
        if session_name in self.session_stats:
            self.session_stats[session_name]['trades'] += 1
            if won:
                self.session_stats[session_name]['wins'] += 1
    
    def get_optimal_sessions_for_symbol(self, symbol: str) -> List[str]:
        """
        Get recommended sessions for specific symbols
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of recommended session names
        """
        # Gold (XAUUSD) sessions
        if 'XAU' in symbol or 'GOLD' in symbol:
            return ['london', 'silver_bullet', 'ny_am']
        
        # EUR pairs (London + NY)
        elif 'EUR' in symbol:
            return ['london', 'ny_am']
        
        # GBP pairs (London heavy)
        elif 'GBP' in symbol:
            return ['london', 'ny_am']
        
        # JPY pairs (Asian + NY)
        elif 'JPY' in symbol:
            return ['ny_am', 'ny_pm']
        
        # Default
        else:
            return ['london', 'ny_am']
    
    def should_trade_symbol_now(self, symbol: str, 
                                current_time: Optional[datetime] = None) -> Tuple[bool, str]:
        """
        Check if symbol should be traded at current time
        
        Args:
            symbol: Trading symbol
            current_time: Time to check
            
        Returns:
            (should_trade, reason)
        """
        # First check if any trading allowed
        allowed, reason = self.is_trading_allowed(current_time)
        if not allowed:
            return (False, reason)
        
        # Get current session
        kz = self.get_current_killzone(current_time)
        
        # Get optimal sessions for symbol
        optimal_sessions = self.get_optimal_sessions_for_symbol(symbol)
        
        # Map killzone type to session name
        session_map = {
            KillzoneType.LONDON: 'london',
            KillzoneType.NY_AM: 'ny_am',
            KillzoneType.SILVER_BULLET: 'silver_bullet',
            KillzoneType.NY_PM: 'ny_pm'
        }
        
        current_session = session_map.get(kz.zone_type)
        
        if current_session in optimal_sessions:
            return (True, f"Optimal session for {symbol}: {kz.name}")
        else:
            return (False, f"Not optimal session for {symbol}")
    
    def get_time_until_next_session(self, current_time: Optional[datetime] = None) -> str:
        """
        Get formatted string showing time until next session
        
        Returns:
            Human-readable time string
        """
        next_kz, minutes = self.get_next_killzone(current_time)
        
        hours = minutes // 60
        mins = minutes % 60
        
        if hours > 0:
            return f"{hours}h {mins}m until {next_kz.name}"
        else:
            return f"{mins}m until {next_kz.name}"
    
    def validate_trade_timing(self, symbol: str, 
                             current_time: Optional[datetime] = None) -> Dict:
        """
        Comprehensive timing validation for trade
        
        Args:
            symbol: Trading symbol
            current_time: Time to validate
            
        Returns:
            Dict with validation results
        """
        kz = self.get_current_killzone(current_time)
        allowed, reason = self.is_trading_allowed(current_time)
        should_trade, symbol_reason = self.should_trade_symbol_now(symbol, current_time)
        
        return {
            'allowed': allowed and should_trade,
            'current_killzone': kz.name,
            'killzone_priority': kz.priority,
            'is_silver_bullet': self.is_silver_bullet_window(current_time),
            'reason': symbol_reason if should_trade else reason,
            'next_session': self.get_time_until_next_session(current_time)
        }
