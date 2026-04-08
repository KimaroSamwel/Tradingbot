"""
FUNDAMENTAL ANALYSIS FOR CURRENCY TRADING
Section I.B - Fundamental Analysis (Currencies)
- Interest rate differentials
- Central bank policy (QE/QT, rate decisions)
- Economic indicators (CPI, GDP, employment)
- Trade balances & political stability
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum


class CentralBankStance(Enum):
    """Central bank monetary policy stance"""
    HAWKISH = "hawkish"          # Raising rates, tightening
    DOVISH = "dovish"            # Cutting rates, easing
    NEUTRAL = "neutral"          # Holding steady
    UNKNOWN = "unknown"


@dataclass
class EconomicIndicators:
    """Economic indicators for a currency"""
    country: str
    currency: str
    
    # Interest rates
    interest_rate: float            # Current policy rate
    expected_rate_change: float     # Expected change in next 6 months
    
    # Inflation
    cpi: float                      # Consumer Price Index YoY %
    pce: float                      # Personal Consumption Expenditure (if US)
    inflation_target: float         # Central bank target (usually 2%)
    
    # Growth
    gdp_growth: float               # GDP growth rate %
    unemployment_rate: float        # Unemployment %
    
    # Trade
    trade_balance: float            # Trade balance (positive = surplus)
    current_account: float          # Current account balance
    
    # Policy
    cb_stance: CentralBankStance    # Central bank stance
    qe_active: bool                 # Quantitative easing active
    
    # Stability
    political_risk_score: float     # 0-10 (0=stable, 10=unstable)
    
    last_updated: datetime


class FundamentalAnalyzer:
    """
    Analyzes fundamental factors for currency pairs
    Based on proven fundamental analysis principles
    """
    
    # Economic data for major currencies (would be updated via API in production)
    CURRENCY_DATA = {
        "USD": EconomicIndicators(
            country="United States", currency="USD",
            interest_rate=5.25, expected_rate_change=0.0,
            cpi=3.1, pce=2.6, inflation_target=2.0,
            gdp_growth=2.5, unemployment_rate=3.7,
            trade_balance=-65.0, current_account=-200.0,
            cb_stance=CentralBankStance.NEUTRAL, qe_active=False,
            political_risk_score=2.0, last_updated=datetime.now()
        ),
        "EUR": EconomicIndicators(
            country="Eurozone", currency="EUR",
            interest_rate=4.50, expected_rate_change=-0.25,
            cpi=2.4, pce=0.0, inflation_target=2.0,
            gdp_growth=0.5, unemployment_rate=6.5,
            trade_balance=25.0, current_account=30.0,
            cb_stance=CentralBankStance.DOVISH, qe_active=False,
            political_risk_score=3.0, last_updated=datetime.now()
        ),
        "GBP": EconomicIndicators(
            country="United Kingdom", currency="GBP",
            interest_rate=5.25, expected_rate_change=0.0,
            cpi=4.0, pce=0.0, inflation_target=2.0,
            gdp_growth=0.3, unemployment_rate=4.2,
            trade_balance=-10.0, current_account=-15.0,
            cb_stance=CentralBankStance.NEUTRAL, qe_active=False,
            political_risk_score=4.0, last_updated=datetime.now()
        ),
        "JPY": EconomicIndicators(
            country="Japan", currency="JPY",
            interest_rate=0.10, expected_rate_change=0.10,
            cpi=2.8, pce=0.0, inflation_target=2.0,
            gdp_growth=1.2, unemployment_rate=2.5,
            trade_balance=-5.0, current_account=15.0,
            cb_stance=CentralBankStance.HAWKISH, qe_active=True,
            political_risk_score=1.0, last_updated=datetime.now()
        ),
        "CHF": EconomicIndicators(
            country="Switzerland", currency="CHF",
            interest_rate=1.75, expected_rate_change=0.0,
            cpi=1.7, pce=0.0, inflation_target=2.0,
            gdp_growth=1.0, unemployment_rate=2.0,
            trade_balance=8.0, current_account=10.0,
            cb_stance=CentralBankStance.NEUTRAL, qe_active=False,
            political_risk_score=0.5, last_updated=datetime.now()
        ),
        "AUD": EconomicIndicators(
            country="Australia", currency="AUD",
            interest_rate=4.35, expected_rate_change=0.0,
            cpi=4.1, pce=0.0, inflation_target=2.5,
            gdp_growth=1.8, unemployment_rate=3.9,
            trade_balance=12.0, current_account=5.0,
            cb_stance=CentralBankStance.NEUTRAL, qe_active=False,
            political_risk_score=1.5, last_updated=datetime.now()
        ),
        "CAD": EconomicIndicators(
            country="Canada", currency="CAD",
            interest_rate=5.00, expected_rate_change=-0.25,
            cpi=3.4, pce=0.0, inflation_target=2.0,
            gdp_growth=1.1, unemployment_rate=5.8,
            trade_balance=2.0, current_account=-1.0,
            cb_stance=CentralBankStance.DOVISH, qe_active=False,
            political_risk_score=1.5, last_updated=datetime.now()
        ),
        "NZD": EconomicIndicators(
            country="New Zealand", currency="NZD",
            interest_rate=5.50, expected_rate_change=-0.25,
            cpi=4.7, pce=0.0, inflation_target=2.0,
            gdp_growth=0.3, unemployment_rate=3.9,
            trade_balance=-2.0, current_account=-6.0,
            cb_stance=CentralBankStance.DOVISH, qe_active=False,
            political_risk_score=1.0, last_updated=datetime.now()
        )
    }
    
    def analyze_pair(self, pair: str) -> Dict:
        """
        Analyze fundamental factors for a currency pair
        
        Args:
            pair: Currency pair (e.g., "EURUSD")
            
        Returns:
            Dict with fundamental analysis and bias
        """
        if len(pair) != 6:
            return {'error': 'Invalid pair format'}
        
        base_currency = pair[:3]
        quote_currency = pair[3:]
        
        base_data = self.CURRENCY_DATA.get(base_currency)
        quote_data = self.CURRENCY_DATA.get(quote_currency)
        
        if not base_data or not quote_data:
            return {'error': 'Currency data not available'}
        
        analysis = {
            'pair': pair,
            'base_currency': base_currency,
            'quote_currency': quote_currency,
            'timestamp': datetime.now()
        }
        
        # 1. Interest Rate Differential (Most important for currencies)
        rate_diff = base_data.interest_rate - quote_data.interest_rate
        expected_rate_diff = (base_data.interest_rate + base_data.expected_rate_change) - \
                            (quote_data.interest_rate + quote_data.expected_rate_change)
        
        analysis['interest_rate_differential'] = rate_diff
        analysis['expected_rate_differential'] = expected_rate_diff
        analysis['rate_diff_change'] = expected_rate_diff - rate_diff
        
        rate_bias = 1 if rate_diff > 1.0 else -1 if rate_diff < -1.0 else 0
        
        # 2. Central Bank Policy Stance
        cb_score = self._compare_cb_stance(base_data.cb_stance, quote_data.cb_stance)
        analysis['cb_policy_score'] = cb_score
        
        # 3. Inflation Differential (High inflation = weakness)
        inflation_diff = base_data.cpi - quote_data.cpi
        analysis['inflation_differential'] = inflation_diff
        inflation_bias = -1 if inflation_diff > 1.0 else 1 if inflation_diff < -1.0 else 0
        
        # 4. Growth Differential (Higher growth = strength)
        growth_diff = base_data.gdp_growth - quote_data.gdp_growth
        analysis['growth_differential'] = growth_diff
        growth_bias = 1 if growth_diff > 1.0 else -1 if growth_diff < -1.0 else 0
        
        # 5. Trade Balance Differential (Surplus = strength)
        trade_diff = base_data.trade_balance - quote_data.trade_balance
        analysis['trade_balance_diff'] = trade_diff
        trade_bias = 1 if trade_diff > 20 else -1 if trade_diff < -20 else 0
        
        # 6. Political Stability (Lower risk = strength)
        stability_diff = quote_data.political_risk_score - base_data.political_risk_score
        analysis['stability_score'] = stability_diff
        stability_bias = 1 if stability_diff > 2 else -1 if stability_diff < -2 else 0
        
        # 7. Calculate Overall Fundamental Bias (Weighted scoring)
        fundamental_score = (
            rate_bias * 0.35 +           # 35% weight to interest rates
            cb_score * 0.25 +            # 25% to central bank policy
            growth_bias * 0.15 +         # 15% to growth
            inflation_bias * 0.10 +      # 10% to inflation
            trade_bias * 0.10 +          # 10% to trade balance
            stability_bias * 0.05        # 5% to political stability
        )
        
        analysis['fundamental_score'] = fundamental_score
        
        # Determine bias
        if fundamental_score > 0.3:
            analysis['bias'] = 'BULLISH'
            analysis['bias_strength'] = 'STRONG' if fundamental_score > 0.6 else 'MODERATE'
        elif fundamental_score < -0.3:
            analysis['bias'] = 'BEARISH'
            analysis['bias_strength'] = 'STRONG' if fundamental_score < -0.6 else 'MODERATE'
        else:
            analysis['bias'] = 'NEUTRAL'
            analysis['bias_strength'] = 'WEAK'
        
        analysis['factors'] = {
            'interest_rates': {'current_diff': rate_diff, 'expected_diff': expected_rate_diff, 'bias': rate_bias, 'weight': 0.35},
            'central_bank_policy': {'base_stance': base_data.cb_stance.value, 'quote_stance': quote_data.cb_stance.value, 'bias': cb_score, 'weight': 0.25},
            'growth': {'diff': growth_diff, 'bias': growth_bias, 'weight': 0.15},
            'inflation': {'diff': inflation_diff, 'bias': inflation_bias, 'weight': 0.10},
            'trade_balance': {'diff': trade_diff, 'bias': trade_bias, 'weight': 0.10},
            'stability': {'diff': stability_diff, 'bias': stability_bias, 'weight': 0.05}
        }
        
        return analysis
    
    def _compare_cb_stance(self, base_stance: CentralBankStance, quote_stance: CentralBankStance) -> float:
        """Compare central bank stances. Returns: -1 to 1"""
        stance_scores = {
            CentralBankStance.HAWKISH: 1.0,
            CentralBankStance.NEUTRAL: 0.0,
            CentralBankStance.DOVISH: -1.0,
            CentralBankStance.UNKNOWN: 0.0
        }
        return (stance_scores[base_stance] - stance_scores[quote_stance]) / 2
    
    def should_trade_fundamental(self, pair: str, technical_signal: str) -> Tuple[bool, str]:
        """
        Check if fundamental analysis supports technical signal
        
        Args:
            pair: Currency pair
            technical_signal: 'BUY' or 'SELL'
            
        Returns:
            (should_trade, reason)
        """
        analysis = self.analyze_pair(pair)
        
        if 'error' in analysis:
            return (True, "No fundamental filter (data unavailable)")
        
        fundamental_bias = analysis['bias']
        bias_strength = analysis['bias_strength']
        
        # Strong fundamental bias opposing technical signal = DON'T TRADE
        if bias_strength == 'STRONG':
            if technical_signal == 'BUY' and fundamental_bias == 'BEARISH':
                return (False, f"Strong bearish fundamentals oppose BUY signal")
            elif technical_signal == 'SELL' and fundamental_bias == 'BULLISH':
                return (False, f"Strong bullish fundamentals oppose SELL signal")
        
        # Fundamental alignment = HIGHER CONFIDENCE
        if technical_signal == 'BUY' and fundamental_bias == 'BULLISH':
            return (True, f"✅ Fundamentals align: {fundamental_bias} ({bias_strength})")
        elif technical_signal == 'SELL' and fundamental_bias == 'BEARISH':
            return (True, f"✅ Fundamentals align: {fundamental_bias} ({bias_strength})")
        
        # Neutral fundamentals = ALLOW TRADE
        if fundamental_bias == 'NEUTRAL':
            return (True, "Fundamentals neutral - technical analysis leads")
        
        # Weak opposing fundamentals = ALLOW BUT CAUTIOUS
        return (True, f"⚠️ Weak {fundamental_bias.lower()} fundamentals - proceed with caution")
