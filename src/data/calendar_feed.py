"""
APEX FX Trading Bot - Economic Calendar Feed
Section 5.5: News Event Blackout Schedule
High/Medium impact events block or reduce trading
"""

import requests
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import time


class ImpactLevel(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class NewsEvent:
    """Economic news event"""
    datetime: datetime
    currency: str
    event: str
    impact: ImpactLevel
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None


class EconomicCalendar:
    """Economic calendar with news blackout management"""
    
    def __init__(self):
        self._events: List[NewsEvent] = []
        self._last_fetch = None
        self._fetch_interval = 3600  # 1 hour
    
    def fetch_calendar(self, days: int = 7) -> List[NewsEvent]:
        """Fetch upcoming economic events"""
        now = datetime.now()
        
        if self._last_fetch and (now - self._last_fetch).total_seconds() < self._fetch_interval:
            return self._get_upcoming_events(days)
        
        try:
            events = self._fetch_from_forexfactory(days)
            self._events = events
            self._last_fetch = now
        except Exception as e:
            print(f"Calendar fetch error: {e}")
            self._events = self._get_default_events()
        
        return self._get_upcoming_events(days)
    
    def _fetch_from_forexfactory(self, days: int) -> List[NewsEvent]:
        """Fetch from Forex Factory API"""
        events = []
        
        try:
            url = "https://nfforexfactory.com/data/calendar"
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    try:
                        event_time = datetime.fromisoformat(item.get('date', ''))
                        if event_time > datetime.now():
                            events.append(NewsEvent(
                                datetime=event_time,
                                currency=item.get('currency', 'USD'),
                                event=item.get('title', ''),
                                impact=ImpactLevel(item.get('impact', 'low'))
                            ))
                    except:
                        pass
        except Exception as e:
            print(f"ForexFactory error: {e}")
        
        return events[:50]  # Limit to 50 events
    
    def _get_default_events(self) -> List[NewsEvent]:
        """Default high-impact events (US/NFP/FOMC dates)"""
        events = []
        
        major_events = [
            {'day': 1, 'month': 4, 'event': 'US Manufacturing PMI', 'currency': 'USD', 'impact': ImpactLevel.HIGH},
            {'day': 3, 'month': 4, 'event': 'FOMC Meeting Minutes', 'currency': 'USD', 'impact': ImpactLevel.HIGH},
            {'day': 5, 'month': 4, 'event': 'US Non-Farm Payrolls', 'currency': 'USD', 'impact': ImpactLevel.HIGH},
            {'day': 10, 'month': 4, 'event': 'US CPI', 'currency': 'USD', 'impact': ImpactLevel.HIGH},
            {'day': 12, 'month': 4, 'event': 'US Retail Sales', 'currency': 'USD', 'impact': ImpactLevel.HIGH},
            {'day': 25, 'month': 4, 'event': 'US GDP', 'currency': 'USD', 'impact': ImpactLevel.HIGH},
            {'day': 30, 'month': 4, 'event': 'FOMC Rate Decision', 'currency': 'USD', 'impact': ImpactLevel.HIGH},
        ]
        
        now = datetime.now()
        for me in major_events:
            try:
                event_date = datetime(now.year, me['month'], me['day'], 13, 30)
                if event_date > now:
                    events.append(NewsEvent(
                        datetime=event_date,
                        currency=me['currency'],
                        event=me['event'],
                        impact=me['impact']
                    ))
            except:
                pass
        
        return events
    
    def _get_upcoming_events(self, days: int) -> List[NewsEvent]:
        """Get events within the next N days"""
        cutoff = datetime.now() + timedelta(days=days)
        return [e for e in self._events if e.datetime <= cutoff]
    
    def is_blackout_time(self, symbol: str, minutes_before: int = 30, minutes_after: int = 15) -> bool:
        """Check if currently in blackout period for a symbol"""
        now = datetime.now()
        
        symbol_currencies = {
            'EURUSD': ['EUR', 'USD'],
            'GBPUSD': ['GBP', 'USD'],
            'USDJPY': ['USD', 'JPY'],
            'USDCHF': ['USD', 'CHF'],
            'USDCAD': ['USD', 'CAD'],
            'XAUUSD': ['USD', 'XAU']
        }
        
        currencies = symbol_currencies.get(symbol, ['USD'])
        
        for event in self._events:
            if event.currency not in currencies:
                continue
            
            if event.impact != ImpactLevel.HIGH:
                continue
            
            before_window = event.datetime - timedelta(minutes=minutes_before)
            after_window = event.datetime + timedelta(minutes=minutes_after)
            
            if before_window <= now <= after_window:
                return True
        
        return False
    
    def get_position_size_reduction(self, symbol: str) -> float:
        """Get position size reduction factor based on upcoming news"""
        now = datetime.now()
        
        symbol_currencies = {
            'EURUSD': ['EUR', 'USD'],
            'GBPUSD': ['GBP', 'USD'],
            'USDJPY': ['USD', 'JPY'],
            'USDCHF': ['USD', 'CHF'],
            'USDCAD': ['USD', 'CAD'],
            'XAUUSD': ['USD', 'XAU']
        }
        
        currencies = symbol_currencies.get(symbol, ['USD'])
        
        for event in self._events:
            if event.currency not in currencies:
                continue
            
            if event.impact == ImpactLevel.MEDIUM:
                time_until = (event.datetime - now).total_seconds() / 60
                if 0 < time_until < 60:
                    return 0.5  # 50% reduction
        
        return 1.0  # No reduction
    
    def is_gold_blackout(self) -> bool:
        """Special 45-minute blackout for gold (CPI, FOMC, NFP, GDP)"""
        now = datetime.now()
        
        gold_events = ['CPI', 'FOMC', 'Non-Farm', 'GDP', 'NFP']
        
        for event in self._events:
            if event.impact != ImpactLevel.HIGH:
                continue
            
            if any(ge.lower() in event.event.lower() for ge in gold_events):
                before_window = event.datetime - timedelta(minutes=45)
                after_window = event.datetime + timedelta(minutes=20)
                
                if before_window <= now <= after_window:
                    return True
        
        return False
    
    def get_upcoming_high_impact(self, hours: int = 4) -> List[NewsEvent]:
        """Get high impact events in the next N hours"""
        cutoff = datetime.now() + timedelta(hours=hours)
        return [
            e for e in self._events
            if e.impact == ImpactLevel.HIGH and datetime.now() < e.datetime < cutoff
        ]


_calendar = None


def get_calendar() -> EconomicCalendar:
    """Get global calendar instance"""
    global _calendar
    if _calendar is None:
        _calendar = EconomicCalendar()
    return _calendar