"""Sentiment & Positioning Analyzer (COT-style)"""
from dataclasses import dataclass

@dataclass
class SentimentSignal:
    retail_bias: str
    institutional_bias: str
    contrarian_signal: str
    confidence: float

class SentimentAnalyzer:
    def __init__(self):
        self.retail_positions = {}
        
    def analyze(self, symbol: str, retail_long_pct: float = 50.0) -> SentimentSignal:
        # Contrarian logic: fade retail
        if retail_long_pct > 70:
            return SentimentSignal("BULLISH", "BEARISH", "SELL", 75.0)
        elif retail_long_pct < 30:
            return SentimentSignal("BEARISH", "BULLISH", "BUY", 75.0)
        else:
            return SentimentSignal("NEUTRAL", "NEUTRAL", "NEUTRAL", 40.0)
