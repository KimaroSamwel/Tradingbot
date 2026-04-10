"""
APEX FX Trading Bot - Signal Scorer
PRD Volume II Section 11: Signal Quality Scoring

Evaluates every entry candidate on a 0-100 scale across 5 weighted factor groups.
COT data plugs in as a bonus/penalty.
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class SignalScoreResult:
    """Result of signal scoring"""
    total_score: float
    grade: str
    position_modifier: float
    factor_breakdown: Dict[str, float]
    cot_adjustment: float
    symbol: str
    direction: str


class SignalScorer:
    """
    Signal Scorer - evaluates entry candidates on 0-100 scale.
    
    Factor weights (must sum to 100):
    - trend_alignment: 30 (D1+H4+H1 EMA alignment)
    - momentum: 25 (RSI zone + MACD direction)
    - regime_quality: 20 (ADX strength or BB squeeze)
    - session_timing: 15 (Optimal vs secondary window)
    - execution_quality: 10 (Spread percentile for window)
    
    Grades:
    - REJECT (0-59): modifier 0.0 - do not trade
    - MARGINAL (60-74): modifier 0.60
    - STANDARD (75-84): modifier 1.00
    - HIGH_CONVICTION (85-100): modifier 1.25
    
    COT adjustments:
    - CONFIRM (+10): COT aligns with trade direction
    - NEUTRAL (0): No COT data or unclear
    - CONTRAINDICATE (-15): COT contraindicated
    """
    
    FACTORS = {
        'trend_alignment': {'weight': 30, 'desc': 'D1+H4+H1 EMA alignment'},
        'momentum': {'weight': 25, 'desc': 'RSI zone + MACD direction'},
        'regime_quality': {'weight': 20, 'desc': 'ADX strength or BB squeeze'},
        'session_timing': {'weight': 15, 'desc': 'Optimal vs secondary window'},
        'execution_quality': {'weight': 10, 'desc': 'Spread percentile for window'},
    }
    
    GRADES = {
        (0, 14): {'grade': 'REJECT', 'modifier': 0.0},
        (15, 18): {'grade': 'MARGINAL', 'modifier': 0.60},
        (19, 23): {'grade': 'STANDARD', 'modifier': 1.00},
        (24, 30): {'grade': 'HIGH_CONVICTION', 'modifier': 1.25},
    }
    
    # COT thresholds
    COT_BONUS = 10
    COT_PENALTY = 15
    
    # Session windows
    OPTIMAL_SESSIONS = {
        'EURUSD': ['LONDON', 'OVERLAP'],
        'GBPUSD': ['LONDON'],
        'USDJPY': ['TOKYO', 'OVERLAP'],
        'USDCHF': ['LONDON'],
        'USDCAD': ['NEW_YORK'],
        'XAUUSD': ['LONDON', 'NEW_YORK'],
    }
    
    def __init__(self, config: Optional[Dict] = None, logger=None):
        """
        Initialize signal scorer.
        
        Args:
            config: Optional configuration
            logger: Optional logger
        """
        self._config = config or {}
        self._logger = logger
    
    def score(
        self,
        symbol: str,
        direction: str,
        indicators: Dict,
        session_window: str,
        spread_percentile: float,
        cot_index: Optional[float]
    ) -> Dict:
        """
        Score a signal candidate.
        
        Args:
            symbol: Trading symbol
            direction: BUY or SELL
            indicators: Dict with technical indicators
            session_window: Current session window name
            spread_percentile: Current spread percentile (0-100)
            cot_index: Optional COT index (0-100)
            
        Returns:
            Dict with total_score, grade, position_modifier, factor_breakdown, cot_adjustment
        """
        # Score each factor
        trend_score = self._score_trend_alignment(symbol, direction, indicators)
        momentum_score = self._score_momentum(indicators, direction)
        regime_score = self._score_regime(indicators)
        session_score = self._score_session(symbol, session_window)
        execution_score = self._score_execution(spread_percentile)
        
        # Build factor breakdown
        factor_breakdown = {
            'trend_alignment_score': trend_score,
            'momentum_score': momentum_score,
            'regime_quality_score': regime_score,
            'session_timing_score': session_score,
            'execution_quality_score': execution_score,
        }
        
        # Calculate total (weighted)
        total = (
            trend_score * (self.FACTORS['trend_alignment']['weight'] / 100) +
            momentum_score * (self.FACTORS['momentum']['weight'] / 100) +
            regime_score * (self.FACTORS['regime_quality']['weight'] / 100) +
            session_score * (self.FACTORS['session_timing']['weight'] / 100) +
            execution_score * (self.FACTORS['execution_quality']['weight'] / 100)
        )
        
        # Apply COT adjustment
        total_with_cot, cot_adjustment = self._apply_cot(
            total, symbol, direction, cot_index
        )
        
        # Determine grade and modifier
        grade, modifier = self._get_grade_and_modifier(total_with_cot)
        
        return {
            'symbol': symbol,
            'direction': direction,
            'total_score': round(total_with_cot, 2),
            'grade': grade,
            'position_modifier': modifier,
            'factor_breakdown': factor_breakdown,
            'cot_adjustment': cot_adjustment,
        }
    
    def _score_trend_alignment(
        self, 
        symbol: str, 
        direction: str, 
        indicators: Dict
    ) -> float:
        """
        30 pts max. D1+H4+H1 all aligned = 30. Two = 20. One = 10. None = 0.
        """
        score = 0
        
        # Check EMA alignments (simplified - use available indicators)
        ema_alignment = indicators.get('ema_alignment', {})
        
        d1_aligned = ema_alignment.get('d1', False)
        h4_aligned = ema_alignment.get('h4', False)
        h1_aligned = ema_alignment.get('h1', False)
        
        aligned_count = sum([d1_aligned, h4_aligned, h1_aligned])
        
        if aligned_count == 3:
            score = 30
        elif aligned_count == 2:
            score = 20
        elif aligned_count == 1:
            score = 10
        
        return score
    
    def _score_momentum(
        self, 
        indicators: Dict, 
        direction: str
    ) -> float:
        """
        25 pts max. RSI in ideal zone + MACD confirming = 25. One = 12. Neither = 0.
        """
        score = 0
        
        rsi = indicators.get('rsi', 50)
        macd_hist = indicators.get('macd_hist', 0)
        macd_direction = indicators.get('macd_direction')
        rsi_ideal_flag = indicators.get('rsi_ideal')
        
        # RSI ideal zones
        rsi_ideal = False
        if rsi_ideal_flag is not None:
            rsi_ideal = rsi_ideal_flag
        elif direction == 'BUY' and 40 <= rsi <= 60:
            rsi_ideal = True
        elif direction == 'SELL' and 40 <= rsi <= 60:
            rsi_ideal = True
        
        # MACD confirming
        macd_confirm = False
        if macd_direction is not None:
            macd_confirm = (macd_direction == direction)
        elif direction == 'BUY' and macd_hist > 0:
            macd_confirm = True
        elif direction == 'SELL' and macd_hist < 0:
            macd_confirm = True
        
        if rsi_ideal and macd_confirm:
            score = 25
        elif rsi_ideal or macd_confirm:
            score = 12
        
        return score
    
    def _score_regime(self, indicators: Dict) -> float:
        """
        20 pts max. ADX > 30 or BB squeeze extreme = 20. ADX 25-30 = 12. Below = 0.
        """
        score = 0
        
        adx = indicators.get('adx', 0)
        bb_width = indicators.get('bb_width', 1.0)
        bb_width_avg = indicators.get('bb_width_avg', 1.0)
        
        # ADX strength
        if adx > 30:
            score = 20
        elif 25 <= adx <= 30:
            score = 12
        
        # Or BB squeeze
        if bb_width_avg > 0 and bb_width < bb_width_avg * 0.5:
            score = max(score, 20)
        
        return score
    
    def _score_session(
        self, 
        symbol: str, 
        session_window: str
    ) -> float:
        """
        15 pts max. Optimal session = 15. Secondary = 8. Outside preferred = 0.
        """
        if not session_window:
            return 0
        
        optimal = self.OPTIMAL_SESSIONS.get(symbol, [])
        
        if session_window in optimal:
            return 15
        elif session_window in ['TOKYO', 'NEW_YORK', 'LONDON']:
            return 8
        else:
            return 0
    
    def _score_execution(self, spread_percentile: float) -> float:
        """
        10 pts max. < 40th pct = 10. 40-70th = 6. 70-80th = 3. Above = 0.
        """
        if spread_percentile < 40:
            return 10
        elif spread_percentile < 70:
            return 6
        elif spread_percentile < 80:
            return 3
        else:
            return 0
    
    def _apply_cot(
        self, 
        score: float, 
        symbol: str, 
        direction: str,
        cot_index: Optional[float]
    ) -> Tuple[float, float]:
        """
        Apply COT bonus (+10) or penalty (-15).
        
        Returns:
            Tuple of (adjusted_score, adjustment_amount)
        """
        if cot_index is None:
            return score, 0
        
        # Determine COT signal based on direction
        # If COT index > 60 (net long) and direction is BUY = bonus
        # If COT index < 40 (net short) and direction is SELL = bonus
        # Otherwise check for contraindication
        
        adjustment = 0
        
        if direction == 'BUY':
            if cot_index > 70:  # Extreme long
                adjustment = self.COT_BONUS
            elif cot_index < 30:  # Extreme short - contraindication
                adjustment = -self.COT_PENALTY
        elif direction == 'SELL':
            if cot_index < 30:  # Extreme short
                adjustment = self.COT_BONUS
            elif cot_index > 70:  # Extreme long - contraindication
                adjustment = -self.COT_PENALTY
        
        return max(0, score + adjustment), adjustment
    
    def _get_grade_and_modifier(self, score: float) -> Tuple[str, float]:
        """
        Get grade and position modifier based on total score.
        """
        for (min_score, max_score), grade_info in self.GRADES.items():
            if min_score <= score <= max_score:
                return grade_info['grade'], grade_info['modifier']
        
        return 'REJECT', 0.0


# Global instance
_signal_scorer = None


def get_signal_scorer(config: Optional[Dict] = None, logger=None) -> SignalScorer:
    """Get global signal scorer instance."""
    global _signal_scorer
    if _signal_scorer is None:
        _signal_scorer = SignalScorer(config, logger)
    return _signal_scorer