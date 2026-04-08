"""
ICT 2022 MENTORSHIP MODEL - COMPLETE STRATEGY
Combines all ICT elements into a cohesive trading system

Strategy Flow:
1. Daily Bias (H4) - Determine market direction
2. Killzone Filter - Trade only during London/NY
3. Liquidity Sweep - Wait for SSL/BSL manipulation
4. Market Structure Shift - Confirm trend change
5. Fair Value Gap Entry - Enter on retest
6. Risk Management - Stops beyond liquidity, TPs at opposing pools
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

from src.ict.liquidity_detector import ICTLiquidityDetector, LiquiditySweep
from src.ict.market_structure import ICTMarketStructure, StructureShift
from src.ict.fvg_detector import ICTFVGDetector, FairValueGap
from src.ict.killzone_filter import ICTKillzoneFilter


@dataclass
class ICTTradeSignal:
    """Complete ICT trade signal"""
    direction: str  # 'LONG' or 'SHORT'
    entry_price: float
    stop_loss: float
    take_profit_1: float  # 50% exit
    take_profit_2: float  # 30% exit
    take_profit_3: float  # 20% trailing
    
    # ICT Components
    liquidity_sweep: Optional[LiquiditySweep]
    structure_shift: Optional[StructureShift]
    entry_fvg: Optional[FairValueGap]
    
    # Confluence Score
    confluence_score: float  # 0-100
    
    # Metadata
    symbol: str
    timeframe: str
    signal_time: datetime
    killzone: str
    
    # Risk
    risk_reward_ratio: float
    position_size: float


class ICT2022Strategy:
    """
    ICT 2022 Mentorship Model Implementation
    
    This is the PRIMARY strategy for XAUUSD trading
    Win Rate Target: 65-75%
    Risk:Reward: Minimum 1:2
    """
    
    def __init__(self, symbol: str = 'XAUUSD'):
        """
        Args:
            symbol: Trading symbol
        """
        self.symbol = symbol
        
        # Initialize ICT components
        self.liquidity_detector = ICTLiquidityDetector(
            lookback_bars=20,
            equal_level_tolerance_pips=2.0,
            min_sweep_pips=1.0,
            min_rejection_ratio=2.0
        )
        
        self.structure_detector = ICTMarketStructure(
            swing_lookback=10,
            min_break_pips=5.0
        )
        
        self.fvg_detector = ICTFVGDetector(
            min_gap_pips=5.0,
            min_body_ratio=0.5,
            use_ote=True
        )
        
        self.killzone_filter = ICTKillzoneFilter()
        
        # Configuration
        self.min_confluence_score = 70.0
        self.min_rr_ratio = 2.0
        
    def analyze(self, df_h4: pd.DataFrame, df_h1: pd.DataFrame, 
               df_m15: pd.DataFrame) -> Optional[ICTTradeSignal]:
        """
        Complete ICT analysis across timeframes
        
        Args:
            df_h4: H4 data (daily bias)
            df_h1: H1 data (structure)
            df_m15: M15 data (entry)
            
        Returns:
            ICTTradeSignal or None
        """
        # Step 1: Killzone Filter (CRITICAL)
        timing_valid = self.killzone_filter.validate_trade_timing(self.symbol)
        if not timing_valid['allowed']:
            return None
        
        # Step 2: Daily Bias (H4)
        daily_bias = self._get_daily_bias(df_h4)
        if daily_bias == 'NEUTRAL':
            return None
        
        # Step 3: Market Structure (H1)
        structure_analysis = self.structure_detector.analyze_structure(df_h1)
        structure_valid, structure_reason = self.structure_detector.validate_structure_for_trade(daily_bias)
        
        if not structure_valid:
            return None
        
        # Step 4: Liquidity Sweep Detection (M15)
        liquidity_pools = self.liquidity_detector.identify_liquidity_pools(df_m15)
        sweeps = self.liquidity_detector.detect_sweeps(df_m15, liquidity_pools)
        
        latest_sweep = self.liquidity_detector.get_latest_sweep()
        if not latest_sweep or not latest_sweep.rejection_confirmed:
            return None
        
        # Step 5: Structure Shift Confirmation
        latest_structure_shift = self.structure_detector.get_latest_shift()
        if not latest_structure_shift:
            return None
        
        # Validate sweep and structure alignment
        if daily_bias == 'LONG':
            # Need SSL sweep + bullish MSS
            if latest_sweep.sweep_type != 'SSL':
                return None
            if latest_structure_shift.direction != 'bullish':
                return None
        else:  # SHORT
            # Need BSL sweep + bearish MSS
            if latest_sweep.sweep_type != 'BSL':
                return None
            if latest_structure_shift.direction != 'bearish':
                return None
        
        # Step 6: Fair Value Gap Entry
        self.fvg_detector.detect_fvgs(df_m15)
        self.fvg_detector.update_fvg_fills(df_m15)
        
        current_price = df_m15.iloc[-1]['close']
        
        if daily_bias == 'LONG':
            entry_fvg = self.fvg_detector.get_nearest_fvg(current_price, 'bullish')
        else:
            entry_fvg = self.fvg_detector.get_nearest_fvg(current_price, 'bearish')
        
        if not entry_fvg or entry_fvg.filled:
            return None
        
        # Check if price is in OTE zone
        if not self.fvg_detector.is_price_in_ote_zone(current_price, entry_fvg):
            return None
        
        # Step 7: Calculate Entry and Stops
        signal = self._calculate_trade_parameters(
            daily_bias,
            current_price,
            latest_sweep,
            latest_structure_shift,
            entry_fvg,
            df_m15,
            timing_valid['current_killzone']
        )
        
        # Step 8: Confluence Score
        if signal:
            signal.confluence_score = self._calculate_confluence_score(
                daily_bias,
                latest_sweep,
                latest_structure_shift,
                entry_fvg,
                timing_valid
            )
            
            if signal.confluence_score < self.min_confluence_score:
                return None
        
        return signal
    
    def _get_daily_bias(self, df_h4: pd.DataFrame) -> str:
        """
        Determine daily trading bias from H4
        
        Returns:
            'LONG' | 'SHORT' | 'NEUTRAL'
        """
        if len(df_h4) < 50:
            return 'NEUTRAL'
        
        current = df_h4.iloc[-1]
        
        # Calculate EMA 50
        ema_50 = df_h4['close'].ewm(span=50, adjust=False).mean().iloc[-1]
        
        # Price position relative to EMA
        if current['close'] > ema_50:
            bias = 'LONG'
        elif current['close'] < ema_50:
            bias = 'SHORT'
        else:
            bias = 'NEUTRAL'
        
        # Confirm with recent structure
        recent_high = df_h4['high'].tail(10).max()
        recent_low = df_h4['low'].tail(10).min()
        prev_high = df_h4['high'].iloc[-20:-10].max()
        prev_low = df_h4['low'].iloc[-20:-10].min()
        
        # Higher highs and higher lows = bullish
        if recent_high > prev_high and recent_low > prev_low:
            if bias == 'LONG':
                return 'LONG'
        
        # Lower highs and lower lows = bearish
        if recent_high < prev_high and recent_low < prev_low:
            if bias == 'SHORT':
                return 'SHORT'
        
        return bias
    
    def _calculate_trade_parameters(self,
                                   direction: str,
                                   current_price: float,
                                   sweep: LiquiditySweep,
                                   structure_shift: StructureShift,
                                   fvg: FairValueGap,
                                   df: pd.DataFrame,
                                   killzone: str) -> ICTTradeSignal:
        """Calculate entry, SL, and TP levels"""
        
        # Entry: OTE level within FVG (62-78.6%)
        ote_levels = self.fvg_detector.get_ote_levels(fvg)
        entry_price = ote_levels['ote_low']  # Conservative entry at 62%
        
        if direction == 'LONG':
            # Stop Loss: Below liquidity sweep low
            stop_loss = sweep.sweep_low - 5.0  # 5 pips buffer
            
            # Take Profits: Based on structure and opposing liquidity
            # TP1: 1:2 RR minimum
            risk = entry_price - stop_loss
            tp1_distance = risk * 2.0
            tp1 = entry_price + tp1_distance
            
            # TP2: 1:3 RR or next resistance
            tp2 = entry_price + (risk * 3.0)
            
            # TP3: 1:4 RR or major resistance
            tp3 = entry_price + (risk * 4.0)
            
        else:  # SHORT
            # Stop Loss: Above liquidity sweep high
            stop_loss = sweep.sweep_high + 5.0
            
            risk = stop_loss - entry_price
            tp1_distance = risk * 2.0
            tp1 = entry_price - tp1_distance
            
            tp2 = entry_price - (risk * 3.0)
            tp3 = entry_price - (risk * 4.0)
        
        # Calculate R:R
        rr_ratio = abs(tp1 - entry_price) / abs(stop_loss - entry_price)
        
        return ICTTradeSignal(
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=tp1,
            take_profit_2=tp2,
            take_profit_3=tp3,
            liquidity_sweep=sweep,
            structure_shift=structure_shift,
            entry_fvg=fvg,
            confluence_score=0.0,  # Calculated separately
            symbol=self.symbol,
            timeframe='M15',
            signal_time=df.iloc[-1]['time'],
            killzone=killzone,
            risk_reward_ratio=rr_ratio,
            position_size=0.0  # Calculated by position sizer
        )
    
    def _calculate_confluence_score(self,
                                    bias: str,
                                    sweep: LiquiditySweep,
                                    structure_shift: StructureShift,
                                    fvg: FairValueGap,
                                    timing: Dict) -> float:
        """
        Calculate ICT confluence score (0-100)
        
        Score Breakdown:
        - Daily Bias: 20 points
        - Killzone: 15 points
        - Liquidity Sweep: 25 points
        - MSS/BOS: 20 points
        - FVG: 15 points
        - Extra: 5 points (volume, structure strength)
        """
        score = 0.0
        
        # 1. Daily Bias (20 points)
        if bias in ['LONG', 'SHORT']:
            score += 20.0
        
        # 2. Killzone (15 points)
        if timing['is_silver_bullet']:
            score += 15.0  # Silver Bullet = full points
        elif timing['killzone_priority'] == 1:
            score += 12.0  # London or NY AM
        elif timing['killzone_priority'] == 2:
            score += 8.0   # NY PM
        
        # 3. Liquidity Sweep (25 points)
        if sweep.rejection_confirmed:
            score += 15.0
            # Bonus for rejection strength
            if sweep.rejection_strength >= 3.0:
                score += 5.0
            # Bonus for volume spike
            if sweep.volume_spike:
                score += 5.0
        
        # 4. MSS/BOS (20 points)
        if structure_shift.shift_type == 'MSS':
            score += 20.0  # Full points for MSS
        elif structure_shift.shift_type == 'BOS':
            score += 15.0  # Partial for BOS
        
        # 5. FVG (15 points)
        if fvg:
            score += 10.0
            # Bonus for strong FVG
            if fvg.strength >= 50:
                score += 5.0
        
        return min(score, 100.0)
    
    def get_signal_summary(self, signal: ICTTradeSignal) -> str:
        """Get human-readable signal summary"""
        summary = f"""
╔═══════════════════════════════════════════════════════════════╗
║           ICT 2022 TRADE SIGNAL - {signal.symbol}             ║
╚═══════════════════════════════════════════════════════════════╝

🎯 DIRECTION: {signal.direction}
⏰ KILLZONE: {signal.killzone}
📊 TIMEFRAME: {signal.timeframe}
🔢 CONFLUENCE: {signal.confluence_score:.1f}/100

═══════════════════════════════════════════════════════════════
💰 TRADE PARAMETERS
═══════════════════════════════════════════════════════════════
Entry:     ${signal.entry_price:.2f}
Stop Loss: ${signal.stop_loss:.2f}
TP1 (50%): ${signal.take_profit_1:.2f}
TP2 (30%): ${signal.take_profit_2:.2f}
TP3 (20%): ${signal.take_profit_3:.2f}

Risk:      ${abs(signal.entry_price - signal.stop_loss):.2f}
Reward:    ${abs(signal.take_profit_1 - signal.entry_price):.2f}
R:R Ratio: 1:{signal.risk_reward_ratio:.2f}

═══════════════════════════════════════════════════════════════
🔍 ICT COMPONENTS
═══════════════════════════════════════════════════════════════
"""
        
        if signal.liquidity_sweep:
            summary += f"✅ Liquidity Sweep: {signal.liquidity_sweep.sweep_type}\n"
            summary += f"   Rejection: {signal.liquidity_sweep.rejection_strength:.1f}x\n"
            summary += f"   Volume Spike: {'Yes' if signal.liquidity_sweep.volume_spike else 'No'}\n\n"
        
        if signal.structure_shift:
            summary += f"✅ Structure: {signal.structure_shift.shift_type} ({signal.structure_shift.direction})\n"
            summary += f"   Strength: {signal.structure_shift.strength:.1f}/100\n\n"
        
        if signal.entry_fvg:
            summary += f"✅ Entry FVG: {signal.entry_fvg.gap_type.upper()}\n"
            summary += f"   Size: {signal.entry_fvg.size_pips:.1f} pips\n"
            summary += f"   Strength: {signal.entry_fvg.strength:.1f}/100\n"
        
        summary += "\n═══════════════════════════════════════════════════════════════\n"
        
        return summary


class PowerOf3Strategy:
    """
    Power of 3 (AMD) Strategy
    Accumulation → Manipulation → Distribution
    
    Best for: Trending days after consolidation
    Win Rate: 60-70%
    """
    
    def __init__(self):
        self.asian_range_high = None
        self.asian_range_low = None
        self.manipulation_detected = False
        self.manipulation_direction = None
        
    def analyze_asian_session(self, df: pd.DataFrame) -> Dict:
        """
        Analyze Asian session to mark accumulation range
        
        Args:
            df: M15 or M5 data from Asian session (7PM-2AM EST)
            
        Returns:
            Dict with range info
        """
        if len(df) < 10:
            return {'range_valid': False}
        
        self.asian_range_high = df['high'].max()
        self.asian_range_low = df['low'].min()
        
        range_size = self.asian_range_high - self.asian_range_low
        
        return {
            'range_valid': True,
            'high': self.asian_range_high,
            'low': self.asian_range_low,
            'size': range_size
        }
    
    def detect_manipulation(self, df: pd.DataFrame) -> Optional[str]:
        """
        Detect manipulation phase (false breakout)
        
        Returns:
            'BULLISH' | 'BEARISH' | None
        """
        if self.asian_range_high is None:
            return None
        
        current = df.iloc[-1]
        
        # Bearish manipulation (sweep above high → rejection)
        if current['high'] > self.asian_range_high:
            if current['close'] < self.asian_range_high:
                # Confirmed rejection
                self.manipulation_detected = True
                self.manipulation_direction = 'BEARISH'
                return 'BEARISH'
        
        # Bullish manipulation (sweep below low → rejection)
        if current['low'] < self.asian_range_low:
            if current['close'] > self.asian_range_low:
                self.manipulation_detected = True
                self.manipulation_direction = 'BULLISH'
                return 'BULLISH'
        
        return None
    
    def get_distribution_signal(self, df: pd.DataFrame) -> Optional[str]:
        """
        Get distribution phase signal
        
        AMD Logic:
        - If manipulation swept LOWS (bullish trap) → Distribution goes DOWN (SHORT)
        - If manipulation swept HIGHS (bearish trap) → Distribution goes UP (LONG)
        
        Returns:
            'LONG' | 'SHORT' | None
        """
        if not self.manipulation_detected:
            return None
        
        current = df.iloc[-1]
        
        # After BEARISH manipulation (swept highs then rejected)
        # Smart money is now SELLING (distribution down)
        if self.manipulation_direction == 'BEARISH':
            # Confirm distribution has started (breaking below range)
            if current['close'] < self.asian_range_low:
                return 'SHORT'
        
        # After BULLISH manipulation (swept lows then rejected)
        # Smart money is now BUYING (distribution up)
        elif self.manipulation_direction == 'BULLISH':
            # Confirm distribution has started (breaking above range)
            if current['close'] > self.asian_range_high:
                return 'LONG'
        
        return None
