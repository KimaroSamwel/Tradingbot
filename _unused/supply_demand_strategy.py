"""
SUPPLY & DEMAND TRADING STRATEGY
Complete implementation of institutional supply/demand methodology

Features:
- Zone detection and management
- Multi-timeframe validation
- Rejection pattern recognition
- Zone strength scoring
- Risk management based on zone quality
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.strategies.supply_demand_detector import SupplyDemandDetector, SupplyDemandZone


@dataclass
class SDTradeSignal:
    """Supply/Demand trade signal"""
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    zone: SupplyDemandZone
    confidence: float  # 0-100
    pattern: str
    risk_reward: float
    position_size_multiplier: float  # Based on zone quality


class SupplyDemandStrategy:
    """
    Professional Supply & Demand Trading Strategy
    
    Entry Requirements:
    1. Price touches high-quality zone
    2. Rejection pattern confirmed
    3. Zone strength ≥ minimum threshold
    4. Multi-timeframe alignment (optional)
    5. Risk:Reward ≥ 1:2
    """
    
    def __init__(self,
                 min_zone_strength: float = 5.0,
                 require_htf_alignment: bool = True,
                 min_risk_reward: float = 2.0,
                 max_zone_tests: int = 3):
        """
        Args:
            min_zone_strength: Minimum zone strength score (0-10)
            require_htf_alignment: Require higher timeframe zone alignment
            min_risk_reward: Minimum R:R ratio
            max_zone_tests: Maximum zone tests before considering exhausted
        """
        self.detector = SupplyDemandDetector(
            lookback=100,
            min_move_atr=1.5,
            max_base_candles=5,
            min_strength=min_zone_strength
        )
        
        self.min_zone_strength = min_zone_strength
        self.require_htf_alignment = require_htf_alignment
        self.min_risk_reward = min_risk_reward
        self.max_zone_tests = max_zone_tests
        
        # Active zones by timeframe
        self.zones_h4: List[SupplyDemandZone] = []
        self.zones_h1: List[SupplyDemandZone] = []
        self.zones_m15: List[SupplyDemandZone] = []
    
    def analyze(self, df_h4: pd.DataFrame, df_h1: pd.DataFrame, 
                df_m15: pd.DataFrame) -> Optional[SDTradeSignal]:
        """
        Analyze for supply/demand trade opportunities
        
        Args:
            df_h4: 4-hour timeframe data
            df_h1: 1-hour timeframe data
            df_m15: 15-minute timeframe data
            
        Returns:
            Trade signal or None
        """
        # Update zones for each timeframe
        self.zones_h4 = self.detector.find_zones(df_h4, 'H4')
        self.zones_h1 = self.detector.find_zones(df_h1, 'H1')
        self.zones_m15 = self.detector.find_zones(df_m15, 'M15')
        
        # Update zone test counts
        self.zones_h4 = self.detector.update_zone_tests(self.zones_h4, df_h4)
        self.zones_h1 = self.detector.update_zone_tests(self.zones_h1, df_h1)
        self.zones_m15 = self.detector.update_zone_tests(self.zones_m15, df_m15)
        
        # Get current price
        current_price = df_m15['close'].iloc[-1]
        current_low = df_m15['low'].iloc[-1]
        current_high = df_m15['high'].iloc[-1]
        
        # Check M15 zones for touches
        for zone in self.zones_m15:
            # Skip exhausted zones
            if zone.tested_count > self.max_zone_tests:
                continue
            
            # Skip weak zones
            if zone.strength < self.min_zone_strength:
                continue
            
            # Check if zone was touched
            if not self.detector.check_zone_touch(zone, current_low, current_high):
                continue
            
            # Check for rejection pattern
            has_rejection, pattern = self.detector.check_rejection_pattern(df_m15, zone)
            
            if not has_rejection:
                continue
            
            # Check multi-timeframe alignment if required
            if self.require_htf_alignment:
                htf_aligned = self._check_htf_alignment(zone, self.zones_h1, self.zones_h4)
                if not htf_aligned:
                    continue
            
            # Generate trade signal
            signal = self._generate_signal(zone, current_price, pattern, df_m15)
            
            if signal and signal.risk_reward >= self.min_risk_reward:
                return signal
        
        return None
    
    def _check_htf_alignment(self, m15_zone: SupplyDemandZone,
                            h1_zones: List[SupplyDemandZone],
                            h4_zones: List[SupplyDemandZone]) -> bool:
        """
        Check if M15 zone aligns with higher timeframe zones
        
        Returns:
            True if HTF zone exists at same level
        """
        # Check H1 zones
        for h1_zone in h1_zones:
            if (h1_zone.zone_type == m15_zone.zone_type and
                self._zones_align(m15_zone, h1_zone)):
                return True
        
        # Check H4 zones (stronger confirmation)
        for h4_zone in h4_zones:
            if (h4_zone.zone_type == m15_zone.zone_type and
                self._zones_align(m15_zone, h4_zone)):
                return True
        
        return False
    
    def _zones_align(self, zone1: SupplyDemandZone, zone2: SupplyDemandZone, 
                     tolerance: float = 0.002) -> bool:
        """
        Check if two zones align (within tolerance)
        
        Args:
            zone1: First zone
            zone2: Second zone
            tolerance: Overlap tolerance (0.002 = 0.2%)
            
        Returns:
            True if zones overlap significantly
        """
        # Calculate overlap
        overlap_top = min(zone1.top, zone2.top)
        overlap_bottom = max(zone1.bottom, zone2.bottom)
        
        if overlap_bottom > overlap_top:
            return False  # No overlap
        
        overlap_size = overlap_top - overlap_bottom
        zone1_size = zone1.top - zone1.bottom
        
        # Check if overlap is significant
        overlap_ratio = overlap_size / zone1_size if zone1_size > 0 else 0
        
        return overlap_ratio >= 0.5  # At least 50% overlap
    
    def _generate_signal(self, zone: SupplyDemandZone, current_price: float,
                        pattern: str, df: pd.DataFrame) -> Optional[SDTradeSignal]:
        """
        Generate trade signal from zone touch
        
        Args:
            zone: Touched zone
            current_price: Current market price
            pattern: Rejection pattern detected
            df: M15 dataframe
            
        Returns:
            Trade signal or None
        """
        atr = df['atr'].iloc[-1] if 'atr' in df.columns else zone.zone_width * 2
        
        if zone.zone_type == 'demand':
            # LONG setup
            direction = 'LONG'
            entry_price = current_price
            stop_loss = zone.bottom - (zone.zone_width * 0.15)  # 15% below zone
            
            # Multiple take profit levels
            risk = entry_price - stop_loss
            take_profit_1 = entry_price + (risk * 1.5)  # 1:1.5 R:R
            take_profit_2 = entry_price + (risk * 2.5)  # 1:2.5 R:R
            take_profit_3 = entry_price + (risk * 4.0)  # 1:4 R:R
            
            risk_reward = (take_profit_2 - entry_price) / risk if risk > 0 else 0
        
        else:  # supply
            # SHORT setup
            direction = 'SHORT'
            entry_price = current_price
            stop_loss = zone.top + (zone.zone_width * 0.15)  # 15% above zone
            
            # Multiple take profit levels
            risk = stop_loss - entry_price
            take_profit_1 = entry_price - (risk * 1.5)
            take_profit_2 = entry_price - (risk * 2.5)
            take_profit_3 = entry_price - (risk * 4.0)
            
            risk_reward = (entry_price - take_profit_2) / risk if risk > 0 else 0
        
        # Calculate confidence based on zone quality
        confidence = self._calculate_confidence(zone, pattern)
        
        # Position size multiplier based on zone quality
        position_multiplier = self._get_position_multiplier(zone)
        
        return SDTradeSignal(
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
            take_profit_2=take_profit_2,
            take_profit_3=take_profit_3,
            zone=zone,
            confidence=confidence,
            pattern=pattern,
            risk_reward=risk_reward,
            position_size_multiplier=position_multiplier
        )
    
    def _calculate_confidence(self, zone: SupplyDemandZone, pattern: str) -> float:
        """
        Calculate signal confidence (0-100)
        
        Factors:
        - Zone strength (0-40)
        - Zone freshness (0-30)
        - Rejection pattern (0-20)
        - HTF alignment (0-10)
        """
        confidence = 0.0
        
        # Zone strength (0-40)
        confidence += (zone.strength / 10.0) * 40
        
        # Freshness (0-30)
        if zone.is_fresh():
            confidence += 30
        elif zone.is_prime():
            confidence += 20
        else:
            confidence += 5
        
        # Pattern strength (0-20)
        pattern_scores = {
            'BULLISH_PIN_BAR': 20,
            'BEARISH_PIN_BAR': 20,
            'BULLISH_ENGULFING': 18,
            'BEARISH_ENGULFING': 18
        }
        confidence += pattern_scores.get(pattern, 10)
        
        # HTF alignment bonus (0-10)
        if self.require_htf_alignment:
            confidence += 10
        
        return min(confidence, 100.0)
    
    def _get_position_multiplier(self, zone: SupplyDemandZone) -> float:
        """
        Get position size multiplier based on zone quality
        
        Returns:
            Multiplier (0.5 - 1.5)
        """
        if zone.strength >= 8.0 and zone.is_fresh():
            return 1.5  # Strong fresh zone
        elif zone.strength >= 7.0 and zone.is_fresh():
            return 1.3
        elif zone.strength >= 6.0 and zone.is_prime():
            return 1.0  # Normal position
        elif zone.strength >= 5.0:
            return 0.8
        else:
            return 0.5  # Weak zone
    
    def get_active_zones_summary(self) -> Dict:
        """
        Get summary of active zones for all timeframes
        
        Returns:
            Dictionary with zone counts and details
        """
        return {
            'h4_zones': {
                'total': len(self.zones_h4),
                'demand': len([z for z in self.zones_h4 if z.zone_type == 'demand']),
                'supply': len([z for z in self.zones_h4 if z.zone_type == 'supply']),
                'fresh': len([z for z in self.zones_h4 if z.is_fresh()])
            },
            'h1_zones': {
                'total': len(self.zones_h1),
                'demand': len([z for z in self.zones_h1 if z.zone_type == 'demand']),
                'supply': len([z for z in self.zones_h1 if z.zone_type == 'supply']),
                'fresh': len([z for z in self.zones_h1 if z.is_fresh()])
            },
            'm15_zones': {
                'total': len(self.zones_m15),
                'demand': len([z for z in self.zones_m15 if z.zone_type == 'demand']),
                'supply': len([z for z in self.zones_m15 if z.zone_type == 'supply']),
                'fresh': len([z for z in self.zones_m15 if z.is_fresh()])
            }
        }
    
    def get_nearest_zones(self, current_price: float, max_distance_pct: float = 0.02) -> Dict:
        """
        Get nearest zones to current price
        
        Args:
            current_price: Current market price
            max_distance_pct: Maximum distance in percentage (0.02 = 2%)
            
        Returns:
            Dictionary with nearest demand and supply zones
        """
        max_distance = current_price * max_distance_pct
        
        nearest_demand = None
        nearest_supply = None
        
        # Check M15 zones (most recent/relevant)
        for zone in self.zones_m15:
            distance = abs((zone.top + zone.bottom) / 2 - current_price)
            
            if distance > max_distance:
                continue
            
            if zone.zone_type == 'demand' and zone.top < current_price:
                if nearest_demand is None or zone.top > nearest_demand.top:
                    nearest_demand = zone
            
            elif zone.zone_type == 'supply' and zone.bottom > current_price:
                if nearest_supply is None or zone.bottom < nearest_supply.bottom:
                    nearest_supply = zone
        
        return {
            'nearest_demand': nearest_demand,
            'nearest_supply': nearest_supply,
            'demand_distance': (current_price - nearest_demand.top) if nearest_demand else None,
            'supply_distance': (nearest_supply.bottom - current_price) if nearest_supply else None
        }
