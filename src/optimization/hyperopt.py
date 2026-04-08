"""Lightweight parameter optimizer with randomized search."""

from __future__ import annotations

import itertools
import random
from typing import Dict, List, Tuple


class HyperoptOptimizer:
    """Freqtrade-style optimization wrapper (randomized grid search)."""

    def __init__(self, strategy_class, parameter_space: Dict[str, List], optimization_metric: str = "sharpe_ratio"):
        self.strategy_class = strategy_class
        self.param_space = parameter_space or {}
        self.optimization_metric = optimization_metric

    def _iter_candidates(self) -> List[Dict]:
        if not self.param_space:
            return [{}]
        keys = list(self.param_space.keys())
        values = [self.param_space[k] for k in keys]
        return [dict(zip(keys, combo)) for combo in itertools.product(*values)]

    def optimize(self, evaluator, iterations: int = 200) -> Tuple[Dict, float]:
        candidates = self._iter_candidates()
        if not candidates:
            return {}, float("-inf")

        if iterations > 0 and len(candidates) > iterations:
            candidates = random.sample(candidates, iterations)

        best_params = {}
        best_score = float("-inf")

        for params in candidates:
            score = float(evaluator(self.strategy_class, params, self.optimization_metric) or float("-inf"))
            if score > best_score:
                best_score = score
                best_params = params

        return best_params, best_score

    def validate_on_out_of_sample(self, validator, best_params: Dict, test_data) -> Dict:
        return validator(self.strategy_class, best_params, test_data, self.optimization_metric)
