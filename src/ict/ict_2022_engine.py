"""
ICT 2022 ENGINE - Complete Implementation
Institutional trading concepts with precise GMT+3 killzone timing for Nairobi

Components:
- AMD Cycle Detection (Accumulation, Manipulation, Distribution)
- Killzone Session Filtering (London, NY, Silver Bullet)
- Liquidity Sweep Detection
- Market Structure Shift (MSS) and Break of Structure (BOS)
- Fair Value Gap (FVG) Trading
- Order Block Identification
- Optimal Trade Entry (OTE) 62-78.6%
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
from datetime import datetime, time as dt_time
from enum import Enum


class AMDPhase(Enum):
    """AMD Cycle Phases"""
    ACCUMULATION = "ACCUMULATION"
    MANIPULATION = "MANIPULATION"
    DISTRIBUTION = "DISTRIBUTION"
    UNKNOWN = "UNKNOWN"


class MarketStructure(Enum):
    """Market structure types"""
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    MSS_BULLISH = "MSS_BULLISH"  # Market Structure Shift to bullish
    MSS_BEARISH = "MSS_BEARISH"  # Market Structure Shift to bearish
    BOS_BULLISH = "BOS_BULLISH"  # Break of Structure bullish
    BOS_BEARISH = "BOS_BEARISH"  # Break of Structure bearish


@dataclass
class FairValueGap:
    """Fair Value Gap structure"""
    start_time: datetime
    start_price: float
    end_price: float
    direction: str  # 'bullish' or 'bearish'
    filled: bool = False
    ote_62: float = 0  # 62% Fibonacci level
    ote_79: float = 0  # 78.6% Fibonacci level


@dataclass
class OrderBlock:
    """Order Block structure"""
    time: datetime
    high: float
    low: float
    close: float
    direction: str  # 'bullish' or 'bearish'
    strength: float  # 0-100
    touched: bool = False


@dataclass
class LiquiditySweep:
    """Liquidity Sweep structure"""
    time: datetime
    level: float
    direction: str  # 'above' or 'below'
    pips_swept: float
    confirmed: bool = False


@dataclass
class ICTSignal:
    """Complete ICT trading signal"""
    timestamp: datetime
    symbol: str
    direction: str  # 'BUY' or 'SELL'
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float  # 0-100
    
    # ICT components
    amd_phase: AMDPhase
    in_killzone: bool
    killzone_name: Optional[str]
    liquidity_sweep: Optional[LiquiditySweep]
    fair_value_gap: Optional[FairValueGap]
    order_block: Optional[OrderBlock]
    market_structure: MarketStructure
    
    # Confluence factors
    confluence_score: int  # Number of ICT factors present
    reasons: List[str]


class ICT2022Engine:
    """
    Complete ICT 2022 Model Implementation
    Timezone: GMT+3 (Nairobi)
    """
    
    def __init__(self, broker_timezone: str = 'Africa/Nairobi'):
        """
        Initialize ICT 2022 Engine
        
        Args:
            broker_timezone: Broker timezone (default Africa/Nairobi for GMT+3 Nairobi)
        """
        self.broker_timezone = broker_timezone
        
        # Try to import pytz for proper timezone handling
        try:
            import pytz
            self.tz = pytz.timezone(broker_timezone)
        except (ImportError, KeyError):
            # Fallback: assume GMT+3 offset
            from datetime import timezone, timedelta
            self.tz = timezone(timedelta(hours=3))
        
        # Killzone times (GMT+3 for Nairobi)
        self.killzones = {
            'LONDON': {
                'start': dt_time(11, 0),  # 11 AM GMT+3 = 8 AM GMT
                'end': dt_time(13, 0),    # 1 PM GMT+3 = 10 AM GMT
                'priority': 1
            },
            'NEW_YORK': {
                'start': dt_time(14, 0),  # 2 PM GMT+3 = 11 AM GMT
                'end': dt_time(23, 0),    # 11 PM GMT+3 = 8 PM GMT
                'priority': 2
            },
            'SILVER_BULLET': {
                'start': dt_time(18, 0),  # 6 PM GMT+3 = 3 PM GMT
                'end': dt_time(19, 0),    # 7 PM GMT+3 = 4 PM GMT
                'priority': 3  # Highest priority
            }
        }
        
        # AMD cycle tracking
        self.current_amd_phase = AMDPhase.UNKNOWN
        
        # Liquidity levels tracking
        self.liquidity_levels = []
        
        # Fair Value Gaps tracking
        self.active_fvgs = []
        
        # Order Blocks tracking
        self.active_order_blocks = []
        
        # Market structure tracking
        self.swing_highs = []
        self.swing_lows = []
        self.current_structure = MarketStructure.BULLISH
        
    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[ICTSignal]:
        """
        Complete ICT analysis for trading signal
        
        Args:
            df: OHLCV dataframe (M15 timeframe recommended)
            symbol: Trading symbol
            
        Returns:
            ICTSignal if valid setup found, None otherwise
        """
        if len(df) < 100:
            return None
        
        # 1. Check if in killzone
        in_killzone, killzone_name = self._check_killzone()
        
        # 2. Detect AMD phase
        amd_phase = self._detect_amd_phase(df)
        
        # 3. Identify liquidity sweeps
        liquidity_sweep = self._detect_liquidity_sweep(df)
        
        # 4. Identify Fair Value Gaps
        fvg = self._identify_fair_value_gaps(df)
        
        # 5. Identify Order Blocks
        order_block = self._identify_order_blocks(df)
        
        # 6. Analyze Market Structure
        market_structure = self._analyze_market_structure(df)
        
        # 7. Generate signal if confluence exists
        signal = self._generate_signal(
            df=df,
            symbol=symbol,
            amd_phase=amd_phase,
            in_killzone=in_killzone,
            killzone_name=killzone_name,
            liquidity_sweep=liquidity_sweep,
            fvg=fvg,
            order_block=order_block,
            market_structure=market_structure
        )
        
        return signal
    
    def _check_killzone(self) -> Tuple[bool, Optional[str]]:
        """Check if current time is in a killzone"""
        # FIX: Use broker timezone instead of local time
        current_time = datetime.now(self.tz).time()
        
        # Check Silver Bullet first (highest priority)
        for kz_name in ['SILVER_BULLET', 'LONDON', 'NEW_YORK']:
            kz = self.killzones[kz_name]
            if kz['start'] <= current_time <= kz['end']:
                return True, kz_name
        
        return False, None
    
    def _detect_amd_phase(self, df: pd.DataFrame) -> AMDPhase:
        """
        Detect AMD cycle phase
        
        Logic:
        - Accumulation: Low volatility, tight range, consolidation
        - Manipulation: Liquidity sweep, false breakout
        - Distribution: High volatility move in trend direction
        """
        # Calculate volatility (ATR)
        atr = self._calculate_atr(df)
        avg_atr = atr.mean()
        current_atr = atr.iloc[-1]
        
        # Calculate range
        recent_high = df['high'].iloc[-20:].max()
        recent_low = df['low'].iloc[-20:].min()
        range_size = recent_high - recent_low
        avg_range = (df['high'].iloc[-100:-20] - df['low'].iloc[-100:-20]).mean()
        
        # Accumulation: Low volatility, tight range
        if current_atr < avg_atr * 0.7 and range_size < avg_range * 0.8:
            return AMDPhase.ACCUMULATION
        
        # Check for manipulation (liquidity sweep)
        liquidity_sweep = self._detect_liquidity_sweep(df)
        if liquidity_sweep and liquidity_sweep.confirmed:
            return AMDPhase.MANIPULATION
        
        # Distribution: High volatility expansion
        if current_atr > avg_atr * 1.3:
            return AMDPhase.DISTRIBUTION
        
        return AMDPhase.UNKNOWN
    
    def _detect_liquidity_sweep(self, df: pd.DataFrame) -> Optional[LiquiditySweep]:
        """
        Detect liquidity sweeps (stop hunts)
        
        Logic:
        - Price breaks recent high/low
        - Immediately reverses back
        - Typically happens before major moves
        """
        if len(df) < 50:
            return None
        
        # Get recent swing high/low
        swing_high = df['high'].iloc[-20:-1].max()
        swing_low = df['low'].iloc[-20:-1].min()
        
        current_high = df['high'].iloc[-1]
        current_low = df['low'].iloc[-1]
        current_close = df['close'].iloc[-1]
        
        # Check for upside liquidity sweep
        if current_high > swing_high:
            # Check if reversed back
            if current_close < swing_high:
                pips_swept = (current_high - swing_high) * 10000  # For forex
                return LiquiditySweep(
                    time=df.index[-1],
                    level=swing_high,
                    direction='above',
                    pips_swept=pips_swept,
                    confirmed=True
                )
        
        # Check for downside liquidity sweep
        if current_low < swing_low:
            # Check if reversed back
            if current_close > swing_low:
                pips_swept = (swing_low - current_low) * 10000
                return LiquiditySweep(
                    time=df.index[-1],
                    level=swing_low,
                    direction='below',
                    pips_swept=pips_swept,
                    confirmed=True
                )
        
        return None
    
    def _identify_fair_value_gaps(self, df: pd.DataFrame) -> Optional[FairValueGap]:
        """
        Identify Fair Value Gaps (FVG)
        
        Logic:
        - 3-candle pattern
        - Gap between candle 1 high and candle 3 low (bullish FVG)
        - Gap between candle 1 low and candle 3 high (bearish FVG)
        """
        if len(df) < 3:
            return None
        
        # Check last 3 candles
        candle1 = df.iloc[-3]
        candle2 = df.iloc[-2]
        candle3 = df.iloc[-1]
        
        # Bullish FVG: gap between candle1 high and candle3 low
        if candle3['low'] > candle1['high']:
            gap_size = candle3['low'] - candle1['high']
            
            # Calculate OTE levels (62% and 78.6%)
            ote_62 = candle1['high'] + (gap_size * 0.62)
            ote_79 = candle1['high'] + (gap_size * 0.786)
            
            return FairValueGap(
                start_time=candle1.name,
                start_price=candle1['high'],
                end_price=candle3['low'],
                direction='bullish',
                ote_62=ote_62,
                ote_79=ote_79
            )
        
        # Bearish FVG: gap between candle1 low and candle3 high
        if candle3['high'] < candle1['low']:
            gap_size = candle1['low'] - candle3['high']
            
            ote_62 = candle1['low'] - (gap_size * 0.62)
            ote_79 = candle1['low'] - (gap_size * 0.786)
            
            return FairValueGap(
                start_time=candle1.name,
                start_price=candle1['low'],
                end_price=candle3['high'],
                direction='bearish',
                ote_62=ote_62,
                ote_79=ote_79
            )
        
        return None
    
    def _identify_order_blocks(self, df: pd.DataFrame) -> Optional[OrderBlock]:
        """
        Identify Order Blocks
        
        Logic:
        - Last down candle before strong up move (bullish OB)
        - Last up candle before strong down move (bearish OB)
        """
        if len(df) < 10:
            return None
        
        # Look for bullish order block
        for i in range(len(df) - 5, len(df) - 1):
            candle = df.iloc[i]
            next_candles = df.iloc[i+1:i+4]
            
            # Bullish OB: down candle followed by strong up move
            if candle['close'] < candle['open']:  # Down candle
                if (next_candles['close'] > next_candles['open']).sum() >= 2:  # Followed by up moves
                    strength = ((next_candles['close'].iloc[-1] - candle['low']) / candle['low']) * 10000
                    
                    return OrderBlock(
                        time=candle.name,
                        high=candle['high'],
                        low=candle['low'],
                        close=candle['close'],
                        direction='bullish',
                        strength=min(100, strength * 10)
                    )
        
        # Look for bearish order block
        for i in range(len(df) - 5, len(df) - 1):
            candle = df.iloc[i]
            next_candles = df.iloc[i+1:i+4]
            
            # Bearish OB: up candle followed by strong down move
            if candle['close'] > candle['open']:  # Up candle
                if (next_candles['close'] < next_candles['open']).sum() >= 2:  # Followed by down moves
                    strength = ((candle['high'] - next_candles['close'].iloc[-1]) / candle['high']) * 10000
                    
                    return OrderBlock(
                        time=candle.name,
                        high=candle['high'],
                        low=candle['low'],
                        close=candle['close'],
                        direction='bearish',
                        strength=min(100, strength * 10)
                    )
        
        return None
    
    def _analyze_market_structure(self, df: pd.DataFrame) -> MarketStructure:
        """
        Analyze market structure for MSS and BOS
        
        Logic:
        - MSS: Break of previous structure (higher high in downtrend = MSS bullish)
        - BOS: Continuation of structure (higher high in uptrend = BOS bullish)
        """
        if len(df) < 50:
            return MarketStructure.BULLISH
        
        # Identify swing points
        swing_highs = self._find_swing_highs(df)
        swing_lows = self._find_swing_lows(df)
        
        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return MarketStructure.BULLISH
        
        # Check for higher highs and higher lows (bullish structure)
        recent_highs = swing_highs[-3:]
        recent_lows = swing_lows[-3:]
        
        higher_highs = all(recent_highs[i] < recent_highs[i+1] for i in range(len(recent_highs)-1))
        higher_lows = all(recent_lows[i] < recent_lows[i+1] for i in range(len(recent_lows)-1))
        
        if higher_highs and higher_lows:
            return MarketStructure.BOS_BULLISH
        
        # Check for lower highs and lower lows (bearish structure)
        lower_highs = all(recent_highs[i] > recent_highs[i+1] for i in range(len(recent_highs)-1))
        lower_lows = all(recent_lows[i] > recent_lows[i+1] for i in range(len(recent_lows)-1))
        
        if lower_highs and lower_lows:
            return MarketStructure.BOS_BEARISH
        
        # Check for MSS (structure shift)
        if higher_highs and not higher_lows:
            return MarketStructure.MSS_BULLISH
        
        if lower_lows and not lower_highs:
            return MarketStructure.MSS_BEARISH
        
        return MarketStructure.BULLISH
    
    def _generate_signal(self, df: pd.DataFrame, symbol: str,
                        amd_phase: AMDPhase, in_killzone: bool,
                        killzone_name: Optional[str],
                        liquidity_sweep: Optional[LiquiditySweep],
                        fvg: Optional[FairValueGap],
                        order_block: Optional[OrderBlock],
                        market_structure: MarketStructure) -> Optional[ICTSignal]:
        """Generate trading signal based on ICT confluence"""
        
        # Minimum requirements for signal
        confluence_count = 0
        reasons = []
        
        # 1. Must be in killzone (or very close to it)
        if not in_killzone:
            return None
        
        confluence_count += 1
        reasons.append(f"In {killzone_name} killzone")
        
        # 2. Check liquidity sweep
        if liquidity_sweep:
            confluence_count += 1
            reasons.append(f"Liquidity sweep {liquidity_sweep.direction} ({liquidity_sweep.pips_swept:.1f} pips)")
        
        # 3. Check FVG
        if fvg:
            confluence_count += 1
            reasons.append(f"{fvg.direction.title()} Fair Value Gap")
        
        # 4. Check Order Block
        if order_block:
            confluence_count += 1
            reasons.append(f"{order_block.direction.title()} Order Block (strength: {order_block.strength:.1f})")
        
        # 5. Check Market Structure
        if 'BULLISH' in market_structure.value:
            confluence_count += 1
            reasons.append(f"Market Structure: {market_structure.value}")
        elif 'BEARISH' in market_structure.value:
            confluence_count += 1
            reasons.append(f"Market Structure: {market_structure.value}")
        
        # 6. AMD phase
        if amd_phase in [AMDPhase.MANIPULATION, AMDPhase.DISTRIBUTION]:
            confluence_count += 1
            reasons.append(f"AMD Phase: {amd_phase.value}")
        
        # Require minimum 3 confluence factors
        if confluence_count < 3:
            return None
        
        # Determine direction
        bullish_factors = sum([
            fvg.direction == 'bullish' if fvg else False,
            order_block.direction == 'bullish' if order_block else False,
            'BULLISH' in market_structure.value,
            liquidity_sweep.direction == 'below' if liquidity_sweep else False
        ])
        
        bearish_factors = sum([
            fvg.direction == 'bearish' if fvg else False,
            order_block.direction == 'bearish' if order_block else False,
            'BEARISH' in market_structure.value,
            liquidity_sweep.direction == 'above' if liquidity_sweep else False
        ])
        
        if bullish_factors <= bearish_factors and bullish_factors < 2:
            return None  # No clear direction
        
        direction = 'BUY' if bullish_factors > bearish_factors else 'SELL'
        
        # Calculate entry, SL, TP
        current_price = df['close'].iloc[-1]
        atr = self._calculate_atr(df).iloc[-1]
        
        if direction == 'BUY':
            # Entry at current or OTE level if FVG exists
            entry_price = fvg.ote_62 if fvg and fvg.direction == 'bullish' else current_price
            stop_loss = entry_price - (atr * 1.5)
            take_profit = entry_price + (atr * 2.5)
        else:
            entry_price = fvg.ote_62 if fvg and fvg.direction == 'bearish' else current_price
            stop_loss = entry_price + (atr * 1.5)
            take_profit = entry_price - (atr * 2.5)
        
        # Calculate confidence
        confidence = min(100, (confluence_count / 6) * 100)
        
        # Boost confidence for Silver Bullet
        if killzone_name == 'SILVER_BULLET':
            confidence = min(100, confidence * 1.2)
        
        return ICTSignal(
            timestamp=datetime.now(),
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            amd_phase=amd_phase,
            in_killzone=in_killzone,
            killzone_name=killzone_name,
            liquidity_sweep=liquidity_sweep,
            fair_value_gap=fvg,
            order_block=order_block,
            market_structure=market_structure,
            confluence_score=confluence_count,
            reasons=reasons
        )
    
    # Helper methods
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return atr
    
    def _find_swing_highs(self, df: pd.DataFrame, window: int = 5) -> List[float]:
        """Find swing high points"""
        swing_highs = []
        
        for i in range(window, len(df) - window):
            if df['high'].iloc[i] == df['high'].iloc[i-window:i+window+1].max():
                swing_highs.append(df['high'].iloc[i])
        
        return swing_highs
    
    def _find_swing_lows(self, df: pd.DataFrame, window: int = 5) -> List[float]:
        """Find swing low points"""
        swing_lows = []
        
        for i in range(window, len(df) - window):
            if df['low'].iloc[i] == df['low'].iloc[i-window:i+window+1].min():
                swing_lows.append(df['low'].iloc[i])
        
        return swing_lows
    
    def print_signal(self, signal: ICTSignal):
        """Print ICT signal in readable format"""
        if not signal:
            return
        
        print("\n" + "="*80)
        print("ICT 2022 TRADING SIGNAL")
        print("="*80)
        print(f"Symbol: {signal.symbol}")
        print(f"Direction: {signal.direction}")
        print(f"Confidence: {signal.confidence:.1f}%")
        print(f"Confluence Score: {signal.confluence_score}/6")
        print(f"\nEntry: {signal.entry_price:.5f}")
        print(f"Stop Loss: {signal.stop_loss:.5f}")
        print(f"Take Profit: {signal.take_profit:.5f}")
        print(f"Risk/Reward: 1:{abs((signal.take_profit - signal.entry_price) / (signal.entry_price - signal.stop_loss)):.2f}")
        print(f"\nAMD Phase: {signal.amd_phase.value}")
        print(f"Killzone: {signal.killzone_name}")
        print(f"Market Structure: {signal.market_structure.value}")
        
        print(f"\nConfluence Factors:")
        for i, reason in enumerate(signal.reasons, 1):
            print(f"  {i}. {reason}")
        
        print("="*80 + "\n")
