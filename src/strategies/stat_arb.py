"""Statistical arbitrage utilities (pairs/z-score based)."""

from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


class StatisticalArbitrage:
    """Cointegration-inspired selection and z-score spread triggers."""

    def __init__(self, config: Dict):
        cfg = config or {}
        self.correlation_threshold = float(cfg.get("correlation_threshold", 0.8) or 0.8)
        self.z_score_entry = float(cfg.get("z_score_entry", 2.0) or 2.0)
        self.z_score_exit = float(cfg.get("z_score_exit", 0.5) or 0.5)

    def find_cointegrated_pairs(self, symbols_data: Dict[str, pd.DataFrame], lookback: int = 100) -> List[Tuple[str, str, float]]:
        pairs: List[Tuple[str, str, float]] = []
        symbols = list(symbols_data.keys())

        for i, s1 in enumerate(symbols):
            df1 = symbols_data.get(s1)
            if df1 is None or len(df1) < lookback:
                continue
            ret1 = df1["close"].pct_change().dropna().tail(lookback)

            for s2 in symbols[i + 1 :]:
                df2 = symbols_data.get(s2)
                if df2 is None or len(df2) < lookback:
                    continue
                ret2 = df2["close"].pct_change().dropna().tail(lookback)
                idx = ret1.index.intersection(ret2.index)
                if len(idx) < lookback // 2:
                    continue
                corr = float(ret1.loc[idx].corr(ret2.loc[idx]))
                if np.isfinite(corr) and abs(corr) >= self.correlation_threshold:
                    pairs.append((s1, s2, corr))

        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        return pairs

    def calculate_spread_zscore(self, pair_data: Dict[str, pd.DataFrame]) -> Dict:
        if len(pair_data) != 2:
            return {"zscore": 0.0, "spread": 0.0, "signal": "NONE"}

        symbols = list(pair_data.keys())
        s1, s2 = symbols[0], symbols[1]
        c1 = pair_data[s1]["close"].astype(float)
        c2 = pair_data[s2]["close"].astype(float)
        idx = c1.index.intersection(c2.index)
        c1, c2 = c1.loc[idx], c2.loc[idx]

        if len(c1) < 50:
            return {"zscore": 0.0, "spread": 0.0, "signal": "NONE"}

        spread = c1 - c2
        mean = spread.rolling(50).mean().iloc[-1]
        std = spread.rolling(50).std().iloc[-1]
        if not np.isfinite(std) or std <= 1e-10:
            return {"zscore": 0.0, "spread": float(spread.iloc[-1]), "signal": "NONE"}

        zscore = float((spread.iloc[-1] - mean) / std)
        if zscore >= self.z_score_entry:
            signal = "SHORT_SPREAD"
        elif zscore <= -self.z_score_entry:
            signal = "LONG_SPREAD"
        elif abs(zscore) <= self.z_score_exit:
            signal = "EXIT"
        else:
            signal = "HOLD"

        return {
            "pair": (s1, s2),
            "spread": float(spread.iloc[-1]),
            "zscore": zscore,
            "signal": signal,
        }
