"""Carry Trade Analyzer - Interest rate differential strategies with swap tracking"""
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from typing import Dict, Optional
import json
import os

@dataclass
class CarrySignal:
    pair: str
    rate_diff: float
    daily_swap_long: float  # Swap for long position
    daily_swap_short: float  # Swap for short position
    wednesday_triple_swap: bool
    bias: str
    confidence: float
    expected_annual_return: float  # From carry alone

@dataclass
class SwapRates:
    """Swap rates for a currency pair"""
    symbol: str
    swap_long: float  # Points per lot per day
    swap_short: float
    last_updated: datetime

class CarryTradeAnalyzer:
    def __init__(self, swap_cache_file: str = 'data/cache/swap_rates.json'):
        # Central bank rates (update monthly)
        self.rates = {
            'USD': 5.25, 'EUR': 4.50, 'GBP': 5.25,
            'JPY': -0.10, 'AUD': 4.35, 'NZD': 5.50,
            'CHF': 1.75, 'CAD': 5.00
        }
        
        # Swap rates cache
        self.swap_cache_file = swap_cache_file
        self.swap_rates: Dict[str, SwapRates] = {}
        self._load_swap_cache()
        
    def _load_swap_cache(self):
        """Load cached swap rates"""
        if os.path.exists(self.swap_cache_file):
            try:
                with open(self.swap_cache_file, 'r') as f:
                    data = json.load(f)
                    for symbol, swap_data in data.items():
                        self.swap_rates[symbol] = SwapRates(
                            symbol=symbol,
                            swap_long=swap_data['swap_long'],
                            swap_short=swap_data['swap_short'],
                            last_updated=datetime.fromisoformat(swap_data['last_updated'])
                        )
            except Exception as e:
                print(f"Error loading swap cache: {e}")
                
    def update_swap_rates(self, symbol: str, swap_long: float, swap_short: float):
        """Update swap rates for a symbol (from MT5 or broker API)"""
        self.swap_rates[symbol] = SwapRates(
            symbol=symbol,
            swap_long=swap_long,
            swap_short=swap_short,
            last_updated=datetime.now()
        )
        self._save_swap_cache()
        
    def _save_swap_cache(self):
        """Save swap rates to cache"""
        os.makedirs(os.path.dirname(self.swap_cache_file), exist_ok=True)
        data = {}
        for symbol, swap in self.swap_rates.items():
            data[symbol] = {
                'swap_long': swap.swap_long,
                'swap_short': swap.swap_short,
                'last_updated': swap.last_updated.isoformat()
            }
        with open(self.swap_cache_file, 'w') as f:
            json.dump(data, f, indent=2)
            
    def update_central_bank_rate(self, currency: str, rate: float):
        """Update central bank rate"""
        self.rates[currency] = rate
        
    def is_wednesday(self, current_time: datetime = None) -> bool:
        """Check if today is Wednesday (triple swap day)"""
        if current_time is None:
            current_time = datetime.now()
        return current_time.weekday() == 2  # Wednesday
        
    def analyze(self, symbol: str, current_time: datetime = None) -> CarrySignal:
        """Full carry trade analysis with swap tracking"""
        if current_time is None:
            current_time = datetime.now()
            
        base = symbol[:3]
        quote = symbol[3:6]
        
        # Interest rate differential
        rate_diff = self.rates.get(base, 0) - self.rates.get(quote, 0)
        
        # Get swap rates (use cached or estimate)
        if symbol in self.swap_rates:
            swap_data = self.swap_rates[symbol]
            swap_long = swap_data.swap_long
            swap_short = swap_data.swap_short
        else:
            # Estimate swap from rate differential
            swap_long = rate_diff * 0.0001  # Rough approximation
            swap_short = -rate_diff * 0.0001
            
        # Wednesday triple swap
        is_wed = self.is_wednesday(current_time)
        
        # Calculate expected annual return from carry
        days_per_year = 365
        if is_wed:
            days_per_year = 365 / 3  # Account for triple swap
            
        # For long position
        annual_return_long = (swap_long * days_per_year) if swap_long > 0 else 0
        # For short position  
        annual_return_short = (swap_short * days_per_year) if swap_short > 0 else 0
        
        expected_return = max(annual_return_long, annual_return_short)
        
        # Determine bias
        if abs(rate_diff) > 3.0:
            bias = "LONG" if rate_diff > 0 else "SHORT"
            conf = 75.0
        elif abs(rate_diff) > 1.5:
            bias = "LONG" if rate_diff > 0 else "SHORT"
            conf = 60.0
        else:
            bias = "NEUTRAL"
            conf = 40.0
            
        return CarrySignal(
            pair=symbol,
            rate_diff=rate_diff,
            daily_swap_long=swap_long,
            daily_swap_short=swap_short,
            wednesday_triple_swap=is_wed,
            bias=bias,
            confidence=conf,
            expected_annual_return=expected_return
        )
    
    def get_top_carry_pairs(self, symbols: list) -> list:
        """Get top carry trade opportunities"""
        signals = [self.analyze(symbol) for symbol in symbols]
        # Sort by expected return
        return sorted(signals, key=lambda x: x.expected_annual_return, reverse=True)
