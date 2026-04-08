"""
SEASONALITY PATTERN ANALYZER
Identifies recurring calendar-based patterns in forex markets

Patterns:
1. Monthly patterns (month-end flows, tax deadlines)
2. Weekly patterns (Tuesday trends, Friday profit-taking)
3. Intraday patterns (session overlaps, key times)
4. Quarterly patterns (window dressing)
5. Annual patterns (Japanese fiscal year)

References:
- "Trading Strategies Based on Seasonal Patterns" - academic papers
- Bank rebalancing flows observation
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from enum import Enum


class DayOfWeek(Enum):
    """Day of week enumeration"""
    MONDAY = 0
    TUESDAY = 1
    WEDNESDAY = 2
    THURSDAY = 3
    FRIDAY = 4
    SATURDAY = 5
    SUNDAY = 6


class MonthOfYear(Enum):
    """Month enumeration"""
    JANUARY = 1
    FEBRUARY = 2
    MARCH = 3
    APRIL = 4
    MAY = 5
    JUNE = 6
    JULY = 7
    AUGUST = 8
    SEPTEMBER = 9
    OCTOBER = 10
    NOVEMBER = 11
    DECEMBER = 12


@dataclass
class SeasonalityPattern:
    """Seasonality pattern detected"""
    pattern_type: str  # MONTHLY, WEEKLY, INTRADAY, QUARTERLY
    description: str
    bullish_bias: float  # -1 to +1 (negative = bearish)
    confidence: float  # 0-100
    historical_win_rate: float
    recommendation: str


@dataclass
class CalendarEvent:
    """Important calendar event"""
    event_type: str
    date: datetime
    description: str
    expected_impact: str  # HIGH, MEDIUM, LOW
    trading_bias: str  # BULLISH, BEARISH, NEUTRAL


class MonthlyPatternAnalyzer:
    """
    Analyzes monthly recurring patterns
    """
    
    def __init__(self):
        self.patterns = {
            # Month-end patterns
            'month_end_rebalancing': {
                'days': [-2, -1, 1],  # Last 2 days + first day
                'description': 'Month-end portfolio rebalancing',
                'impact': 'HIGH'
            },
            # Quarter-end patterns
            'quarter_end_window_dressing': {
                'months': [3, 6, 9, 12],
                'days': [-3, -2, -1],
                'description': 'Quarter-end window dressing',
                'impact': 'HIGH'
            },
            # Tax patterns
            'japanese_fiscal_year': {
                'months': [3, 9],  # March and September
                'description': 'Japanese fiscal year repatriation flows',
                'impact': 'HIGH',
                'currency_bias': {'USDJPY': -1}  # Yen strengthening
            },
            # Seasonal patterns
            'santa_rally': {
                'month': 12,
                'description': 'December risk-on rally',
                'impact': 'MEDIUM',
                'risk_bias': 'RISK_ON'
            },
            'sell_in_may': {
                'month': 5,
                'description': 'May equity weakness',
                'impact': 'LOW',
                'risk_bias': 'RISK_OFF'
            }
        }
        
    def analyze_month(self, current_date: datetime, 
                     symbol: str) -> List[SeasonalityPattern]:
        """
        Analyze monthly patterns for current date
        
        Args:
            current_date: Current datetime
            symbol: Trading symbol
            
        Returns:
            List of active monthly patterns
        """
        patterns = []
        
        month = current_date.month
        day = current_date.day
        
        # Check if near month-end
        last_day = self._get_last_trading_day(current_date)
        days_to_month_end = (last_day - current_date).days
        
        if days_to_month_end <= 2 or day == 1:
            patterns.append(SeasonalityPattern(
                pattern_type="MONTHLY",
                description="Month-end rebalancing period",
                bullish_bias=0.0,  # Neutral, increased volatility
                confidence=75.0,
                historical_win_rate=0.55,
                recommendation="Expect increased volatility and potential reversals"
            ))
            
        # Quarter-end check
        if month in [3, 6, 9, 12] and days_to_month_end <= 3:
            patterns.append(SeasonalityPattern(
                pattern_type="QUARTERLY",
                description="Quarter-end window dressing",
                bullish_bias=0.2,  # Slight bullish bias (buying)
                confidence=70.0,
                historical_win_rate=0.58,
                recommendation="Watch for fund manager position adjustments"
            ))
            
        # Japanese fiscal year (March/September)
        if month in [3, 9] and 'JPY' in symbol:
            bias = -0.5 if symbol.endswith('JPY') else 0.5
            patterns.append(SeasonalityPattern(
                pattern_type="MONTHLY",
                description="Japanese fiscal year repatriation",
                bullish_bias=bias,
                confidence=65.0,
                historical_win_rate=0.60,
                recommendation="JPY tends to strengthen during repatriation"
            ))
            
        # December Santa Rally
        if month == 12 and 'USD' in symbol:
            patterns.append(SeasonalityPattern(
                pattern_type="MONTHLY",
                description="Santa Rally risk-on sentiment",
                bullish_bias=0.3,
                confidence=55.0,
                historical_win_rate=0.56,
                recommendation="Risk currencies may strengthen vs safe havens"
            ))
            
        return patterns
    
    def _get_last_trading_day(self, current_date: datetime) -> datetime:
        """Get last trading day of month"""
        # Simplified - assumes last day is trading day
        if current_date.month == 12:
            return datetime(current_date.year + 1, 1, 1)
        else:
            return datetime(current_date.year, current_date.month + 1, 1)


class WeeklyPatternAnalyzer:
    """
    Analyzes weekly recurring patterns
    """
    
    def __init__(self):
        self.day_biases = {
            DayOfWeek.MONDAY: {
                'description': 'Gap trading and position establishment',
                'volatility': 'MEDIUM',
                'bias': 0.0
            },
            DayOfWeek.TUESDAY: {
                'description': 'Strongest trending day',
                'volatility': 'HIGH',
                'bias': 0.1  # Slight continuation bias
            },
            DayOfWeek.WEDNESDAY: {
                'description': 'Midweek momentum continuation',
                'volatility': 'HIGH',
                'bias': 0.1
            },
            DayOfWeek.THURSDAY: {
                'description': 'European option expiry effects',
                'volatility': 'MEDIUM',
                'bias': 0.0
            },
            DayOfWeek.FRIDAY: {
                'description': 'Profit-taking and position squaring',
                'volatility': 'HIGH',
                'bias': -0.2  # Mean reversion bias
            },
            DayOfWeek.SATURDAY: {
                'description': 'Weekend session - limited/closed liquidity',
                'volatility': 'LOW',
                'bias': 0.0
            },
            DayOfWeek.SUNDAY: {
                'description': 'Weekend/market reopen transition',
                'volatility': 'LOW',
                'bias': 0.0
            }
        }
        
    def analyze_day_of_week(self, current_date: datetime) -> SeasonalityPattern:
        """
        Analyze weekly patterns
        
        Args:
            current_date: Current datetime
            
        Returns:
            Seasonality pattern for the day
        """
        day_enum = DayOfWeek(current_date.weekday())
        day_info = self.day_biases.get(day_enum, {
            'description': 'Non-standard trading day',
            'volatility': 'LOW',
            'bias': 0.0
        })
        
        return SeasonalityPattern(
            pattern_type="WEEKLY",
            description=f"{day_enum.name}: {day_info['description']}",
            bullish_bias=day_info['bias'],
            confidence=60.0,
            historical_win_rate=0.52,
            recommendation=self._get_day_recommendation(day_enum)
        )
    
    def _get_day_recommendation(self, day: DayOfWeek) -> str:
        """Get trading recommendation for day of week"""
        if day == DayOfWeek.MONDAY:
            return "Watch for gap fills and range establishment"
        elif day in [DayOfWeek.TUESDAY, DayOfWeek.WEDNESDAY]:
            return "Favor trend-following strategies"
        elif day == DayOfWeek.THURSDAY:
            return "Be aware of option expiry volatility"
        elif day == DayOfWeek.FRIDAY:
            return "Reduce exposure, watch for profit-taking reversals"
        else:
            return "Limited liquidity - avoid trading"


class IntradayPatternAnalyzer:
    """
    Analyzes intraday time-based patterns
    """
    
    def __init__(self, timezone_offset: int = 3):  # GMT+3 for Nairobi
        """
        Args:
            timezone_offset: Offset from GMT (default 3 for Nairobi)
        """
        self.timezone_offset = timezone_offset
        
        # Define key times in GMT+3
        self.key_times = {
            'tokyo_open': {'hour': 5, 'impact': 'MEDIUM'},
            'london_open': {'hour': 11, 'impact': 'HIGH'},
            'ny_open': {'hour': 16, 'impact': 'HIGH'},
            'london_4pm_fix': {'hour': 19, 'impact': 'HIGH'},  # WMR fixing
            'london_close': {'hour': 19, 'impact': 'MEDIUM'},
            'ny_close': {'hour': 0, 'impact': 'LOW'}
        }
        
    def analyze_intraday(self, current_time: datetime) -> List[SeasonalityPattern]:
        """
        Analyze intraday patterns
        
        Args:
            current_time: Current datetime
            
        Returns:
            List of active intraday patterns
        """
        patterns = []
        hour = current_time.hour
        
        # 9:30 AM NY open (16:30 GMT+3)
        if hour == 16 and current_time.minute >= 30:
            patterns.append(SeasonalityPattern(
                pattern_type="INTRADAY",
                description="NYSE open - high volatility spike",
                bullish_bias=0.0,
                confidence=80.0,
                historical_win_rate=0.54,
                recommendation="Wait 15-30 minutes for volatility to settle"
            ))
            
        # London open (11:00 GMT+3)
        if hour == 11:
            patterns.append(SeasonalityPattern(
                pattern_type="INTRADAY",
                description="London session open - strong trends",
                bullish_bias=0.1,
                confidence=75.0,
                historical_win_rate=0.57,
                recommendation="Favor breakout and trend strategies"
            ))
            
        # London/NY overlap (16:00-19:00 GMT+3)
        if 16 <= hour < 19:
            patterns.append(SeasonalityPattern(
                pattern_type="INTRADAY",
                description="London/NY overlap - highest liquidity",
                bullish_bias=0.0,
                confidence=85.0,
                historical_win_rate=0.58,
                recommendation="Best time for trading - tight spreads, strong moves"
            ))
            
        # Lunch hour (12:00-14:00 GMT+3)
        if 12 <= hour < 14:
            patterns.append(SeasonalityPattern(
                pattern_type="INTRADAY",
                description="European lunch - reduced liquidity",
                bullish_bias=0.0,
                confidence=70.0,
                historical_win_rate=0.48,
                recommendation="Range trading preferred, avoid breakouts"
            ))
            
        # London 4PM WMR Fixing (19:00 GMT+3)
        if hour == 19 and current_time.minute < 30:
            patterns.append(SeasonalityPattern(
                pattern_type="INTRADAY",
                description="London 4PM WMR fixing - institutional flows",
                bullish_bias=0.0,
                confidence=80.0,
                historical_win_rate=0.55,
                recommendation="Sharp moves possible during fixing window (15:50-16:10 GMT). Watch GBP pairs especially."
            ))
            
        # Asian session (21:00-5:00 GMT+3)
        if hour >= 21 or hour < 5:
            patterns.append(SeasonalityPattern(
                pattern_type="INTRADAY",
                description="Asian session - low volatility",
                bullish_bias=0.0,
                confidence=65.0,
                historical_win_rate=0.50,
                recommendation="Range trading for JPY pairs, avoid EUR/GBP"
            ))
            
        return patterns


class SeasonalityAnalyzer:
    """
    Master seasonality analyzer coordinating all timeframes
    """
    
    def __init__(self, timezone_offset: int = 3):
        self.monthly = MonthlyPatternAnalyzer()
        self.weekly = WeeklyPatternAnalyzer()
        self.intraday = IntradayPatternAnalyzer(timezone_offset)
        
    def analyze_all_patterns(self, current_time: datetime,
                            symbol: str) -> Dict[str, List[SeasonalityPattern]]:
        """
        Analyze all seasonality patterns
        
        Args:
            current_time: Current datetime
            symbol: Trading symbol
            
        Returns:
            Dictionary of patterns by type
        """
        return {
            'monthly': self.monthly.analyze_month(current_time, symbol),
            'weekly': [self.weekly.analyze_day_of_week(current_time)],
            'intraday': self.intraday.analyze_intraday(current_time)
        }
    
    def get_overall_bias(self, current_time: datetime,
                        symbol: str) -> Tuple[float, str]:
        """
        Get overall seasonality bias
        
        Args:
            current_time: Current datetime
            symbol: Trading symbol
            
        Returns:
            (bias_score, recommendation)
        """
        all_patterns = self.analyze_all_patterns(current_time, symbol)
        
        total_bias = 0.0
        total_confidence = 0.0
        
        for pattern_type, patterns in all_patterns.items():
            for pattern in patterns:
                weight = pattern.confidence / 100.0
                total_bias += pattern.bullish_bias * weight
                total_confidence += weight
                
        if total_confidence > 0:
            overall_bias = total_bias / total_confidence
        else:
            overall_bias = 0.0
            
        # Generate recommendation
        if overall_bias > 0.2:
            recommendation = "Bullish seasonality bias - favor long positions"
        elif overall_bias < -0.2:
            recommendation = "Bearish seasonality bias - favor short positions"
        else:
            recommendation = "Neutral seasonality - trade technically"
            
        return overall_bias, recommendation
    
    def get_active_events(self, current_time: datetime,
                         symbol: str) -> List[CalendarEvent]:
        """
        Get active calendar events affecting trading
        
        Args:
            current_time: Current datetime
            symbol: Trading symbol
            
        Returns:
            List of active calendar events
        """
        events = []
        
        # Check for month-end
        last_day = self.monthly._get_last_trading_day(current_time)
        days_to_end = (last_day - current_time).days
        
        if days_to_end <= 2:
            events.append(CalendarEvent(
                event_type="MONTH_END",
                date=last_day,
                description="Month-end rebalancing flows",
                expected_impact="HIGH",
                trading_bias="NEUTRAL"
            ))
            
        # Check for quarter-end
        if current_time.month in [3, 6, 9, 12] and days_to_end <= 3:
            events.append(CalendarEvent(
                event_type="QUARTER_END",
                date=last_day,
                description="Quarter-end window dressing",
                expected_impact="HIGH",
                trading_bias="BULLISH"
            ))
            
        return events
