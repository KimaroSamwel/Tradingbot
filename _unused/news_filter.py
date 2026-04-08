"""
NEWS FILTER & ECONOMIC CALENDAR
Filters trades around high-impact news events
Uses Forex Factory API or similar economic calendar service
"""

import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import json
import os


class NewsImpact(Enum):
    """News impact levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class NewsEvent:
    """Economic news event"""
    time: datetime
    currency: str
    title: str
    impact: NewsImpact
    forecast: Optional[str] = None
    previous: Optional[str] = None
    actual: Optional[str] = None


class EconomicCalendar:
    """
    Economic Calendar API Integration
    
    RECOMMENDED APIs:
    1. **ForexFactory** - Free scraping (https://www.forexfactory.com/calendar)
    2. **TradingEconomics** - Paid API ($50/month) (https://tradingeconomics.com/api)
    3. **Investing.com** - Free scraping
    4. **FXStreet** - Free API (https://www.fxstreet.com/economic-calendar)
    5. **Alpha Vantage** - Free tier available (https://www.alphavantage.co/)
    
    BEST RECOMMENDATION: TradingEconomics API
    - Most reliable and comprehensive
    - Real-time updates
    - Historical data available
    - Good documentation
    - Worth the $50/month for serious trading
    
    ALTERNATIVE (Free): ForexFactory Web Scraping
    - Free but requires web scraping
    - Less reliable than paid API
    - May break if website structure changes
    
    ENHANCED: Time-based fallback for when API is unavailable
    """
    
    def __init__(self, api_key: Optional[str] = None, provider: str = 'tradingeconomics',
                 timezone: str = 'Africa/Nairobi'):
        """
        Initialize economic calendar
        
        Args:
            api_key: API key for chosen provider
            provider: 'tradingeconomics', 'forexfactory', 'alphavantage'
            timezone: Broker timezone (default Africa/Nairobi for GMT+3)
        """
        self.api_key = api_key
        self.provider = provider
        self.timezone = timezone
        self.cache_file = 'data/cache/economic_calendar.json'
        self.cache_duration = timedelta(hours=1)
        
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        
        # Enhanced: Time-based fallback for major events
        self._use_fallback = False
        self._fallback_cache: List[NewsEvent] = []
        self._fallback_loaded = False
    
    def fetch_events(self, start_date: datetime, end_date: datetime,
                     currencies: List[str] = ['USD', 'EUR', 'GBP', 'JPY']) -> List[NewsEvent]:
        """
        Fetch economic events from API
        
        Args:
            start_date: Start date
            end_date: End date
            currencies: List of currencies to track
        
        Returns:
            List of news events
        """
        if self.provider == 'tradingeconomics':
            return self._fetch_tradingeconomics(start_date, end_date, currencies)
        elif self.provider == 'alphavantage':
            return self._fetch_alphavantage(start_date, end_date, currencies)
        else:
            return self._fetch_from_cache()
    
    def _fetch_tradingeconomics(self, start_date: datetime, end_date: datetime,
                                currencies: List[str]) -> List[NewsEvent]:
        """
        Fetch from TradingEconomics API
        
        API Documentation: https://docs.tradingeconomics.com/
        Endpoint: https://api.tradingeconomics.com/calendar
        
        Setup:
        1. Sign up at https://tradingeconomics.com/api
        2. Get API key from dashboard
        3. Add to config.yaml:
           news_filter:
             enabled: true
             api_provider: 'tradingeconomics'
             api_key: 'YOUR_API_KEY_HERE'
        """
        if not self.api_key:
            print("⚠️ TradingEconomics API key not configured")
            print("   Sign up at: https://tradingeconomics.com/api")
            print("   Cost: $50/month for real-time data")
            return []
        
        try:
            url = 'https://api.tradingeconomics.com/calendar'
            params = {
                'c': self.api_key,
                'd1': start_date.strftime('%Y-%m-%d'),
                'd2': end_date.strftime('%Y-%m-%d'),
                'country': ','.join(currencies)
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            events = []
            
            for item in data:
                impact = self._determine_impact(item.get('importance', 1))
                
                events.append(NewsEvent(
                    time=datetime.fromisoformat(item['Date'].replace('Z', '+00:00')),
                    currency=item.get('Country', 'USD'),
                    title=item.get('Event', 'Unknown'),
                    impact=impact,
                    forecast=item.get('Forecast'),
                    previous=item.get('Previous'),
                    actual=item.get('Actual')
                ))
            
            self._save_to_cache(events)
            return events
        
        except Exception as e:
            print(f"❌ Failed to fetch from TradingEconomics: {e}")
            return self._fetch_from_cache_or_fallback()
    
    def _fetch_from_cache_or_fallback(self) -> List[NewsEvent]:
        """Fetch from cache, or use time-based fallback if unavailable"""
        # Try cache first
        cached = self._fetch_from_cache()
        if cached:
            return cached
        
        # Use time-based fallback for known major events
        if not self._fallback_loaded:
            self._load_fallback_events()
        
        return self._fallback_cache
    
    def _fetch_alphavantage(self, start_date: datetime, end_date: datetime,
                           currencies: List[str]) -> List[NewsEvent]:
        """
        Fetch from Alpha Vantage API (Free tier: 5 calls/min, 500/day)
        
        API Documentation: https://www.alphavantage.co/documentation/
        Uses NEWS_SENTIMENT endpoint with forex and economic topics
        
        Setup:
        1. Get free API key: https://www.alphavantage.co/support/#api-key
        2. Add to config.yaml:
           news_filter:
             enabled: true
             api_provider: 'alphavantage'
             api_key: 'YOUR_FREE_API_KEY'
        """
        if not self.api_key:
            print("⚠️ Alpha Vantage API key not configured")
            print("   Get free key at: https://www.alphavantage.co/support/#api-key")
            return []
        
        try:
            # Alpha Vantage NEWS_SENTIMENT endpoint
            url = 'https://www.alphavantage.co/query'
            
            # Build forex tickers from currencies
            forex_tickers = []
            for currency in currencies:
                if currency != 'USD':
                    forex_tickers.append(f'FOREX:{currency}')
            
            # Topics relevant to forex trading
            topics = 'economy_monetary,economy_fiscal,economy_macro,financial_markets'
            
            params = {
                'function': 'NEWS_SENTIMENT',
                'apikey': self.api_key,
                'topics': topics,
                'time_from': start_date.strftime('%Y%m%dT%H%M'),
                'sort': 'LATEST',
                'limit': 200  # Get up to 200 recent articles
            }
            
            # Add forex tickers if specified
            if forex_tickers:
                params['tickers'] = ','.join(forex_tickers)
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            events = []
            
            # Check for API errors
            if 'Error Message' in data:
                print(f"❌ Alpha Vantage API Error: {data['Error Message']}")
                return self._fetch_from_cache()
            
            if 'Note' in data:
                print(f"⚠️ Alpha Vantage Rate Limit: {data['Note']}")
                return self._fetch_from_cache()
            
            # Parse news feed
            if 'feed' in data:
                for item in data['feed']:
                    try:
                        # Parse timestamp
                        time_str = item.get('time_published', '')
                        event_time = datetime.strptime(time_str, '%Y%m%dT%H%M%S')
                        
                        # Determine impact from sentiment scores
                        sentiment_score = float(item.get('overall_sentiment_score', 0))
                        relevance_score = float(item.get('relevance_score', 0))
                        
                        # High relevance + strong sentiment = high impact
                        if relevance_score > 0.7 and abs(sentiment_score) > 0.5:
                            impact = NewsImpact.HIGH
                        elif relevance_score > 0.5 or abs(sentiment_score) > 0.3:
                            impact = NewsImpact.MEDIUM
                        else:
                            impact = NewsImpact.LOW
                        
                        # Extract currency from ticker_sentiment
                        currency = 'USD'  # Default
                        if 'ticker_sentiment' in item and item['ticker_sentiment']:
                            for ticker_info in item['ticker_sentiment']:
                                ticker = ticker_info.get('ticker', '')
                                if ticker.startswith('FOREX:'):
                                    currency = ticker.replace('FOREX:', '')[:3]
                                    break
                        
                        events.append(NewsEvent(
                            time=event_time,
                            currency=currency,
                            title=item.get('title', 'Economic News'),
                            impact=impact,
                            forecast=None,
                            previous=None,
                            actual=f"Sentiment: {sentiment_score:.2f}"
                        ))
                    
                    except Exception as e:
                        # Skip malformed items
                        continue
                
                print(f"✅ Fetched {len(events)} news events from Alpha Vantage")
            
            else:
                print("⚠️ No news feed in Alpha Vantage response")
            
            self._save_to_cache(events)
            return events
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Network error fetching from Alpha Vantage: {e}")
            return self._fetch_from_cache()
        except Exception as e:
            print(f"❌ Failed to fetch from Alpha Vantage: {e}")
            return self._fetch_from_cache_or_fallback()
    
    def _load_fallback_events(self):
        """
        Load time-based fallback for known major economic events
        
        This provides basic protection when API is unavailable.
        Uses known times for major US/European news events.
        """
        self._fallback_cache = []
        now = datetime.now()
        
        # Known high-impact news times (GMT+3 for Nairobi)
        # These are approximate times - real implementation needs calendar API
        high_impact_templates = [
            # US Session News (14:00-17:00 GMT+3)
            {'hour': 14, 'minute': 30, 'currency': 'USD', 'name': 'Non-Farm Employment Change (NFP)', 'day_offset': 'first_friday'},
            {'hour': 15, 'minute': 30, 'currency': 'USD', 'name': 'Core CPI', 'day_offset': None},
            {'hour': 15, 'minute': 30, 'currency': 'USD', 'name': 'Retail Sales', 'day_offset': None},
            {'hour': 16, 'minute': 0, 'currency': 'USD', 'name': 'GDP', 'day_offset': None},
            {'hour': 17, 'minute': 0, 'currency': 'USD', 'name': 'ISM Manufacturing PMI', 'day_offset': None},
            {'hour': 17, 'minute': 0, 'currency': 'USD', 'name': 'ISM Services PMI', 'day_offset': None},
            
            # FOMC/Interest Rate Decisions (18:00-19:00 GMT+3)
            {'hour': 19, 'minute': 0, 'currency': 'USD', 'name': 'FOMC Rate Decision', 'day_offset': 'fomc_week'},
            {'hour': 19, 'minute': 30, 'currency': 'USD', 'name': 'Fed Chair Press Conference', 'day_offset': 'fomc_week'},
            
            # European Session News (15:30-17:00 GMT+3)
            {'hour': 16, 'minute': 0, 'currency': 'EUR', 'name': 'ECB Rate Decision', 'day_offset': 'ecb_week'},
            {'hour': 16, 'minute': 30, 'currency': 'EUR', 'name': 'ECB President Speech', 'day_offset': 'ecb_week'},
            {'hour': 13, 'minute': 0, 'currency': 'GBP', 'name': 'BOE Rate Decision', 'day_offset': 'boe_week'},
            
            # Central Bank Speakers
            {'hour': 17, 'minute': 0, 'currency': 'USD', 'name': 'Fed Official Speech', 'day_offset': None},
            {'hour': 16, 'minute': 0, 'currency': 'EUR', 'name': 'ECB President Speech', 'day_offset': None},
        ]
        
        for day_offset in range(7):  # Check next 7 days
            check_date = now.date() + timedelta(days=day_offset)
            weekday = check_date.weekday()
            
            for template in high_impact_templates:
                event_datetime = datetime.combine(
                    check_date,
                    datetime.min.time().replace(hour=template['hour'], minute=template['minute'])
                )
                
                # Check special conditions
                skip = False
                
                # NFP: Only first Friday of month
                if template.get('day_offset') == 'first_friday':
                    if weekday != 4 or check_date.day > 7:  # Not Friday or not first week
                        skip = True
                
                # FOMC Week: March, June, September, December, 15th-21st
                elif template.get('day_offset') == 'fomc_week':
                    if now.month not in [3, 6, 9, 12]:
                        skip = True
                    if now.day < 15 or now.day > 21:
                        skip = True
                    if weekday not in [1, 2, 3]:  # Tue-Thu
                        skip = True
                
                # ECB Week: Every 6 weeks approximately
                elif template.get('day_offset') == 'ecb_week':
                    # ECB meets every 6 weeks on Thursdays
                    # Approximate - for production use real calendar
                    pass  # Let through
                
                # BOE: Monthly, first Thursday
                elif template.get('day_offset') == 'boe_week':
                    if weekday != 3:  # Not Thursday
                        skip = True
                    if check_date.day > 7:  # Not first week
                        skip = True
                
                if skip:
                    continue
                
                # Skip if more than 24 hours ahead
                if event_datetime > now + timedelta(hours=24):
                    continue
                
                # Skip if more than 30 minutes in the past
                if event_datetime < now - timedelta(minutes=30):
                    continue
                
                event = NewsEvent(
                    time=event_datetime,
                    currency=template['currency'],
                    title=template['name'],
                    impact=NewsImpact.HIGH
                )
                self._fallback_cache.append(event)
        
        self._fallback_loaded = True
        print(f"📅 Loaded {len(self._fallback_cache)} fallback news events")
    
    def is_nfp_day(self) -> bool:
        """Check if today is NFP Friday (first Friday of month)"""
        today = datetime.now()
        return today.weekday() == 4 and today.day <= 7
    
    def is_fomc_week(self) -> bool:
        """Check if current week is FOMC meeting week"""
        today = datetime.now()
        return (today.month in [3, 6, 9, 12] and 
                15 <= today.day <= 21 and 
                today.weekday() in [1, 2, 3])
    
    def _determine_impact(self, importance: int) -> NewsImpact:
        """Determine news impact from importance score"""
        if importance >= 3:
            return NewsImpact.HIGH
        elif importance == 2:
            return NewsImpact.MEDIUM
        else:
            return NewsImpact.LOW
    
    def _save_to_cache(self, events: List[NewsEvent]):
        """Save events to cache"""
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'events': [
                    {
                        'time': e.time.isoformat(),
                        'currency': e.currency,
                        'title': e.title,
                        'impact': e.impact.value,
                        'forecast': e.forecast,
                        'previous': e.previous,
                        'actual': e.actual
                    }
                    for e in events
                ]
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        
        except Exception as e:
            print(f"Failed to cache events: {e}")
    
    def _fetch_from_cache(self) -> List[NewsEvent]:
        """Load events from cache"""
        try:
            if not os.path.exists(self.cache_file):
                return []
            
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time > self.cache_duration:
                return []
            
            events = []
            for item in cache_data['events']:
                events.append(NewsEvent(
                    time=datetime.fromisoformat(item['time']),
                    currency=item['currency'],
                    title=item['title'],
                    impact=NewsImpact(item['impact']),
                    forecast=item.get('forecast'),
                    previous=item.get('previous'),
                    actual=item.get('actual')
                ))
            
            return events
        
        except Exception as e:
            print(f"Failed to load cache: {e}")
            return []


class NewsFilter:
    """
    News-based trade filtering
    Prevents trading during high-impact news releases
    """
    
    def __init__(self, calendar: EconomicCalendar, 
                 buffer_minutes_before: int = 30,
                 buffer_minutes_after: int = 30):
        """
        Initialize news filter
        
        Args:
            calendar: Economic calendar instance
            buffer_minutes_before: Minutes before news to avoid trading
            buffer_minutes_after: Minutes after news to avoid trading
        """
        self.calendar = calendar
        self.buffer_before = timedelta(minutes=buffer_minutes_before)
        self.buffer_after = timedelta(minutes=buffer_minutes_after)
    
    def is_safe_to_trade(self, symbol: str, current_time: Optional[datetime] = None) -> tuple[bool, Optional[str]]:
        """
        Check if trading is allowed (no major news nearby)
        
        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            current_time: Current time (defaults to now)
        
        Returns:
            (is_safe, reason)
        """
        return self.can_trade(symbol, current_time)
    
    def can_trade(self, symbol: str, current_time: Optional[datetime] = None) -> tuple[bool, Optional[str]]:
        """
        Check if trading is allowed (no major news nearby)
        
        Args:
            symbol: Trading symbol (e.g., 'EURUSD')
            current_time: Current time (defaults to now)
        
        Returns:
            (can_trade, reason)
        """
        if current_time is None:
            current_time = datetime.now()
        
        # If no API key configured, allow trading (don't block)
        if not self.calendar.api_key:
            return (True, "News filter disabled (no API key)")
        
        try:
            currency_pair = symbol[:6]
            base_currency = currency_pair[:3]
            quote_currency = currency_pair[3:6]
            
            search_start = current_time - self.buffer_before
            search_end = current_time + self.buffer_after
            
            events = self.calendar.fetch_events(
                search_start,
                search_end,
                currencies=[base_currency, quote_currency]
            )
            
            high_impact_events = [e for e in events if e.impact == NewsImpact.HIGH]
            
            for event in high_impact_events:
                if search_start <= event.time <= search_end:
                    time_diff = abs((event.time - current_time).total_seconds() / 60)
                    return (False, f"High-impact {event.currency} news in {time_diff:.0f} min: {event.title}")
            
            return (True, "No major news nearby")
        
        except Exception as e:
            # If news filter fails, allow trading (fail-safe)
            print(f"⚠️ News filter error (allowing trade): {e}")
            return (True, "News filter unavailable")
    
    def get_upcoming_events(self, hours: int = 24,
                           min_impact: NewsImpact = NewsImpact.MEDIUM) -> List[NewsEvent]:
        """
        Get upcoming high-impact events
        
        Args:
            hours: Hours to look ahead
            min_impact: Minimum impact level
        
        Returns:
            List of upcoming events
        """
        now = datetime.now()
        end_time = now + timedelta(hours=hours)
        
        events = self.calendar.fetch_events(now, end_time)
        
        filtered = [
            e for e in events
            if e.impact.value >= min_impact.value and e.time > now
        ]
        
        filtered.sort(key=lambda x: x.time)
        return filtered
    
    def print_upcoming_events(self, hours: int = 24):
        """Print upcoming high-impact events"""
        events = self.get_upcoming_events(hours, NewsImpact.MEDIUM)
        
        if not events:
            print(f"\n✅ No major news events in next {hours} hours")
            return
        
        print(f"\n📰 Upcoming News Events (Next {hours}h):")
        print("="*80)
        
        for event in events:
            impact_emoji = "🔴" if event.impact == NewsImpact.HIGH else "🟡"
            time_str = event.time.strftime("%Y-%m-%d %H:%M")
            print(f"{impact_emoji} {time_str} | {event.currency} | {event.title}")
        
        print("="*80)
