"""
DYNAMIC STRATEGY ORCHESTRATOR - 4-Bot Architecture
Implements the "Strategy Orchestra" concept with specialized bots

Bots:
1. SNIPER SCOUT - Analysis & pattern detection
2. PRECISION CONFIRMER - Multi-timeframe validation
3. EXECUTION SNIPER - Order execution
4. GUARDIAN - Risk monitoring & circuit breaker
"""

import pandas as pd
import numpy as np
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from src.strategies.strategy_conflict_manager import (
    StrategyConflictManager, MarketRegime
)
from src.strategies.master_strategy_manager import MasterStrategyManager
from src.analysis.advanced_regime_detector import AdvancedMarketRegimeDetector
from src.ict.ict_2022_engine import ICT2022Engine, ICTSignal
from src.execution.kelly_position_sizer import KellyPositionSizer
from src.risk.trading_circuit_breaker import TradingCircuitBreaker


class BotStatus(Enum):
    """Bot operational status"""
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    ERROR = "ERROR"
    STANDBY = "STANDBY"


@dataclass
class WatchlistItem:
    """Symbol on watchlist with setup details"""
    symbol: str
    pattern: str
    confidence: float
    timeframe: str
    discovered_at: datetime
    expires_at: datetime
    asset_class: str = 'OTHER'


@dataclass
class ValidationResult:
    """Multi-timeframe validation result"""
    symbol: str
    valid: bool
    m15_signal: Optional[Dict]
    h1_signal: Optional[Dict]
    h4_signal: Optional[Dict]
    agreement_score: float  # 0-100
    reasons: List[str]


@dataclass
class ExecutionOrder:
    """Order ready for execution"""
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    lot_size: float
    risk_percent: float
    strategy: str
    confidence: float
    validation_score: float


class SniperScout:
    """
    BOT 1: SNIPER SCOUT
    Continuously scans markets for setups
    """
    
    def __init__(self, symbols: List[str], config: Dict = None):
        self.symbols = symbols
        self.config = config or {}
        self.status = BotStatus.ACTIVE
        self.watchlist: List[WatchlistItem] = []
        self.ict_engine = ICT2022Engine()
        # CRITICAL: MasterStrategyManager with ALL 117 strategies
        self.strategy_manager = MasterStrategyManager(self.config)

    def _classify_asset_class(self, symbol: str) -> str:
        """Map symbol to broad asset class for watchlist diversity."""
        symbol_upper = str(symbol or '').upper()
        if any(token in symbol_upper for token in ('CRASH', 'BOOM', 'VOLATILITY', 'STEP INDEX')):
            return 'SYNTHETICS'
        if symbol_upper.startswith('XAU') or symbol_upper.startswith('XAG'):
            return 'METALS'
        if len(symbol_upper) == 6 and symbol_upper.isalpha():
            return 'FOREX'
        return 'OTHER'

    def _normalize_signal_confidence(self, signal) -> float:
        """
        Normalize confidence to 0-100 and apply optional category scaling.
        Helps cross-strategy comparability when aggregating candidates.
        """
        raw_conf = float(getattr(signal, 'confidence', 0.0) or 0.0)
        raw_conf = max(0.0, min(raw_conf, 100.0))

        category = str(getattr(signal, 'strategy_category', '') or '').lower()
        scale_cfg = self.config.get('confidence_scale', {})
        scale = float(scale_cfg.get(category, 1.0) or 1.0)
        return max(0.0, min(raw_conf * scale, 100.0))

    def _build_related_data(self, symbol: str, market_data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
        """
        Build cross-symbol related_data map for intermarket-aware strategies.

        Structure:
        {
            '<related_symbol>': DataFrame,
            ...
            '_meta': {
                'symbol': str,
                'related_symbols': [...],
                'correlation_data': {...}
            }
        }
        """
        base_symbol_data = {
            key: value for key, value in market_data.items()
            if not (
                key.endswith('_M15')
                or key.endswith('_H1')
                or key.endswith('_H4')
            )
        }

        if symbol not in base_symbol_data:
            return {}

        symbol_df = base_symbol_data[symbol]
        if symbol_df is None or len(symbol_df) < 20:
            return {}

        pair_re = r'^[A-Z]{6}$'
        symbol_upper = str(symbol or '').upper()
        is_forex_symbol = bool(re.match(pair_re, symbol_upper))
        symbol_ccys = {symbol_upper[:3], symbol_upper[3:]} if is_forex_symbol else set()

        correlation_data: Dict[str, float] = {}
        candidate_frames: Dict[str, pd.DataFrame] = {}

        sym_close = symbol_df['close'].pct_change().dropna()
        for other_symbol, other_df in base_symbol_data.items():
            if other_symbol == symbol or other_df is None or len(other_df) < 20:
                continue

            other_upper = str(other_symbol or '').upper()
            include = False

            if is_forex_symbol:
                if bool(re.match(pair_re, other_upper)):
                    other_ccys = {other_upper[:3], other_upper[3:]}
                    include = len(symbol_ccys.intersection(other_ccys)) > 0
                elif other_upper in ('DXY', 'USDX'):
                    include = True
            else:
                include = True

            if not include:
                continue

            candidate_frames[other_symbol] = other_df
            other_close = other_df['close'].pct_change().dropna()
            common_idx = sym_close.index.intersection(other_close.index)
            if len(common_idx) >= 20:
                corr = float(sym_close.loc[common_idx].tail(120).corr(other_close.loc[common_idx].tail(120)))
                if np.isfinite(corr):
                    correlation_data[other_symbol] = corr

        # Prioritize strongly related symbols.
        ranked_related = sorted(
            candidate_frames.keys(),
            key=lambda s: abs(correlation_data.get(s, 0.0)),
            reverse=True,
        )
        max_related = int(self.config.get('max_related_symbols', 10) or 10)
        selected_related = ranked_related[:max_related]

        related_data: Dict[str, Any] = {
            s: candidate_frames[s] for s in selected_related
        }
        related_data['_meta'] = {
            'symbol': symbol,
            'related_symbols': selected_related,
            'correlation_data': {s: correlation_data.get(s, 0.0) for s in selected_related},
        }
        return related_data
        
    def scan_markets(self, market_data: Dict[str, pd.DataFrame]) -> List[WatchlistItem]:
        """
        Scan all symbols for potential setups using ALL 117 strategies
        
        Args:
            market_data: Dictionary of symbol -> dataframe
            
        Returns:
            List of watchlist items
        """
        new_watchlist = []
        
        for symbol in self.symbols:
            if symbol not in market_data:
                continue
            
            df = market_data[symbol]
            
            # PRIORITY 1: ICT analysis (Primary strategy)
            ict_signal = self.ict_engine.analyze(df, symbol)
            if ict_signal and ict_signal.confidence > 60:
                new_watchlist.append(WatchlistItem(
                    symbol=symbol,
                    pattern=f"ICT_{ict_signal.market_structure.value}",
                    confidence=ict_signal.confidence,
                    timeframe='M15',
                    discovered_at=datetime.now(),
                    expires_at=datetime.now() + pd.Timedelta(hours=2),
                    asset_class=self._classify_asset_class(symbol),
                ))
            
            # PRIORITY 2: ALL 117 STRATEGIES via MasterStrategyManager
            try:
                related_data = self._build_related_data(symbol, market_data)

                all_signals = self.strategy_manager.analyze_all_strategies(
                    symbol=symbol,
                    df=df,
                    df_h4=market_data.get(f"{symbol}_H4"),
                    df_h1=market_data.get(f"{symbol}_H1"),
                    related_data=related_data,
                    current_time=datetime.now()
                )

                # Keep strongest normalized-confidence strategies first.
                all_signals.sort(key=self._normalize_signal_confidence, reverse=True)
                
                # Add top signals from all strategies
                for signal in all_signals[:10]:  # Top 10 from 117 strategies
                    normalized_conf = self._normalize_signal_confidence(signal)
                    if normalized_conf > 65:
                        new_watchlist.append(WatchlistItem(
                            symbol=symbol,
                            pattern=f"{signal.strategy_category}_{signal.strategy_name}",
                            confidence=normalized_conf,
                            timeframe=signal.timeframe,
                            discovered_at=datetime.now(),
                            expires_at=datetime.now() + pd.Timedelta(hours=1),
                            asset_class=self._classify_asset_class(symbol),
                        ))
            except Exception as e:
                print(f"Strategy scan error for {symbol}: {e}")
            
            # PRIORITY 3: Pattern detection (supply/demand, S/R, etc.)
            patterns = self._detect_patterns(df)
            for pattern in patterns:
                new_watchlist.append(WatchlistItem(
                    symbol=symbol,
                    pattern=pattern['name'],
                    confidence=pattern['confidence'],
                    timeframe='M15',
                    discovered_at=datetime.now(),
                    expires_at=datetime.now() + pd.Timedelta(hours=1),
                    asset_class=self._classify_asset_class(symbol),
                ))
        
        # Update watchlist
        self.watchlist = self._update_watchlist(new_watchlist)
        
        return self.watchlist
    
    def _detect_patterns(self, df: pd.DataFrame) -> List[Dict]:
        """Detect chart patterns and setups"""
        patterns = []
        
        # Support/Resistance
        sr_levels = self._find_support_resistance(df)
        if sr_levels:
            patterns.append({
                'name': 'Support_Resistance',
                'confidence': 70,
                'details': sr_levels
            })
        
        # Double top/bottom
        double_pattern = self._detect_double_pattern(df)
        if double_pattern:
            patterns.append(double_pattern)
        
        # Fibonacci retracement
        fib_setup = self._detect_fibonacci_setup(df)
        if fib_setup:
            patterns.append(fib_setup)
        
        return patterns
    
    def _find_support_resistance(self, df: pd.DataFrame, window: int = 20) -> Optional[Dict]:
        """Find key support/resistance levels"""
        if len(df) < window * 2:
            return None

        highs = df['high'].rolling(window=window).max()
        lows = df['low'].rolling(window=window).min()

        current_price = df['close'].iloc[-1]

        # Find nearest levels
        resistance_candidates = highs[highs > current_price].dropna()
        support_candidates = lows[lows < current_price].dropna()
        resistance = resistance_candidates.iloc[-5:].values if len(resistance_candidates) > 0 else []
        support = support_candidates.iloc[-5:].values if len(support_candidates) > 0 else []

        if len(resistance) > 0 or len(support) > 0:
            return {
                'resistance': [float(x) for x in resistance],
                'support': [float(x) for x in support],
                'current_price': current_price
            }

        return None
    
    def _detect_double_pattern(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect double top/bottom patterns"""
        # Simplified implementation
        if len(df) < 50:
            return None
        
        highs = df['high'].iloc[-50:]
        max_high = highs.max()
        
        # Find two peaks at similar levels
        peaks = []
        for i in range(5, len(highs) - 5):
            if highs.iloc[i] == highs.iloc[i-5:i+5].max():
                peaks.append(highs.iloc[i])
        
        if len(peaks) >= 2:
            if abs(peaks[-1] - peaks[-2]) / peaks[-1] < 0.002:  # Within 0.2%
                return {
                    'name': 'Double_Top',
                    'confidence': 75,
                    'level': peaks[-1]
                }
        
        return None
    
    def _detect_fibonacci_setup(self, df: pd.DataFrame) -> Optional[Dict]:
        """Detect Fibonacci retracement setups"""
        if len(df) < 30:
            return None
        
        # Find swing high and low
        swing_high = df['high'].iloc[-30:].max()
        swing_low = df['low'].iloc[-30:].min()
        
        # Calculate Fibonacci levels
        diff = swing_high - swing_low
        fib_382 = swing_high - (diff * 0.382)
        fib_500 = swing_high - (diff * 0.500)
        fib_618 = swing_high - (diff * 0.618)
        
        current_price = df['close'].iloc[-1]
        
        # Check if price is near a Fibonacci level
        tolerance = diff * 0.02  # 2% tolerance
        
        for level, name in [(fib_382, '38.2%'), (fib_500, '50%'), (fib_618, '61.8%')]:
            if abs(current_price - level) < tolerance:
                return {
                    'name': f'Fibonacci_{name}',
                    'confidence': 65,
                    'level': level
                }
        
        return None
    
    def _update_watchlist(self, new_items: List[WatchlistItem]) -> List[WatchlistItem]:
        """Update watchlist, removing expired items"""
        now = datetime.now()
        
        # Remove expired items
        active_items = [item for item in self.watchlist if item.expires_at > now]
        
        # Add new items (avoid duplicates)
        for item in new_items:
            if not any(i.symbol == item.symbol and i.pattern == item.pattern for i in active_items):
                active_items.append(item)
        
        # Sort by confidence
        active_items.sort(key=lambda x: x.confidence, reverse=True)
        
        return active_items[:20]  # Keep top 20


class PrecisionConfirmer:
    """
    BOT 2: PRECISION CONFIRMER
    Multi-timeframe validation & confluence checking
    """
    
    def __init__(self):
        self.status = BotStatus.ACTIVE
        self.regime_detector = AdvancedMarketRegimeDetector()
        self.conflict_manager = StrategyConflictManager()
        
    def validate_setup(self, symbol: str,
                      df_m15: pd.DataFrame,
                      df_h1: Optional[pd.DataFrame] = None,
                      df_h4: Optional[pd.DataFrame] = None,
                      min_agreement: int = 2) -> ValidationResult:
        """
        Validate setup across multiple timeframes
        
        Args:
            symbol: Trading symbol
            df_m15: M15 data
            df_h1: H1 data (optional)
            df_h4: H4 data (optional)
            min_agreement: Minimum timeframes that must agree
            
        Returns:
            ValidationResult with confluence analysis
        """
        signals = {}
        reasons = []
        
        # M15 analysis
        m15_signal = self._analyze_timeframe(df_m15, 'M15')
        signals['m15'] = m15_signal
        
        # H1 analysis
        h1_signal = None
        if df_h1 is not None and len(df_h1) > 50:
            h1_signal = self._analyze_timeframe(df_h1, 'H1')
            signals['h1'] = h1_signal
        
        # H4 analysis
        h4_signal = None
        if df_h4 is not None and len(df_h4) > 50:
            h4_signal = self._analyze_timeframe(df_h4, 'H4')
            signals['h4'] = h4_signal
        
        # Calculate agreement
        agreement_score, reasons = self._calculate_agreement(signals)
        
        # Check if minimum agreement met
        valid = agreement_score >= (min_agreement / 3.0 * 100)
        
        return ValidationResult(
            symbol=symbol,
            valid=valid,
            m15_signal=m15_signal,
            h1_signal=h1_signal,
            h4_signal=h4_signal,
            agreement_score=agreement_score,
            reasons=reasons
        )
    
    def _analyze_timeframe(self, df: pd.DataFrame, timeframe: str) -> Dict:
        """Analyze single timeframe using enriched indicators when available.
        
        Uses full indicator suite (EMA alignment, HMA, MACD, RSI, QQE, Squeeze,
        Institutional Money Flow) if AdvancedIndicators columns are present.
        Falls back to basic EMA20/50 + RSI if enriched columns are absent.
        """
        if len(df) < 20:
            return {
                'timeframe': timeframe,
                'direction': 'NEUTRAL',
                'confidence': 0,
                'ema20': 0.0,
                'ema50': 0.0,
                'rsi': 50.0,
                'entry_price': 0.0,
                'stop_loss': 0.0,
                'take_profit': 0.0,
                'atr': 0.0,
                'current_price': 0.0
            }
        
        last = df.iloc[-1]
        current_price = float(last['close'])
        has_enriched = 'ema_bullish_align' in df.columns
        
        # --- Enriched analysis (full indicator suite computed) ---
        if has_enriched:
            bullish_votes = 0
            bearish_votes = 0
            total_factors = 0
            
            # EMA alignment (Trend)
            ema_bull = float(last.get('ema_bullish_align', 0)) > 0.66
            ema_bear = float(last.get('ema_bearish_align', 0)) > 0.66
            if ema_bull: bullish_votes += 2
            elif ema_bear: bearish_votes += 2
            total_factors += 2
            
            # HMA trend (Trend)
            hma_trend = int(last.get('hma_trend', 0))
            if hma_trend == 1: bullish_votes += 1
            elif hma_trend == -1: bearish_votes += 1
            total_factors += 1
            
            # MACD histogram (Momentum)
            macd_hist = float(last.get('macd_hist', 0))
            if macd_hist > 0: bullish_votes += 1
            elif macd_hist < 0: bearish_votes += 1
            total_factors += 1
            
            # RSI zone (Momentum)
            rsi = float(last.get('rsi', 50))
            if 40 < rsi < 70: bullish_votes += 1
            elif 30 < rsi < 60: bearish_votes += 1
            total_factors += 1
            
            # QQE MOD trend (Momentum)
            qqe_trend = int(last.get('qqe_trend', 0))
            if qqe_trend == 1: bullish_votes += 1
            elif qqe_trend == -1: bearish_votes += 1
            total_factors += 1
            
            # Institutional Money Flow (Volume)
            if bool(last.get('imf_bullish', False)): bullish_votes += 1
            elif bool(last.get('imf_bearish', False)): bearish_votes += 1
            total_factors += 1
            
            # Determine direction from multi-indicator consensus
            if bullish_votes > bearish_votes and bullish_votes >= 3:
                direction = 'BUY'
                confidence = min(95, 50 + (bullish_votes / max(total_factors, 1)) * 50)
            elif bearish_votes > bullish_votes and bearish_votes >= 3:
                direction = 'SELL'
                confidence = min(95, 50 + (bearish_votes / max(total_factors, 1)) * 50)
            else:
                direction = 'NEUTRAL'
                confidence = 30
            
            ema20_val = float(last.get('ema_21', last.get('close', 0)))
            ema50_val = float(last.get('ema_50', last.get('close', 0)))
        else:
            # --- Fallback: basic EMA20/50 + RSI ---
            ema20 = df['close'].ewm(span=20).mean()
            ema50 = df['close'].ewm(span=50).mean() if len(df) >= 50 else ema20
            ema20_val = float(ema20.iloc[-1])
            ema50_val = float(ema50.iloc[-1])
            
            if current_price > ema20_val > ema50_val:
                direction = 'BUY'
                confidence = 70
            elif current_price < ema20_val < ema50_val:
                direction = 'SELL'
                confidence = 70
            else:
                direction = 'NEUTRAL'
                confidence = 40
            
            rsi = self._calculate_rsi(df)
            if rsi > 70 and direction == 'SELL':
                confidence += 10
            elif rsi < 30 and direction == 'BUY':
                confidence += 10
        
        atr = self._calculate_atr(df)
        entry_price = float(current_price)
        if direction == 'BUY':
            stop_loss = entry_price - (atr * 1.5)
            take_profit = entry_price + (atr * 2.5)
        elif direction == 'SELL':
            stop_loss = entry_price + (atr * 1.5)
            take_profit = entry_price - (atr * 2.5)
        else:
            stop_loss = 0.0
            take_profit = 0.0

        return {
            'timeframe': timeframe,
            'direction': direction,
            'confidence': min(100, confidence),
            'ema20': ema20_val,
            'ema50': ema50_val,
            'rsi': float(last.get('rsi', 50)) if has_enriched else rsi,
            'entry_price': float(entry_price),
            'stop_loss': float(stop_loss),
            'take_profit': float(take_profit),
            'atr': float(atr),
            'current_price': float(current_price)
        }
    
    def _calculate_agreement(self, signals: Dict) -> Tuple[float, List[str]]:
        """Calculate multi-timeframe agreement"""
        directions = [s['direction'] for s in signals.values() if s]
        
        if not directions:
            return 0, ["No signals available"]
        
        # Count agreement
        buy_count = directions.count('BUY')
        sell_count = directions.count('SELL')
        
        reasons = []
        
        if buy_count >= 2:
            agreement = (buy_count / len(directions)) * 100
            reasons.append(f"{buy_count}/{len(directions)} timeframes bullish")
            return agreement, reasons
        elif sell_count >= 2:
            agreement = (sell_count / len(directions)) * 100
            reasons.append(f"{sell_count}/{len(directions)} timeframes bearish")
            return agreement, reasons
        else:
            reasons.append("No multi-timeframe agreement")
            return 30, reasons
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate RSI"""
        if len(df) < period + 1:
            return 50
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50

    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ATR with safe fallback for order planning."""
        if df is None or len(df) < period + 1:
            fallback_price = float(df['close'].iloc[-1]) if df is not None and len(df) > 0 else 1.0
            return max(fallback_price * 0.001, 0.0005)

        high_low = df['high'] - df['low']
        high_close = (df['high'] - df['close'].shift(1)).abs()
        low_close = (df['low'] - df['close'].shift(1)).abs()
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean().iloc[-1]

        if pd.isna(atr) or atr <= 0:
            fallback_price = float(df['close'].iloc[-1])
            return max(fallback_price * 0.001, 0.0005)

        return float(atr)


class ExecutionSniper:
    """
    BOT 3: EXECUTION SNIPER
    Handles order execution with precision
    """
    
    def __init__(self, account_balance: float):
        self.status = BotStatus.ACTIVE
        self.position_sizer = KellyPositionSizer(account_balance)
        self.active_orders = []

    def _estimate_pip_size(self, symbol: str, price: float) -> float:
        """Estimate pip size for stop distance conversion."""
        symbol_upper = str(symbol).upper()
        if symbol_upper.startswith('XAU') or symbol_upper.startswith('XAG'):
            return 0.01
        if symbol_upper.endswith('JPY'):
            return 0.01
        if price >= 100:
            return 0.01
        return 0.0001
        
    def prepare_order(self, validation: ValidationResult,
                     ict_signal: Optional[ICTSignal],
                     strategy: str) -> Optional[ExecutionOrder]:
        """
        Prepare order for execution
        
        Args:
            validation: Validation result from PrecisionConfirmer
            ict_signal: ICT signal (if available)
            strategy: Strategy name
            
        Returns:
            ExecutionOrder ready for market
        """
        if not validation.valid:
            return None

        # Determine direction
        m15_signal = validation.m15_signal or {}
        direction = str(m15_signal.get('direction', 'NEUTRAL')).upper()
        if direction == 'LONG':
            direction = 'BUY'
        elif direction == 'SHORT':
            direction = 'SELL'
        if direction == 'NEUTRAL':
            return None

        # Use ICT levels when available and aligned; otherwise use confirmation fallback levels.
        if ict_signal and str(getattr(ict_signal, 'direction', '')).upper() in ('BUY', 'SELL'):
            ict_direction = str(ict_signal.direction).upper()
            if ict_direction != direction:
                ict_signal = None

        if ict_signal:
            entry_price = ict_signal.entry_price
            stop_loss = ict_signal.stop_loss
            take_profit = ict_signal.take_profit
        else:
            entry_price = float(m15_signal.get('entry_price', 0.0) or 0.0)
            stop_loss = float(m15_signal.get('stop_loss', 0.0) or 0.0)
            take_profit = float(m15_signal.get('take_profit', 0.0) or 0.0)

            if not all([entry_price, stop_loss, take_profit]):
                current_price = float(m15_signal.get('current_price', 0.0) or 0.0)
                atr = float(m15_signal.get('atr', 0.0) or 0.0)
                if current_price > 0 and atr > 0:
                    entry_price = current_price
                    if direction == 'BUY':
                        stop_loss = entry_price - (atr * 1.5)
                        take_profit = entry_price + (atr * 2.5)
                    else:
                        stop_loss = entry_price + (atr * 1.5)
                        take_profit = entry_price - (atr * 2.5)

        if not all([entry_price, stop_loss, take_profit]):
            return None

        if direction == 'BUY' and not (stop_loss < entry_price < take_profit):
            return None
        if direction == 'SELL' and not (take_profit < entry_price < stop_loss):
            return None

        # Calculate position size
        pip_size = self._estimate_pip_size(validation.symbol, float(entry_price))
        stop_pips = abs(entry_price - stop_loss) / pip_size if pip_size > 0 else abs(entry_price - stop_loss) * 10000
        stop_pips = max(float(stop_pips), 1.0)

        position_size = self.position_sizer.calculate_position_size(
            symbol=validation.symbol,
            strategy=strategy,
            stop_loss_pips=stop_pips,
            entry_price=entry_price,
            market_volatility=0.5,  # Default
            open_positions=None
        )

        if position_size.lot_size <= 0:
            return None

        return ExecutionOrder(
            symbol=validation.symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            lot_size=position_size.lot_size,
            risk_percent=position_size.risk_percent,
            strategy=strategy,
            confidence=validation.agreement_score,
            validation_score=validation.agreement_score
        )


class Guardian:
    """
    BOT 4: GUARDIAN
    Risk monitoring & circuit breaker
    """
    
    def __init__(self, account_balance: float):
        self.status = BotStatus.ACTIVE
        self.circuit_breaker = TradingCircuitBreaker(account_balance)
        self.portfolio_positions = {}
        
    def check_risk_approval(self, order: ExecutionOrder) -> Tuple[bool, Optional[str]]:
        """
        Check if order passes risk checks
        
        Args:
            order: Execution order to validate
            
        Returns:
            (approved, reason_if_not_approved)
        """
        # Check circuit breaker
        can_trade, reason = self.circuit_breaker.can_trade()
        if not can_trade:
            return False, f"Circuit breaker: {reason}"
        
        # Check position limits
        if len(self.portfolio_positions) >= 5:
            return False, "Maximum 5 concurrent positions"
        
        # Check correlation (simplified)
        if order.symbol in self.portfolio_positions:
            return False, f"Already have position in {order.symbol}"
        
        # Check risk percentage
        if order.risk_percent > 2.0:
            return False, f"Risk too high: {order.risk_percent:.1f}%"
        
        return True, None
    
    def monitor_positions(self, market_data: Dict) -> List[str]:
        """Monitor active positions for exits"""
        alerts = []
        
        for symbol, position in self.portfolio_positions.items():
            if symbol in market_data:
                # Check for exit triggers
                # (Simplified - full implementation would check multiple triggers)
                current_price = market_data[symbol]['close'].iloc[-1]
                
                if position['direction'] == 'BUY':
                    if current_price >= position['take_profit']:
                        alerts.append(f"Take profit hit: {symbol}")
                    elif current_price <= position['stop_loss']:
                        alerts.append(f"Stop loss hit: {symbol}")
                else:
                    if current_price <= position['take_profit']:
                        alerts.append(f"Take profit hit: {symbol}")
                    elif current_price >= position['stop_loss']:
                        alerts.append(f"Stop loss hit: {symbol}")
        
        return alerts


class DynamicStrategyOrchestrator:
    """
    Main orchestrator coordinating all 4 bots
    """
    
    def __init__(self, config: Dict):
        self.config = config

        raw_symbols = config.get('symbols', ['EURUSD', 'GBPUSD', 'XAUUSD'])
        if isinstance(raw_symbols, dict):
            symbols = list(raw_symbols.get('primary', []))
        elif isinstance(raw_symbols, (list, tuple, set)):
            symbols = list(raw_symbols)
        else:
            symbols = ['EURUSD', 'GBPUSD', 'XAUUSD']

        strategy_config = config.get('strategy_config', config)
        
        # Initialize all 4 bots with ALL 117 strategies
        self.scout = SniperScout(
            symbols,
            strategy_config  # Pass strategy config to MasterStrategyManager
        )
        self.confirmer = PrecisionConfirmer()
        self.executor = ExecutionSniper(config.get('account_balance', 10000))
        self.guardian = Guardian(config.get('account_balance', 10000))
        
        # Strategy components
        self.conflict_manager = StrategyConflictManager()
        self.ict_engine = ICT2022Engine()
        
        self.cycle_count = 0
        
    def run_cycle(self, market_data: Dict[str, pd.DataFrame]) -> Dict:
        """
        Run one complete orchestration cycle
        
        Args:
            market_data: Dictionary of symbol -> dataframe (multi-timeframe)
            
        Returns:
            Cycle results with signals and actions
        """
        self.cycle_count += 1
        results = {
            'cycle': self.cycle_count,
            'timestamp': datetime.now(),
            'watchlist': [],
            'validations': [],
            'orders': [],
            'alerts': []
        }
        
        # STEP 1: Scout scans markets
        watchlist = self.scout.scan_markets(market_data)
        results['watchlist'] = watchlist

        # Pick a diverse set of top setups (unique symbols, class-aware).
        candidate_items = self._select_validation_candidates(watchlist, max_symbols=5)
        
        # STEP 2: Confirmer validates top setups (unique symbols only)
        for item in candidate_items:
            symbol = item.symbol
            
            # Get multi-timeframe data
            df_m15 = market_data.get(f"{symbol}_M15", market_data.get(symbol))
            df_h1 = market_data.get(f"{symbol}_H1")
            df_h4 = market_data.get(f"{symbol}_H4")
            
            if df_m15 is None:
                continue
            
            validation = self.confirmer.validate_setup(symbol, df_m15, df_h1, df_h4)
            results['validations'].append(validation)
            
            # STEP 3: Executor prepares orders for valid setups
            if validation.valid:
                # Get ICT signal if available
                ict_signal = self.ict_engine.analyze(df_m15, symbol)
                
                order = self.executor.prepare_order(validation, ict_signal, item.pattern)
                
                if order:
                    # STEP 4: Guardian checks risk
                    approved, reason = self.guardian.check_risk_approval(order)
                    
                    if approved:
                        results['orders'].append(order)
                    else:
                        results['alerts'].append(f"Order rejected: {reason}")
        
        # STEP 5: Guardian monitors existing positions
        alerts = self.guardian.monitor_positions(market_data)
        results['alerts'].extend(alerts)
        
        return results

    def _classify_asset_class(self, symbol: str) -> str:
        """Classify symbols for validation diversity control."""
        symbol_upper = str(symbol or '').upper()
        if any(token in symbol_upper for token in ('CRASH', 'BOOM', 'VOLATILITY', 'STEP INDEX')):
            return 'SYNTHETICS'
        if symbol_upper.startswith('XAU') or symbol_upper.startswith('XAG'):
            return 'METALS'
        if len(symbol_upper) == 6 and symbol_upper.isalpha():
            return 'FOREX'
        return 'OTHER'

    def _select_validation_candidates(self, watchlist: List[WatchlistItem], max_symbols: int = 5) -> List[WatchlistItem]:
        """
        Select top candidates with unique symbols and asset-class diversity.

        Rules:
        1) keep best-confidence entry per symbol;
        2) first pass: one symbol per asset class where possible;
        3) second pass: fill remaining slots by confidence.
        """
        if not watchlist:
            return []

        best_per_symbol: Dict[str, WatchlistItem] = {}
        for item in watchlist:
            existing = best_per_symbol.get(item.symbol)
            if existing is None or float(item.confidence) > float(existing.confidence):
                best_per_symbol[item.symbol] = item

        unique_items = sorted(
            best_per_symbol.values(),
            key=lambda x: float(getattr(x, 'confidence', 0.0)),
            reverse=True,
        )

        selected: List[WatchlistItem] = []
        used_symbols = set()
        covered_classes = set()

        # Pass 1: diversify by class.
        for item in unique_items:
            if len(selected) >= max_symbols:
                break
            asset_class = self._classify_asset_class(item.symbol)
            if asset_class in covered_classes:
                continue
            selected.append(item)
            used_symbols.add(item.symbol)
            covered_classes.add(asset_class)

        # Pass 2: fill by confidence.
        for item in unique_items:
            if len(selected) >= max_symbols:
                break
            if item.symbol in used_symbols:
                continue
            selected.append(item)
            used_symbols.add(item.symbol)

        return selected[:max_symbols]
    
    def print_cycle_results(self, results: Dict):
        """Print cycle results in readable format"""
        print("\n" + "="*80)
        print(f"ORCHESTRATOR CYCLE #{results['cycle']}")
        print(f"Timestamp: {results['timestamp'].strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*80)
        
        print(f"\nWATCHLIST ({len(results['watchlist'])} items):")
        for item in results['watchlist'][:5]:
            print(f"  • {item.symbol:10s} | {item.pattern:20s} | "
                  f"Confidence: {item.confidence:.0f}%")
        
        print(f"\nVALIDATIONS ({len(results['validations'])} checked):")
        for val in results['validations']:
            status = "✓ VALID" if val.valid else "✗ INVALID"
            print(f"  {status} | {val.symbol:10s} | Agreement: {val.agreement_score:.0f}%")
        
        print(f"\nORDERS ({len(results['orders'])} ready):")
        for order in results['orders']:
            print(f"  • {order.direction:4s} {order.symbol:10s} @ {order.entry_price:.5f} | "
                  f"Lot: {order.lot_size:.2f} | Risk: {order.risk_percent:.2f}%")
        
        if results['alerts']:
            print(f"\nALERTS ({len(results['alerts'])}):")
            for alert in results['alerts']:
                print(f"  ⚠ {alert}")
        
        print("="*80 + "\n")
