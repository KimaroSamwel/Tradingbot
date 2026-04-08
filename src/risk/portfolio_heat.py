"""Portfolio Heat Calculator - Aggregate portfolio risk"""
import pandas as pd
import numpy as np
from typing import Dict, List
from dataclasses import dataclass

@dataclass
class PortfolioHeat:
    total_heat: float
    max_heat: float
    heat_ratio: float
    recommendation: str

class PortfolioHeatCalculator:
    def __init__(self, account_balance: float, max_heat: float = 6.0):
        self.balance = account_balance
        self._base_max_heat = max_heat
        self.max_heat = self._adaptive_max_heat(account_balance, max_heat)

    def _adaptive_max_heat(self, balance: float, base_heat: float) -> float:
        """Scale max_heat for micro accounts. Small balances need higher heat tolerance."""
        if balance <= 0:
            return base_heat
        if balance < 50:
            return max(base_heat, 30.0)   # Micro (<$50): allow 30% heat
        if balance < 200:
            return max(base_heat, 20.0)   # Small (<$200): allow 20% heat
        if balance < 1000:
            return max(base_heat, 12.0)   # Medium (<$1000): allow 12% heat
        return base_heat                   # Standard accounts: use configured limit
        
    def calculate_heat(self, positions: List[Dict]) -> PortfolioHeat:
        self.max_heat = self._adaptive_max_heat(self.balance, self._base_max_heat)
        total_risk = sum(p.get('risk_amount', 0) for p in positions)
        heat_pct = (total_risk / max(self.balance, 1.0)) * 100
        ratio = heat_pct / self.max_heat
        
        if ratio > 1.0:
            rec = "DANGER: Reduce positions immediately"
        elif ratio > 0.8:
            rec = "WARNING: Near max heat limit"
        else:
            rec = "OK: Heat within acceptable range"
            
        return PortfolioHeat(heat_pct, self.max_heat, ratio, rec)
