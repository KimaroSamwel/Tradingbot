"""
SMART MONEY & INTERMARKET STRATEGIES
Implementation of institutional trading concepts and correlation strategies

Smart Money Concepts:
- Enhanced Order Blocks
- Breaker Blocks
- Wyckoff Method
- Volume Spread Analysis (VSA)
- Market Maker Model

Intermarket Strategies:
- Gold-USD Correlation
- Oil-CAD Correlation
- VIX-Forex Risk Correlation
- Bond Yield-Forex Correlation
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class SmartMoneySignal:
    strategy: str
    concept: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    institutional_level: float
    timeframe: str


@dataclass
class IntermarketSignal:
    strategy: str
    primary_asset: str
    correlated_asset: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    correlation_strength: float
    timeframe: str


class EnhancedOrderBlockStrategy:
    """Enhanced Order Block Detection"""
    
    @staticmethod
    def detect_order_block(df: pd.DataFrame, lookback: int = 20) -> Optional[SmartMoneySignal]:
        """
        Enhanced Order Block Detection
        Identifies where institutions placed large orders
        """
        if len(df) < lookback + 10:
            return None
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Bullish Order Block: Find last bearish candle before strong rally
        for i in range(2, lookback):
            candle = df.iloc[-i]
            next_candle = df.iloc[-i+1]
            
            # Bearish candle followed by strong bullish move
            if (candle['close'] < candle['open'] and
                next_candle['close'] > next_candle['open'] and
                (next_candle['close'] - next_candle['open']) > (candle['open'] - candle['close']) * 2):
                
                order_block_high = candle['high']
                order_block_low = candle['low']
                
                # Check if price is testing order block
                if order_block_low <= current_price <= order_block_high:
                    return SmartMoneySignal(
                        strategy='order_block',
                        concept='BULLISH_ORDER_BLOCK',
                        direction='LONG',
                        entry_price=current_price,
                        stop_loss=order_block_low - (atr * 0.3),
                        take_profit=current_price + (atr * 3.0),
                        confidence=85.0,
                        institutional_level=order_block_low,
                        timeframe='H1'
                    )
        
        return None


class BreakerBlockStrategy:
    """Breaker Block Strategy"""
    
    @staticmethod
    def detect_breaker(df: pd.DataFrame) -> Optional[SmartMoneySignal]:
        """
        Breaker Block: Failed order block that flips polarity
        Old support becomes resistance and vice versa
        """
        if len(df) < 30:
            return None
        
        current_price = df['close'].iloc[-1]
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # Find recent support/resistance that was broken
        recent_low = df['low'].iloc[-20:-5].min()
        recent_high = df['high'].iloc[-20:-5].max()
        
        # Check if price broke support and is retesting from below
        if current_price < recent_low and df['high'].iloc[-1] >= recent_low * 0.999:
            return SmartMoneySignal(
                strategy='breaker_block',
                concept='FAILED_SUPPORT_BREAKER',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=recent_low + (atr * 0.5),
                take_profit=current_price - (atr * 3.0),
                confidence=80.0,
                institutional_level=recent_low,
                timeframe='H4'
            )
        
        # Check if price broke resistance and is retesting from above
        elif current_price > recent_high and df['low'].iloc[-1] <= recent_high * 1.001:
            return SmartMoneySignal(
                strategy='breaker_block',
                concept='FAILED_RESISTANCE_BREAKER',
                direction='LONG',
                entry_price=current_price,
                stop_loss=recent_high - (atr * 0.5),
                take_profit=current_price + (atr * 3.0),
                confidence=80.0,
                institutional_level=recent_high,
                timeframe='H4'
            )
        
        return None


class WyckoffStrategy:
    """Wyckoff Method - Accumulation/Distribution"""
    
    @staticmethod
    def detect_accumulation(df: pd.DataFrame) -> Optional[SmartMoneySignal]:
        """
        Wyckoff Accumulation Pattern
        Phases: PS, SC, Test, SOS, LPS
        """
        if len(df) < 50:
            return None
        
        # Simplified Wyckoff detection
        # Full implementation requires detailed phase analysis
        
        recent_range = df['high'].iloc[-30:] - df['low'].iloc[-30:]
        avg_range = recent_range.mean()
        
        # Check for narrow range (accumulation)
        if recent_range.iloc[-5:].mean() < avg_range * 0.7:
            current_price = df['close'].iloc[-1]
            range_low = df['low'].iloc[-30:].min()
            range_high = df['high'].iloc[-30:].max()
            
            # Spring (test of support)
            if current_price <= range_low * 1.01:
                atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
                
                return SmartMoneySignal(
                    strategy='wyckoff',
                    concept='ACCUMULATION_SPRING',
                    direction='LONG',
                    entry_price=current_price,
                    stop_loss=range_low - (atr * 0.5),
                    take_profit=range_high + (range_high - range_low),
                    confidence=75.0,
                    institutional_level=range_low,
                    timeframe='D1'
                )
        
        return None


class VSAStrategy:
    """Volume Spread Analysis"""
    
    @staticmethod
    def analyze(df: pd.DataFrame) -> Optional[SmartMoneySignal]:
        """
        VSA: Analyze relationship between volume and price spread
        """
        if 'volume' not in df.columns or len(df) < 20:
            return None
        
        current = df.iloc[-1]
        spread = current['high'] - current['low']
        volume = current['volume']
        
        avg_spread = (df['high'].iloc[-20:] - df['low'].iloc[-20:]).mean()
        avg_volume = df['volume'].iloc[-20:].mean()
        
        current_price = current['close']
        atr = (df['high'] - df['low']).rolling(14).mean().iloc[-1]
        
        # High volume, narrow spread = absorption (potential reversal)
        if volume > avg_volume * 1.5 and spread < avg_spread * 0.7:
            # Check if at support
            if current_price <= df['low'].iloc[-20:].min() * 1.02:
                return SmartMoneySignal(
                    strategy='vsa',
                    concept='ABSORPTION_AT_SUPPORT',
                    direction='LONG',
                    entry_price=current_price,
                    stop_loss=current['low'] - (atr * 0.3),
                    take_profit=current_price + (atr * 2.5),
                    confidence=75.0,
                    institutional_level=current['low'],
                    timeframe='H1'
                )
        
        # Low volume, wide spread = no demand (weakness)
        elif volume < avg_volume * 0.5 and spread > avg_spread * 1.3:
            if current['close'] < current['open']:  # Bearish candle
                return SmartMoneySignal(
                    strategy='vsa',
                    concept='NO_DEMAND',
                    direction='SHORT',
                    entry_price=current_price,
                    stop_loss=current['high'] + (atr * 0.3),
                    take_profit=current_price - (atr * 2.5),
                    confidence=70.0,
                    institutional_level=current['high'],
                    timeframe='H1'
                )
        
        return None


class GoldUSDCorrelationStrategy:
    """Gold vs USD Correlation Trading"""
    
    @staticmethod
    def analyze(df_gold: pd.DataFrame, df_dxy: pd.DataFrame) -> Optional[IntermarketSignal]:
        """
        Gold-USD Inverse Correlation
        DXY up → Gold down, DXY down → Gold up
        """
        if len(df_gold) < 20 or len(df_dxy) < 20:
            return None
        
        # Calculate recent moves
        gold_change = (df_gold['close'].iloc[-1] - df_gold['close'].iloc[-10]) / df_gold['close'].iloc[-10]
        dxy_change = (df_dxy['close'].iloc[-1] - df_dxy['close'].iloc[-10]) / df_dxy['close'].iloc[-10]
        
        # Expected: negative correlation
        expected_correlation = -0.85
        
        current_gold = df_gold['close'].iloc[-1]
        atr_gold = (df_gold['high'] - df_gold['low']).rolling(14).mean().iloc[-1]
        
        # Divergence: DXY down but gold not up yet
        if dxy_change < -0.01 and gold_change < 0.005:
            return IntermarketSignal(
                strategy='gold_usd_correlation',
                primary_asset='XAUUSD',
                correlated_asset='DXY',
                direction='LONG',
                entry_price=current_gold,
                stop_loss=current_gold - (atr_gold * 2.0),
                take_profit=current_gold + (atr_gold * 3.0),
                confidence=75.0,
                correlation_strength=expected_correlation,
                timeframe='H4'
            )
        
        # Divergence: DXY up but gold not down yet
        elif dxy_change > 0.01 and gold_change > -0.005:
            return IntermarketSignal(
                strategy='gold_usd_correlation',
                primary_asset='XAUUSD',
                correlated_asset='DXY',
                direction='SHORT',
                entry_price=current_gold,
                stop_loss=current_gold + (atr_gold * 2.0),
                take_profit=current_gold - (atr_gold * 3.0),
                confidence=75.0,
                correlation_strength=expected_correlation,
                timeframe='H4'
            )
        
        return None


class OilCADCorrelationStrategy:
    """Crude Oil vs CAD Correlation"""
    
    @staticmethod
    def analyze(df_usdcad: pd.DataFrame, df_oil: pd.DataFrame) -> Optional[IntermarketSignal]:
        """
        Oil-CAD Correlation
        Oil up → CAD strengthens → USDCAD down
        """
        if len(df_usdcad) < 20 or len(df_oil) < 20:
            return None
        
        # Calculate moves
        usdcad_change = (df_usdcad['close'].iloc[-1] - df_usdcad['close'].iloc[-10]) / df_usdcad['close'].iloc[-10]
        oil_change = (df_oil['close'].iloc[-1] - df_oil['close'].iloc[-10]) / df_oil['close'].iloc[-10]
        
        current_usdcad = df_usdcad['close'].iloc[-1]
        atr = (df_usdcad['high'] - df_usdcad['low']).rolling(14).mean().iloc[-1]
        
        # Oil up, USDCAD hasn't adjusted down yet
        if oil_change > 0.02 and usdcad_change > 0:
            return IntermarketSignal(
                strategy='oil_cad_correlation',
                primary_asset='USDCAD',
                correlated_asset='CRUDE_OIL',
                direction='SHORT',
                entry_price=current_usdcad,
                stop_loss=current_usdcad + (atr * 2.0),
                take_profit=current_usdcad - (atr * 3.0),
                confidence=70.0,
                correlation_strength=0.75,
                timeframe='H4'
            )
        
        # Oil down, USDCAD hasn't adjusted up yet
        elif oil_change < -0.02 and usdcad_change < 0:
            return IntermarketSignal(
                strategy='oil_cad_correlation',
                primary_asset='USDCAD',
                correlated_asset='CRUDE_OIL',
                direction='LONG',
                entry_price=current_usdcad,
                stop_loss=current_usdcad - (atr * 2.0),
                take_profit=current_usdcad + (atr * 3.0),
                confidence=70.0,
                correlation_strength=0.75,
                timeframe='H4'
            )
        
        return None


class RiskSentimentStrategy:
    """Risk On/Risk Off Trading"""
    
    @staticmethod
    def analyze(df_pair: pd.DataFrame, vix_level: float) -> Optional[IntermarketSignal]:
        """
        Risk Sentiment Analysis
        High VIX → Risk Off → USD, JPY, CHF strengthen
        Low VIX → Risk On → AUD, NZD, commodity currencies strengthen
        """
        if len(df_pair) < 20:
            return None
        
        current_price = df_pair['close'].iloc[-1]
        atr = (df_pair['high'] - df_pair['low']).rolling(14).mean().iloc[-1]
        
        # VIX spike (risk off)
        if vix_level > 25:
            # If trading risk currency like AUDUSD, go short
            return IntermarketSignal(
                strategy='risk_sentiment',
                primary_asset='AUDUSD',
                correlated_asset='VIX',
                direction='SHORT',
                entry_price=current_price,
                stop_loss=current_price + (atr * 2.0),
                take_profit=current_price - (atr * 3.0),
                confidence=70.0,
                correlation_strength=-0.70,
                timeframe='H4'
            )
        
        # VIX low (risk on)
        elif vix_level < 15:
            return IntermarketSignal(
                strategy='risk_sentiment',
                primary_asset='AUDUSD',
                correlated_asset='VIX',
                direction='LONG',
                entry_price=current_price,
                stop_loss=current_price - (atr * 2.0),
                take_profit=current_price + (atr * 3.0),
                confidence=70.0,
                correlation_strength=-0.70,
                timeframe='H4'
            )
        
        return None


# Master Smart Money & Intermarket Selector
class SmartMoneyIntermarketSelector:
    """Master selector for smart money and intermarket strategies"""
    
    def __init__(self):
        self.order_block = EnhancedOrderBlockStrategy()
        self.breaker = BreakerBlockStrategy()
        self.wyckoff = WyckoffStrategy()
        self.vsa = VSAStrategy()
        self.gold_usd = GoldUSDCorrelationStrategy()
        self.oil_cad = OilCADCorrelationStrategy()
        self.risk_sentiment = RiskSentimentStrategy()
    
    def get_smart_money_signals(self, df: pd.DataFrame) -> List[SmartMoneySignal]:
        """Get all smart money signals"""
        signals = []
        
        signals.append(self.order_block.detect_order_block(df))
        signals.append(self.breaker.detect_breaker(df))
        signals.append(self.wyckoff.detect_accumulation(df))
        signals.append(self.vsa.analyze(df))
        
        return [s for s in signals if s is not None]
    
    def get_intermarket_signals(self, pair_data: Dict[str, pd.DataFrame],
                               vix_level: float = None) -> List[IntermarketSignal]:
        """Get all intermarket signals"""
        signals = []
        
        # Gold-USD correlation
        if 'XAUUSD' in pair_data and 'DXY' in pair_data:
            signals.append(self.gold_usd.analyze(pair_data['XAUUSD'], pair_data['DXY']))
        
        # Oil-CAD correlation
        if 'USDCAD' in pair_data and 'CRUDE_OIL' in pair_data:
            signals.append(self.oil_cad.analyze(pair_data['USDCAD'], pair_data['CRUDE_OIL']))
        
        # Risk sentiment
        if vix_level and 'AUDUSD' in pair_data:
            signals.append(self.risk_sentiment.analyze(pair_data['AUDUSD'], vix_level))
        
        return [s for s in signals if s is not None]
    
    def get_best_smart_money(self, df: pd.DataFrame) -> Optional[SmartMoneySignal]:
        """Get highest confidence smart money signal"""
        signals = self.get_smart_money_signals(df)
        return max(signals, key=lambda x: x.confidence) if signals else None
    
    def get_best_intermarket(self, pair_data: Dict[str, pd.DataFrame],
                            vix_level: float = None) -> Optional[IntermarketSignal]:
        """Get highest confidence intermarket signal"""
        signals = self.get_intermarket_signals(pair_data, vix_level)
        return max(signals, key=lambda x: x.confidence) if signals else None
