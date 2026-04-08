"""Forward performance validator for live-trading safety gates."""

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class ForwardValidationResult:
    """Result of forward performance validation."""

    passed: bool
    blocking: bool
    reason: str
    evaluated_trades: int
    metrics: Dict[str, float]
    thresholds: Dict[str, float]


class ForwardPerformanceValidator:
    """Validate if forward performance quality is sufficient for live mode."""

    def __init__(self, config: Dict = None):
        cfg = config or {}

        self.enabled = bool(cfg.get("enabled", True))
        self.block_live_mode = bool(cfg.get("block_live_mode", True))

        self.min_trades = int(cfg.get("min_trades", 30))
        self.lookback_trades = int(cfg.get("lookback_trades", 200))

        self.min_profit_factor = float(cfg.get("min_profit_factor", 1.20))
        self.min_expectancy = float(cfg.get("min_expectancy", 0.0))
        self.min_expectancy_pct = float(cfg.get("min_expectancy_pct", 0.0))
        self.max_drawdown_pct = float(cfg.get("max_drawdown_pct", 0.12))

        self.require_closed_trades = bool(cfg.get("require_closed_trades", True))
        self.min_abs_pnl_for_closed = float(cfg.get("min_abs_pnl_for_closed", 1e-8))

        # Optional walk-forward matrix gate by asset class.
        matrix_cfg = cfg.get("walk_forward_matrix", {})
        self.matrix_enabled = bool(matrix_cfg.get("enabled", False))
        self.matrix_block_live_mode = bool(matrix_cfg.get("block_live_mode", self.block_live_mode))
        self.matrix_required_classes = [
            str(c).upper() for c in matrix_cfg.get("required_classes", ["FOREX", "METALS", "SYNTHETICS"])
        ]
        self.matrix_min_trades_per_class = int(matrix_cfg.get("min_trades_per_class", 20))
        self.matrix_window_size = int(matrix_cfg.get("window_size", 30))
        self.matrix_step_size = int(matrix_cfg.get("step_size", 10))
        self.matrix_min_profit_factor = float(matrix_cfg.get("min_profit_factor", self.min_profit_factor))
        self.matrix_min_win_rate = float(matrix_cfg.get("min_win_rate", 48.0))
        self.matrix_max_drawdown_pct = float(matrix_cfg.get("max_drawdown_pct", self.max_drawdown_pct))
        self.matrix_min_pass_ratio = float(matrix_cfg.get("min_pass_ratio", 0.60))
        self.matrix_block_on_insufficient_trades = bool(
            matrix_cfg.get("block_on_insufficient_trades", False)
        )

    def _is_closed_trade(self, trade) -> bool:
        """Heuristic to treat unresolved placeholder records as not closed."""
        pnl = float(getattr(trade, "pnl", 0.0) or 0.0)
        entry_time = getattr(trade, "entry_time", None)
        exit_time = getattr(trade, "exit_time", None)

        duration_closed = False
        if entry_time is not None and exit_time is not None:
            try:
                duration_closed = exit_time > entry_time
            except Exception:
                duration_closed = False

        return abs(pnl) > self.min_abs_pnl_for_closed or duration_closed

    def _compute_max_drawdown(self, pnls: List[float], starting_balance: float) -> float:
        """Compute max drawdown from cumulative forward PnL stream."""
        balance = max(float(starting_balance), 1.0)
        peak = balance
        max_drawdown = 0.0

        for pnl in pnls:
            balance += float(pnl)
            if balance > peak:
                peak = balance
            if peak > 0:
                drawdown = (peak - balance) / peak
                if drawdown > max_drawdown:
                    max_drawdown = drawdown

        return max_drawdown

    def evaluate(self, trades: List, account_balance: float) -> ForwardValidationResult:
        """Evaluate forward performance against configured quality thresholds."""
        thresholds = {
            "min_trades": float(self.min_trades),
            "min_profit_factor": float(self.min_profit_factor),
            "min_expectancy": float(self.min_expectancy),
            "min_expectancy_pct": float(self.min_expectancy_pct),
            "max_drawdown_pct": float(self.max_drawdown_pct),
        }

        if not self.enabled:
            return ForwardValidationResult(
                passed=True,
                blocking=False,
                reason="Forward validator disabled",
                evaluated_trades=0,
                metrics={},
                thresholds=thresholds,
            )

        evaluation_trades = list(trades or [])

        if self.require_closed_trades:
            evaluation_trades = [t for t in evaluation_trades if self._is_closed_trade(t)]

        if self.lookback_trades > 0 and len(evaluation_trades) > self.lookback_trades:
            evaluation_trades = evaluation_trades[-self.lookback_trades :]

        total = len(evaluation_trades)

        if total < self.min_trades:
            reason = f"Insufficient closed forward trades ({total} < {self.min_trades})"
            return ForwardValidationResult(
                passed=False,
                blocking=self.block_live_mode,
                reason=reason,
                evaluated_trades=total,
                metrics={
                    "profit_factor": 0.0,
                    "expectancy": 0.0,
                    "expectancy_pct": 0.0,
                    "max_drawdown_pct": 0.0,
                    "win_rate": 0.0,
                },
                thresholds=thresholds,
            )

        pnls = [float(getattr(t, "pnl", 0.0) or 0.0) for t in evaluation_trades]
        pnl_pcts = [float(getattr(t, "pnl_percent", 0.0) or 0.0) for t in evaluation_trades]

        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]

        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))

        if gross_loss > 0:
            profit_factor = gross_profit / gross_loss
        elif gross_profit > 0:
            profit_factor = 999.0
        else:
            profit_factor = 0.0

        expectancy = sum(pnls) / total
        expectancy_pct = (sum(pnl_pcts) / len(pnl_pcts)) if pnl_pcts else 0.0
        win_rate = (len(winners) / total) * 100.0
        max_drawdown_pct = self._compute_max_drawdown(pnls, account_balance)

        metrics = {
            "profit_factor": float(profit_factor),
            "expectancy": float(expectancy),
            "expectancy_pct": float(expectancy_pct),
            "max_drawdown_pct": float(max_drawdown_pct),
            "win_rate": float(win_rate),
        }

        failures = []
        if profit_factor < self.min_profit_factor:
            failures.append(f"PF {profit_factor:.2f} < {self.min_profit_factor:.2f}")
        if expectancy < self.min_expectancy:
            failures.append(f"Expectancy {expectancy:.2f} < {self.min_expectancy:.2f}")
        if expectancy_pct < self.min_expectancy_pct:
            failures.append(
                f"Expectancy% {expectancy_pct:.3f} < {self.min_expectancy_pct:.3f}"
            )
        if max_drawdown_pct > self.max_drawdown_pct:
            failures.append(f"MaxDD {max_drawdown_pct:.2%} > {self.max_drawdown_pct:.2%}")

        passed = len(failures) == 0
        reason = "PASS" if passed else "; ".join(failures)

        return ForwardValidationResult(
            passed=passed,
            blocking=(not passed and self.block_live_mode),
            reason=reason,
            evaluated_trades=total,
            metrics=metrics,
            thresholds=thresholds,
        )

    def _iter_walk_forward_windows(self, total: int) -> List[tuple]:
        """Build rolling windows for walk-forward style evaluation."""
        if total <= 0:
            return []

        window = max(5, self.matrix_window_size)
        step = max(1, self.matrix_step_size)

        if total <= window:
            return [(0, total)]

        windows = []
        start = 0
        while start + window <= total:
            windows.append((start, start + window))
            start += step

        if windows and windows[-1][1] < total:
            windows.append((total - window, total))

        return windows

    def _window_metrics(self, window_trades: List, account_balance: float) -> Dict[str, float]:
        """Compute PF/WR/DD metrics for a window."""
        pnls = [float(getattr(t, "pnl", 0.0) or 0.0) for t in window_trades]
        winners = [p for p in pnls if p > 0]
        losers = [p for p in pnls if p < 0]

        gross_profit = sum(winners)
        gross_loss = abs(sum(losers))
        if gross_loss > 0:
            pf = gross_profit / gross_loss
        elif gross_profit > 0:
            pf = 999.0
        else:
            pf = 0.0

        win_rate = (len(winners) / len(window_trades)) * 100.0 if window_trades else 0.0
        max_dd = self._compute_max_drawdown(pnls, account_balance)

        return {
            "profit_factor": float(pf),
            "win_rate": float(win_rate),
            "max_drawdown_pct": float(max_dd),
        }

    def evaluate_walk_forward_matrix(
        self,
        trades: List,
        account_balance: float,
        classify_asset_class: Callable[[str], str],
        required_classes: Optional[List[str]] = None,
    ) -> Dict:
        """
        Evaluate reliability by asset class using walk-forward windows.

        Returns a dict with pass/fail details for deployment gating.
        """
        if not self.matrix_enabled:
            return {
                "enabled": False,
                "passed": True,
                "blocking": False,
                "reason": "walk_forward_matrix_disabled",
                "classes": {},
            }

        evaluation_trades = list(trades or [])
        if self.require_closed_trades:
            evaluation_trades = [t for t in evaluation_trades if self._is_closed_trade(t)]

        grouped: Dict[str, List] = {}
        for trade in evaluation_trades:
            symbol = str(getattr(trade, "symbol", "") or "")
            asset_class = str(classify_asset_class(symbol) or "OTHER").upper()
            grouped.setdefault(asset_class, []).append(trade)

        class_results = {}
        failures = []
        only_insufficient_failures = True
        classes_to_evaluate = [
            str(c).upper() for c in (required_classes or self.matrix_required_classes) if str(c).strip()
        ]
        if not classes_to_evaluate:
            classes_to_evaluate = list(self.matrix_required_classes)

        for class_name in classes_to_evaluate:
            class_trades = grouped.get(class_name, [])
            total = len(class_trades)

            if total < self.matrix_min_trades_per_class:
                class_results[class_name] = {
                    "passed": False,
                    "total_trades": total,
                    "windows": 0,
                    "pass_ratio": 0.0,
                    "reason": (
                        f"insufficient_trades_{total}_lt_{self.matrix_min_trades_per_class}"
                    ),
                }
                failures.append(f"{class_name}: insufficient trades ({total})")
                continue

            windows = self._iter_walk_forward_windows(total)
            passed_windows = 0
            window_metrics = []

            for start, end in windows:
                subset = class_trades[start:end]
                metrics = self._window_metrics(subset, account_balance)
                passed = (
                    metrics["profit_factor"] >= self.matrix_min_profit_factor
                    and metrics["win_rate"] >= self.matrix_min_win_rate
                    and metrics["max_drawdown_pct"] <= self.matrix_max_drawdown_pct
                )
                if passed:
                    passed_windows += 1

                window_metrics.append({
                    "start": start,
                    "end": end,
                    "passed": passed,
                    **metrics,
                })

            pass_ratio = (passed_windows / len(windows)) if windows else 0.0
            class_passed = pass_ratio >= self.matrix_min_pass_ratio

            class_results[class_name] = {
                "passed": class_passed,
                "total_trades": total,
                "windows": len(windows),
                "passed_windows": passed_windows,
                "pass_ratio": float(pass_ratio),
                "min_pass_ratio": float(self.matrix_min_pass_ratio),
                "window_metrics": window_metrics,
            }

            if not class_passed:
                only_insufficient_failures = False
                failures.append(
                    f"{class_name}: pass_ratio {pass_ratio:.2f} < {self.matrix_min_pass_ratio:.2f}"
                )

        passed = len(failures) == 0
        reason = "PASS" if passed else "; ".join(failures)
        blocking = (not passed and self.matrix_block_live_mode)
        if (not passed and only_insufficient_failures and not self.matrix_block_on_insufficient_trades):
            blocking = False

        return {
            "enabled": True,
            "passed": passed,
            "blocking": blocking,
            "reason": reason,
            "only_insufficient_failures": bool((not passed) and only_insufficient_failures),
            "classes": class_results,
            "required_classes": classes_to_evaluate,
            "thresholds": {
                "min_trades_per_class": self.matrix_min_trades_per_class,
                "window_size": self.matrix_window_size,
                "step_size": self.matrix_step_size,
                "min_profit_factor": self.matrix_min_profit_factor,
                "min_win_rate": self.matrix_min_win_rate,
                "max_drawdown_pct": self.matrix_max_drawdown_pct,
                "min_pass_ratio": self.matrix_min_pass_ratio,
                "block_on_insufficient_trades": self.matrix_block_on_insufficient_trades,
            },
        }
