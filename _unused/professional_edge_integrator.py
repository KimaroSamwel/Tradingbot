"""
PROFESSIONAL EDGE INTEGRATOR
Coordinates all new professional trading modules

Integrates:
- Advanced Position Sizing (Optimal F, Fixed Ratio, Percent Vol)
- Seasonality Analysis (Monthly/Weekly/Intraday patterns)
- Wyckoff Method (Accumulation/Distribution)
- Portfolio Heat Management
- Carry Trade Analysis
- Crisis Detection
- Sentiment Analysis
"""

import pandas as pd
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime

from src.execution.advanced_position_sizing import AdvancedPositionSizer
from src.analysis.seasonality_analyzer import SeasonalityAnalyzer
from src.analysis.wyckoff_analyzer import WyckoffAnalyzer
from src.risk.portfolio_heat import PortfolioHeatCalculator
from src.analysis.carry_trade_analyzer import CarryTradeAnalyzer
from src.analysis.crisis_detector import CrisisDetector
from src.analysis.sentiment_analyzer import SentimentAnalyzer
from src.analysis.elliott_wave_analyzer import ElliottWaveAnalyzer


@dataclass
class ProfessionalEdgeSignal:
    """Comprehensive professional analysis signal"""
    symbol: str
    timestamp: datetime
    
    # Position sizing
    recommended_sizing_method: str
    position_size: float
    risk_percent: float
    
    # Seasonality
    seasonality_bias: float  # -1 to +1
    seasonality_confidence: float
    
    # Wyckoff
    wyckoff_phase: str
    wyckoff_direction: str
    wyckoff_confidence: float
    
    # Elliott Wave
    elliott_wave: str
    elliott_wave_confidence: float
    
    # Portfolio
    portfolio_heat: float
    heat_warning: str
    
    # Carry
    carry_bias: str
    carry_strength: float
    carry_swap_info: str
    
    # Crisis
    crisis_level: str
    volatility_factor: float
    
    # Sentiment
    sentiment_signal: str
    
    # Overall
    overall_recommendation: str
    confidence_score: float


class ProfessionalEdgeIntegrator:
    """
    Master coordinator for all professional trading edge modules
    """
    
    def __init__(self, account_balance: float, config: Dict = None):
        """
        Initialize all professional modules
        
        Args:
            account_balance: Current account balance
            config: Configuration dictionary
        """
        self.account_balance = account_balance
        self.config = config or {}
        
        # Initialize all modules
        self.position_sizer = AdvancedPositionSizer(
            account_balance, 
            self.config.get('advanced_sizing', {})
        )
        
        seasonality_cfg = self.config.get('seasonality', {})
        wyckoff_cfg = self.config.get('wyckoff', {})
        portfolio_heat_cfg = self.config.get('portfolio_heat', {})
        elliott_cfg = self.config.get('elliott_wave', {})

        self.seasonality = SeasonalityAnalyzer(
            timezone_offset=seasonality_cfg.get('timezone_offset', 3)
        )
        
        self.wyckoff = WyckoffAnalyzer(
            lookback_period=wyckoff_cfg.get('lookback_period', 100)
        )
        
        self.portfolio_heat = PortfolioHeatCalculator(
            account_balance,
            max_heat=portfolio_heat_cfg.get('max_heat_percent', 6.0)
        )
        
        self.carry_analyzer = CarryTradeAnalyzer()
        self.crisis_detector = CrisisDetector()
        self.sentiment_analyzer = SentimentAnalyzer()
        self.elliott_wave = ElliottWaveAnalyzer(
            lookback_period=elliott_cfg.get('lookback_period', 200)
        )
        
    def analyze(self, symbol: str, df: pd.DataFrame,
                current_positions: List[Dict],
                atr: float, price: float, pip_value: float,
                live_account_balance: float = None) -> ProfessionalEdgeSignal:
        """
        Perform comprehensive professional analysis
        
        Args:
            symbol: Trading symbol
            df: Price dataframe
            current_positions: List of active positions
            atr: Average True Range
            price: Current price
            pip_value: Pip value for symbol
            live_account_balance: Current live MT5 equity (optional, updates position sizer)
            
        Returns:
            Comprehensive professional edge signal
        """
        # FIX #33: Update position sizer with live equity before calculations
        if live_account_balance is not None and live_account_balance > 0:
            self.account_balance = live_account_balance
            self.position_sizer.account_balance = live_account_balance
            self.portfolio_heat.balance = live_account_balance
        
        current_time = datetime.now()
        
        # 1. Seasonality Analysis
        seasonality_bias, season_rec = self.seasonality.get_overall_bias(
            current_time, symbol
        )
        all_patterns = self.seasonality.analyze_all_patterns(current_time, symbol)
        season_conf = self._calc_seasonality_confidence(all_patterns)
        
        # 2. Wyckoff Analysis
        wyckoff_signal = self.wyckoff.analyze(df)
        
        # 3. Elliott Wave Analysis
        elliott_signal = self.elliott_wave.analyze(df)
        
        # 4. Portfolio Heat
        heat_metrics = self.portfolio_heat.calculate_heat(current_positions)
        
        # 5. Carry Trade (with swap tracking)
        carry_signal = self.carry_analyzer.analyze(symbol, current_time)
        
        # 6. Crisis Detection
        crisis_signal = self.crisis_detector.detect(df, symbol)
        
        # 7. Sentiment Analysis (would need real data in production)
        sentiment_signal = self.sentiment_analyzer.analyze(symbol, 50.0)
        
        # 8. Advanced Position Sizing
        sizing_results = self.position_sizer.compare_methods(atr, price, pip_value)
        best_sizing = self._select_best_sizing(sizing_results, crisis_signal.level)
        
        # Generate overall recommendation
        overall_rec, confidence = self._generate_overall_recommendation(
            wyckoff_signal, elliott_signal, seasonality_bias, carry_signal,
            crisis_signal, sentiment_signal, heat_metrics
        )
        
        # Format swap info
        swap_info = f"Long: {carry_signal.daily_swap_long:.2f} | Short: {carry_signal.daily_swap_short:.2f}"
        if carry_signal.wednesday_triple_swap:
            swap_info += " | Triple Swap Day!"
        
        return ProfessionalEdgeSignal(
            symbol=symbol,
            timestamp=current_time,
            recommended_sizing_method=best_sizing.method,
            position_size=best_sizing.lot_size,
            risk_percent=best_sizing.risk_percent,
            seasonality_bias=seasonality_bias,
            seasonality_confidence=season_conf,
            wyckoff_phase=wyckoff_signal.phase.value,
            wyckoff_direction=wyckoff_signal.direction,
            wyckoff_confidence=wyckoff_signal.confidence,
            elliott_wave=f"Wave {elliott_signal.wave_count.current_wave} ({elliott_signal.wave_count.wave_type.value})",
            elliott_wave_confidence=elliott_signal.confidence,
            portfolio_heat=heat_metrics.total_heat,
            heat_warning=heat_metrics.recommendation,
            carry_bias=carry_signal.bias,
            carry_strength=carry_signal.rate_diff,
            carry_swap_info=swap_info,
            crisis_level=crisis_signal.level,
            volatility_factor=crisis_signal.vix_equivalent,
            sentiment_signal=sentiment_signal.contrarian_signal,
            overall_recommendation=overall_rec,
            confidence_score=confidence
        )
    
    def _calc_seasonality_confidence(self, all_patterns: Dict) -> float:
        """Calculate average seasonality confidence"""
        total_conf = 0
        count = 0
        
        for pattern_list in all_patterns.values():
            for pattern in pattern_list:
                total_conf += pattern.confidence
                count += 1
                
        return total_conf / count if count > 0 else 50.0
    
    def _select_best_sizing(self, sizing_results: List, crisis_level: str):
        """Select best sizing method based on conditions"""
        if crisis_level in ["HIGH", "EXTREME"]:
            # Use most conservative in crisis
            return min(sizing_results, key=lambda x: x.risk_percent)
        else:
            # Use highest confidence method
            return max(sizing_results, key=lambda x: x.confidence)
    
    def _generate_overall_recommendation(self, wyckoff, elliott_wave, seasonality_bias,
                                        carry, crisis, sentiment, heat):
        """Generate overall trading recommendation"""
        signals = []

        crisis_cfg = self.config.get('crisis_detection', {})
        stop_on_extreme = bool(crisis_cfg.get('stop_on_extreme', True))
        crisis_level = str(getattr(crisis, 'level', 'NORMAL')).upper()

        def _normalize_direction(direction: str) -> str:
            d = (direction or "").upper()
            if d == "LONG":
                return "BUY"
            if d == "SHORT":
                return "SELL"
            return d
        
        # Wyckoff
        if wyckoff.confidence > 70:
            signals.append((_normalize_direction(wyckoff.direction), wyckoff.confidence))
        
        # Elliott Wave
        if elliott_wave.confidence > 60:
            signals.append((_normalize_direction(elliott_wave.direction), elliott_wave.confidence))
        
        # Seasonality
        if abs(seasonality_bias) > 0.2:
            direction = "BUY" if seasonality_bias > 0 else "SELL"
            signals.append((direction, abs(seasonality_bias) * 100))
        
        # Carry
        if carry.bias != "NEUTRAL" and carry.confidence > 60:
            signals.append((_normalize_direction(carry.bias), carry.confidence))
        
        # Sentiment (contrarian)
        if sentiment.contrarian_signal != "NEUTRAL":
            signals.append((_normalize_direction(sentiment.contrarian_signal), sentiment.confidence))
        
        # Crisis override (config-aware)
        # NOTE:
        # - EXTREME can hard-block if stop_on_extreme=True
        # - HIGH is handled as risk reduction in get_enhanced_signal, not hard block
        if crisis_level == "EXTREME" and stop_on_extreme:
            return "NO TRADE - Crisis EXTREME", 0.0
        
        # Heat override
        if heat.heat_ratio > 0.9:
            return "NO TRADE - Portfolio heat limit", 0.0
        
        # Aggregate signals
        if not signals:
            return "NEUTRAL - Insufficient edge", 40.0
        
        buy_signals = [s for s in signals if s[0] == "BUY"]
        sell_signals = [s for s in signals if s[0] in ["SELL", "SHORT"]]
        
        buy_conf = sum(s[1] for s in buy_signals) / len(signals) if buy_signals else 0
        sell_conf = sum(s[1] for s in sell_signals) / len(signals) if sell_signals else 0
        
        if buy_conf > sell_conf and buy_conf > 50:
            return f"BUY - {len(buy_signals)} professional signals aligned", buy_conf
        elif sell_conf > buy_conf and sell_conf > 50:
            return f"SELL - {len(sell_signals)} professional signals aligned", sell_conf
        else:
            return "NEUTRAL - Mixed signals", max(buy_conf, sell_conf)
    
    def get_enhanced_signal(self, symbol: str, df: pd.DataFrame,
                          base_signal: Dict, current_positions: List[Dict],
                          atr: float, pip_value: float,
                          live_account_balance: float = None) -> Dict:
        """
        Enhance existing signal with professional analysis

        Args:
            symbol: Trading symbol
            df: Price dataframe
            base_signal: Original trading signal
            current_positions: Active positions
            atr: Average True Range
            pip_value: Pip value
            live_account_balance: Current live MT5 equity (optional)

        Returns:
            Enhanced signal with professional insights
        """
        price = df['close'].iloc[-1]

        # Get professional analysis
        pro_signal = self.analyze(
            symbol, df, current_positions,
            atr, price, pip_value,
            live_account_balance=live_account_balance
        )

        # Merge with base signal
        enhanced = base_signal.copy()
        enhanced['professional_edge'] = {
            'wyckoff_phase': pro_signal.wyckoff_phase,
            'wyckoff_confidence': pro_signal.wyckoff_confidence,
            'elliott_wave': pro_signal.elliott_wave,
            'elliott_wave_confidence': pro_signal.elliott_wave_confidence,
            'seasonality_bias': pro_signal.seasonality_bias,
            'carry_bias': pro_signal.carry_bias,
            'carry_swap_info': pro_signal.carry_swap_info,
            'crisis_level': pro_signal.crisis_level,
            'portfolio_heat': pro_signal.portfolio_heat,
            'recommended_sizing': pro_signal.recommended_sizing_method,
            'overall_recommendation': pro_signal.overall_recommendation,
            'confidence_boost': pro_signal.confidence_score
        }

        base_direction = (base_signal.get('direction') or '').upper()
        if base_direction == 'LONG':
            base_direction = 'BUY'
        elif base_direction == 'SHORT':
            base_direction = 'SELL'

        crisis_cfg = self.config.get('crisis_detection', {})
        stop_on_extreme = bool(crisis_cfg.get('stop_on_extreme', True))
        reduce_on_high = bool(crisis_cfg.get('reduce_on_high', True))

        high_crisis_risk_multiplier = crisis_cfg.get('high_crisis_risk_multiplier', 0.5)
        try:
            high_crisis_risk_multiplier = float(high_crisis_risk_multiplier)
        except (TypeError, ValueError):
            high_crisis_risk_multiplier = 0.5
        high_crisis_risk_multiplier = min(max(high_crisis_risk_multiplier, 0.1), 1.0)

        crisis_level = str(getattr(pro_signal, 'crisis_level', 'NORMAL')).upper()

        # Adjust base signal confidence
        if pro_signal.overall_recommendation.startswith("BUY") and base_direction == 'BUY':
            enhanced['confidence'] = min(enhanced.get('confidence', 60) + 10, 95)
        elif pro_signal.overall_recommendation.startswith("SELL") and base_direction == 'SELL':
            enhanced['confidence'] = min(enhanced.get('confidence', 60) + 10, 95)
        elif pro_signal.overall_recommendation.startswith("NO TRADE"):
            should_block = True

            # Respect configured behavior: HIGH crisis should reduce risk, not hard-stop.
            if crisis_level == 'HIGH' and reduce_on_high:
                should_block = False
            elif crisis_level == 'EXTREME' and not stop_on_extreme:
                should_block = False

            if should_block:
                enhanced['confidence'] = 0  # Block trade
                enhanced['blocked_reason'] = pro_signal.overall_recommendation

        if crisis_level == 'HIGH' and reduce_on_high and enhanced.get('confidence', 0) > 0:
            enhanced['risk_multiplier'] = high_crisis_risk_multiplier

        return enhanced
