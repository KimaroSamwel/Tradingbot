"""Information-asymmetry scanner for niche-market opportunities."""

from __future__ import annotations

from typing import Dict, List


class InformationArbitrage:
    def __init__(self):
        self.niche_markets = ["esports", "regional_sports", "long_tail_events"]

    def analyze_niche_market(self, event_data: List[Dict]) -> List[Dict]:
        opportunities = []
        for event in event_data or []:
            liquidity = float(event.get("liquidity_score", 0.0) or 0.0)
            confidence = float(event.get("private_confidence", 0.0) or 0.0)
            public_prob = float(event.get("public_probability", 0.0) or 0.0)

            if liquidity < 0.35 and confidence > 0.75 and confidence > public_prob + 0.20:
                opportunities.append(
                    {
                        "event_id": event.get("event_id"),
                        "market": event.get("market"),
                        "estimated_edge": confidence - public_prob,
                        "confidence": confidence,
                    }
                )
        return opportunities
