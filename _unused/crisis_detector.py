"""Crisis & Volatility Spike Detector"""
import pandas as pd
import numpy as np
from dataclasses import dataclass

@dataclass
class CrisisSignal:
    level: str  # NORMAL, ELEVATED, HIGH, EXTREME
    vix_equivalent: float
    recommendation: str

class CrisisDetector:
    def __init__(self):
        self.normal_atr_baseline = {}
        
    def detect(self, df: pd.DataFrame, symbol: str) -> CrisisSignal:
        atr = df['high'] - df['low']
        current_atr = atr.iloc[-1]
        avg_atr = atr.mean()
        
        volatility_ratio = current_atr / avg_atr if avg_atr > 0 else 1.0
        
        if volatility_ratio > 3.0:
            return CrisisSignal("EXTREME", volatility_ratio * 100, 
                              "STOP TRADING: Flash crash conditions")
        elif volatility_ratio > 2.0:
            return CrisisSignal("HIGH", volatility_ratio * 100,
                              "Reduce size 75%, tight stops")
        elif volatility_ratio > 1.5:
            return CrisisSignal("ELEVATED", volatility_ratio * 100,
                              "Reduce size 50%, widen stops")
        else:
            return CrisisSignal("NORMAL", volatility_ratio * 100,
                              "Normal trading conditions")
