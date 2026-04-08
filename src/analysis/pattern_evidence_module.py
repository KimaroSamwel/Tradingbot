"""Pattern Evidence Module: template-based confidence + regime gating + A/B gate tracking."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
        if out != out:  # NaN
            return float(default)
        return out
    except Exception:
        return float(default)


@dataclass
class TemplateEvidence:
    template_id: str
    family: str
    matched: bool
    score: float
    weight: float
    details: Dict[str, float]


@dataclass
class PatternEvidenceResult:
    enabled: bool
    symbol: str
    direction: str
    strategy: str
    ab_variant: str
    regime_label: str
    regime_confidence: float
    regime_allowed: bool
    bearish_pullback_score: float
    bullish_confirmation_score: float
    confidence_score: float
    gate_passed: bool
    execution_allowed: bool
    should_block: bool
    reasons: List[str]
    templates: List[TemplateEvidence]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "symbol": self.symbol,
            "direction": self.direction,
            "strategy": self.strategy,
            "ab_variant": self.ab_variant,
            "regime_label": self.regime_label,
            "regime_confidence": self.regime_confidence,
            "regime_allowed": self.regime_allowed,
            "bearish_pullback_score": self.bearish_pullback_score,
            "bullish_confirmation_score": self.bullish_confirmation_score,
            "confidence_score": self.confidence_score,
            "gate_passed": self.gate_passed,
            "execution_allowed": self.execution_allowed,
            "should_block": self.should_block,
            "reasons": list(self.reasons),
            "templates": [
                {
                    "template_id": t.template_id,
                    "family": t.family,
                    "matched": bool(t.matched),
                    "score": float(t.score),
                    "weight": float(t.weight),
                    "details": dict(t.details),
                }
                for t in self.templates
            ],
        }


class PatternEvidenceModule:
    """Codifies bearish pullback / bullish confirmation templates for live order gating."""

    BEARISH_TEMPLATE_WEIGHTS = {
        "bearish_engulfing_rejection": 1.00,
        "lower_high_breakdown": 1.00,
        "ema21_pullback_reject": 0.95,
        "fib_618_rejection": 0.90,
        "inside_bar_breakdown": 0.85,
        "rsi_failure_swing_bear": 0.85,
    }

    BULLISH_TEMPLATE_WEIGHTS = {
        "bullish_engulfing_support": 1.00,
        "higher_low_breakout": 1.00,
        "ema21_reclaim_continuation": 0.95,
        "volume_momentum_breakout": 0.90,
    }

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("enabled", True))
        self.lookback_bars = max(60, int(cfg.get("lookback_bars", 140) or 140))
        self.min_confidence = _clamp(_safe_float(cfg.get("min_confidence", 62.0), 62.0), 0.0, 100.0)
        self.min_regime_confidence = _clamp(
            _safe_float(cfg.get("min_regime_confidence", 30.0), 30.0),
            0.0,
            100.0,
        )
        self.counter_signal_penalty = _clamp(
            _safe_float(cfg.get("counter_signal_penalty", 0.30), 0.30),
            0.0,
            1.0,
        )
        self.base_confidence_blend = _clamp(
            _safe_float(cfg.get("base_confidence_blend", 0.35), 0.35),
            0.0,
            1.0,
        )
        self.fail_on_insufficient_data = bool(cfg.get("fail_on_insufficient_data", False))

        gate_cfg = cfg.get("regime_gate", {}) if isinstance(cfg.get("regime_gate", {}), dict) else {}
        self.require_regime_alignment = bool(gate_cfg.get("require_alignment", True))
        self.bearish_allowed_regimes = {
            str(item).upper()
            for item in gate_cfg.get(
                "bearish_allowed_regimes",
                ["STRONG_DOWNTREND", "MODERATE_DOWNTREND", "TRANSITION", "RANGING"],
            )
            if str(item).strip()
        }
        self.bullish_allowed_regimes = {
            str(item).upper()
            for item in gate_cfg.get(
                "bullish_allowed_regimes",
                ["STRONG_UPTREND", "MODERATE_UPTREND", "TRANSITION", "RANGING"],
            )
            if str(item).strip()
        }

        ab_cfg = cfg.get("ab_testing", {}) if isinstance(cfg.get("ab_testing", {}), dict) else {}
        self.ab_enabled = bool(ab_cfg.get("enabled", True))
        self.control_ratio = _clamp(_safe_float(ab_cfg.get("control_ratio", 0.25), 0.25), 0.0, 1.0)
        self.ab_seed = str(ab_cfg.get("seed", "pattern-evidence-v1") or "pattern-evidence-v1")

        self._ab_stats = {
            "A_CONTROL": {"evaluated": 0, "gate_passed": 0, "gate_failed": 0, "bypass": 0},
            "B_TREATMENT": {"evaluated": 0, "gate_passed": 0, "gate_failed": 0, "bypass": 0},
        }

    @property
    def bearish_template_names(self) -> List[str]:
        return list(self.BEARISH_TEMPLATE_WEIGHTS.keys())

    @property
    def bullish_template_names(self) -> List[str]:
        return list(self.BULLISH_TEMPLATE_WEIGHTS.keys())

    def snapshot(self) -> Dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "lookback_bars": int(self.lookback_bars),
            "min_confidence": float(self.min_confidence),
            "min_regime_confidence": float(self.min_regime_confidence),
            "ab_testing": {
                "enabled": bool(self.ab_enabled),
                "control_ratio": float(self.control_ratio),
                "seed": self.ab_seed,
                "stats": {
                    variant: dict(values)
                    for variant, values in self._ab_stats.items()
                },
            },
        }

    def evaluate(
        self,
        symbol: str,
        direction: str,
        strategy: str,
        df: Optional[pd.DataFrame],
        regime_analysis: Optional[Any] = None,
        base_confidence: float = 0.0,
    ) -> PatternEvidenceResult:
        symbol_value = str(symbol or "UNKNOWN")
        strategy_value = str(strategy or "UNKNOWN")
        direction_value = str(direction or "").upper()
        if direction_value == "LONG":
            direction_value = "BUY"
        elif direction_value == "SHORT":
            direction_value = "SELL"

        variant = self._assign_variant(symbol_value, direction_value, strategy_value)

        if not self.enabled:
            return self._result_disabled(symbol_value, direction_value, strategy_value, variant)

        frame = self._prepare_frame(df)
        if frame is None or len(frame) < 40:
            reasons = ["insufficient_market_data"]
            gate_passed = not self.fail_on_insufficient_data
            execution_allowed = gate_passed or variant == "A_CONTROL"
            should_block = not execution_allowed
            self._update_ab_stats(variant, gate_passed, execution_allowed)
            return PatternEvidenceResult(
                enabled=True,
                symbol=symbol_value,
                direction=direction_value,
                strategy=strategy_value,
                ab_variant=variant,
                regime_label="UNKNOWN",
                regime_confidence=0.0,
                regime_allowed=not self.require_regime_alignment,
                bearish_pullback_score=0.0,
                bullish_confirmation_score=0.0,
                confidence_score=0.0,
                gate_passed=gate_passed,
                execution_allowed=execution_allowed,
                should_block=should_block,
                reasons=reasons,
                templates=[],
            )

        regime_label, regime_confidence, regime_allowed = self._evaluate_regime_gate(
            direction=direction_value,
            regime_analysis=regime_analysis,
        )

        atr = self._atr(frame, 14)
        rsi_series = self._rsi(frame["close"], 14)
        ema21 = frame["close"].ewm(span=21, adjust=False).mean()
        ema50 = frame["close"].ewm(span=50, adjust=False).mean()
        volume_ratio = self._volume_ratio(frame)

        templates = self._evaluate_templates(frame, atr, rsi_series, ema21, ema50, volume_ratio)

        bearish_score = self._family_score(templates, family="bearish_pullback")
        bullish_score = self._family_score(templates, family="bullish_confirmation")

        if direction_value == "SELL":
            primary_score = bearish_score
            counter_score = bullish_score
        elif direction_value == "BUY":
            primary_score = bullish_score
            counter_score = bearish_score
        else:
            primary_score = 0.0
            counter_score = 0.0

        blended = (
            primary_score * (1.0 - self.base_confidence_blend)
            + _clamp(_safe_float(base_confidence, 0.0), 0.0, 100.0) * self.base_confidence_blend
        )
        confidence_score = blended - (counter_score * self.counter_signal_penalty)
        confidence_score += 5.0 if regime_allowed else -25.0
        confidence_score = _clamp(confidence_score, 0.0, 100.0)

        reasons: List[str] = []
        gate_passed = True
        if self.require_regime_alignment and not regime_allowed:
            gate_passed = False
            reasons.append(f"regime_gate:{regime_label}:{regime_confidence:.1f}")

        if confidence_score < self.min_confidence:
            gate_passed = False
            reasons.append(
                f"confidence_below_threshold:{confidence_score:.1f}<{self.min_confidence:.1f}"
            )

        if gate_passed:
            reasons.append("pattern_evidence_pass")

        execution_allowed = bool(gate_passed)
        if not gate_passed and variant == "A_CONTROL":
            execution_allowed = True
            reasons.append("ab_control_bypass")

        should_block = not execution_allowed
        self._update_ab_stats(variant, gate_passed, execution_allowed)

        return PatternEvidenceResult(
            enabled=True,
            symbol=symbol_value,
            direction=direction_value,
            strategy=strategy_value,
            ab_variant=variant,
            regime_label=regime_label,
            regime_confidence=regime_confidence,
            regime_allowed=regime_allowed,
            bearish_pullback_score=bearish_score,
            bullish_confirmation_score=bullish_score,
            confidence_score=confidence_score,
            gate_passed=gate_passed,
            execution_allowed=execution_allowed,
            should_block=should_block,
            reasons=reasons,
            templates=templates,
        )

    def _result_disabled(
        self,
        symbol: str,
        direction: str,
        strategy: str,
        variant: str,
    ) -> PatternEvidenceResult:
        self._update_ab_stats(variant, gate_passed=True, execution_allowed=True)
        return PatternEvidenceResult(
            enabled=False,
            symbol=symbol,
            direction=direction,
            strategy=strategy,
            ab_variant=variant,
            regime_label="DISABLED",
            regime_confidence=100.0,
            regime_allowed=True,
            bearish_pullback_score=0.0,
            bullish_confirmation_score=0.0,
            confidence_score=100.0,
            gate_passed=True,
            execution_allowed=True,
            should_block=False,
            reasons=["pattern_evidence_disabled"],
            templates=[],
        )

    def _assign_variant(self, symbol: str, direction: str, strategy: str) -> str:
        if not self.ab_enabled:
            return "B_TREATMENT"

        key = f"{self.ab_seed}|{symbol}|{direction}|{strategy}"
        digest = sha256(key.encode("utf-8")).hexdigest()[:8]
        bucket = int(digest, 16) / 0xFFFFFFFF
        return "A_CONTROL" if bucket < self.control_ratio else "B_TREATMENT"

    def _update_ab_stats(self, variant: str, gate_passed: bool, execution_allowed: bool) -> None:
        payload = self._ab_stats.get(variant)
        if not isinstance(payload, dict):
            return
        payload["evaluated"] = int(payload.get("evaluated", 0)) + 1
        if gate_passed:
            payload["gate_passed"] = int(payload.get("gate_passed", 0)) + 1
        else:
            payload["gate_failed"] = int(payload.get("gate_failed", 0)) + 1
        if execution_allowed and not gate_passed:
            payload["bypass"] = int(payload.get("bypass", 0)) + 1

    def _prepare_frame(self, df: Optional[pd.DataFrame]) -> Optional[pd.DataFrame]:
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            return None

        required = {"open", "high", "low", "close"}
        if not required.issubset(set(df.columns)):
            return None

        frame = df.copy()
        for col in ("open", "high", "low", "close", "volume", "tick_volume"):
            if col in frame.columns:
                frame[col] = pd.to_numeric(frame[col], errors="coerce")

        frame = frame.dropna(subset=["open", "high", "low", "close"])
        if frame.empty:
            return None

        frame = frame.sort_index()
        if len(frame) > self.lookback_bars:
            frame = frame.tail(self.lookback_bars)
        return frame

    def _evaluate_regime_gate(
        self,
        direction: str,
        regime_analysis: Optional[Any],
    ) -> Tuple[str, float, bool]:
        regime = "UNKNOWN"
        confidence = 0.0

        if regime_analysis is not None:
            trend_obj = getattr(regime_analysis, "trend_regime", None)
            regime = str(getattr(trend_obj, "value", trend_obj) or "UNKNOWN").upper()
            confidence = _clamp(_safe_float(getattr(regime_analysis, "confidence", 0.0), 0.0), 0.0, 100.0)

        if not self.require_regime_alignment:
            return regime, confidence, True

        if direction == "SELL":
            allowed = regime in self.bearish_allowed_regimes
        elif direction == "BUY":
            allowed = regime in self.bullish_allowed_regimes
        else:
            allowed = False

        if confidence < self.min_regime_confidence:
            allowed = False

        return regime, confidence, bool(allowed)

    def _evaluate_templates(
        self,
        df: pd.DataFrame,
        atr: float,
        rsi: pd.Series,
        ema21: pd.Series,
        ema50: pd.Series,
        volume_ratio: float,
    ) -> List[TemplateEvidence]:
        out: List[TemplateEvidence] = []

        out.append(self._bearish_engulfing_rejection(df, atr))
        out.append(self._lower_high_breakdown(df, atr, ema21, ema50))
        out.append(self._ema21_pullback_reject(df, atr, ema21, ema50))
        out.append(self._fib_618_rejection(df, atr, rsi, ema21, ema50))
        out.append(self._inside_bar_breakdown(df, atr, ema21, ema50))
        out.append(self._rsi_failure_swing_bear(df, atr, rsi, ema21, ema50))

        out.append(self._bullish_engulfing_support(df, atr))
        out.append(self._higher_low_breakout(df, atr, ema21, ema50))
        out.append(self._ema21_reclaim_continuation(df, atr, ema21, ema50))
        out.append(self._volume_momentum_breakout(df, rsi, ema21, ema50, volume_ratio))

        return out

    def _family_score(self, templates: Sequence[TemplateEvidence], family: str) -> float:
        scoped = [t for t in templates if t.family == family]
        if not scoped:
            return 0.0

        total_weight = sum(max(0.0, _safe_float(t.weight, 0.0)) for t in scoped)
        if total_weight <= 0:
            return 0.0

        weighted = sum(_safe_float(t.score, 0.0) * max(0.0, _safe_float(t.weight, 0.0)) for t in scoped)
        return _clamp(weighted / total_weight, 0.0, 100.0)

    def _score_template(
        self,
        template_id: str,
        family: str,
        conditions: Sequence[Tuple[str, bool, float]],
    ) -> TemplateEvidence:
        total_weight = sum(max(0.0, _safe_float(weight, 0.0)) for _, _, weight in conditions)
        if total_weight <= 0:
            score = 0.0
            details = {name: 0.0 for name, _, _ in conditions}
        else:
            earned = sum(
                max(0.0, _safe_float(weight, 0.0))
                for _, is_true, weight in conditions
                if bool(is_true)
            )
            score = _clamp((earned / total_weight) * 100.0, 0.0, 100.0)
            details = {
                name: (1.0 if bool(is_true) else 0.0)
                for name, is_true, _ in conditions
            }

        if family == "bearish_pullback":
            weight = _safe_float(self.BEARISH_TEMPLATE_WEIGHTS.get(template_id, 1.0), 1.0)
        else:
            weight = _safe_float(self.BULLISH_TEMPLATE_WEIGHTS.get(template_id, 1.0), 1.0)

        return TemplateEvidence(
            template_id=template_id,
            family=family,
            matched=score >= 60.0,
            score=score,
            weight=weight,
            details=details,
        )

    def _bearish_engulfing_rejection(self, df: pd.DataFrame, atr: float) -> TemplateEvidence:
        prev = df.iloc[-2]
        curr = df.iloc[-1]
        recent_high = _safe_float(df["high"].tail(30).max(), _safe_float(curr["high"], 0.0))

        prev_body = abs(_safe_float(prev["close"]) - _safe_float(prev["open"]))
        curr_body = abs(_safe_float(curr["close"]) - _safe_float(curr["open"]))
        near_high = (recent_high - max(_safe_float(curr["open"]), _safe_float(curr["close"]))) <= max(atr * 1.2, 1e-9)

        return self._score_template(
            template_id="bearish_engulfing_rejection",
            family="bearish_pullback",
            conditions=[
                ("prev_bullish", _safe_float(prev["close"]) > _safe_float(prev["open"]), 1.0),
                ("curr_bearish", _safe_float(curr["close"]) < _safe_float(curr["open"]), 1.0),
                (
                    "engulfing",
                    _safe_float(curr["open"]) >= _safe_float(prev["close"]) and _safe_float(curr["close"]) <= _safe_float(prev["open"]),
                    1.4,
                ),
                ("body_dominance", curr_body >= max(prev_body * 0.9, 1e-9), 0.9),
                ("near_resistance", near_high, 0.9),
            ],
        )

    def _lower_high_breakdown(
        self,
        df: pd.DataFrame,
        atr: float,
        ema21: pd.Series,
        ema50: pd.Series,
    ) -> TemplateEvidence:
        highs = df["high"].tail(8)
        lows = df["low"].tail(8)
        close = df["close"].tail(8)
        curr = df.iloc[-1]

        body = abs(_safe_float(curr["close"]) - _safe_float(curr["open"]))
        cond_lower_high = _safe_float(highs.iloc[-1]) < _safe_float(highs.iloc[-3])
        cond_breakdown = _safe_float(close.iloc[-1]) < _safe_float(lows.iloc[-2])

        return self._score_template(
            template_id="lower_high_breakdown",
            family="bearish_pullback",
            conditions=[
                ("lower_high", cond_lower_high, 1.1),
                ("break_below_prev_low", cond_breakdown, 1.2),
                ("ema_trend_down", _safe_float(ema21.iloc[-1]) < _safe_float(ema50.iloc[-1]), 1.1),
                ("bearish_close", _safe_float(curr["close"]) < _safe_float(curr["open"]), 0.8),
                ("impulse_body", body >= max(atr * 0.35, 1e-9), 0.8),
            ],
        )

    def _ema21_pullback_reject(
        self,
        df: pd.DataFrame,
        atr: float,
        ema21: pd.Series,
        ema50: pd.Series,
    ) -> TemplateEvidence:
        curr = df.iloc[-1]
        highs = df["high"].tail(5)

        upper_wick = _safe_float(curr["high"]) - max(_safe_float(curr["open"]), _safe_float(curr["close"]))
        body = abs(_safe_float(curr["close"]) - _safe_float(curr["open"]))

        touched_ema = _safe_float(highs.iloc[:-1].max(), 0.0) >= _safe_float(ema21.iloc[-2], 0.0)

        return self._score_template(
            template_id="ema21_pullback_reject",
            family="bearish_pullback",
            conditions=[
                ("ema_stack_bear", _safe_float(ema21.iloc[-1]) < _safe_float(ema50.iloc[-1]), 1.2),
                ("pullback_touched_ema21", touched_ema, 1.0),
                ("close_back_below_ema21", _safe_float(curr["close"]) < _safe_float(ema21.iloc[-1]), 1.1),
                ("bearish_candle", _safe_float(curr["close"]) < _safe_float(curr["open"]), 0.8),
                ("rejection_wick", upper_wick > body * 0.8 and upper_wick > max(atr * 0.1, 1e-9), 0.8),
            ],
        )

    def _fib_618_rejection(
        self,
        df: pd.DataFrame,
        atr: float,
        rsi: pd.Series,
        ema21: pd.Series,
        ema50: pd.Series,
    ) -> TemplateEvidence:
        window = df.iloc[-35:-5] if len(df) >= 40 else df.iloc[:-1]
        curr = df.iloc[-1]

        if window.empty:
            return self._score_template(
                template_id="fib_618_rejection",
                family="bearish_pullback",
                conditions=[("window_available", False, 1.0)],
            )

        swing_high = _safe_float(window["high"].max(), _safe_float(curr["high"], 0.0))
        swing_low = _safe_float(window["low"].min(), _safe_float(curr["low"], 0.0))
        leg = max(swing_high - swing_low, 1e-9)
        retrace = (_safe_float(curr["close"]) - swing_low) / leg

        return self._score_template(
            template_id="fib_618_rejection",
            family="bearish_pullback",
            conditions=[
                ("retracement_zone", 0.48 <= retrace <= 0.72, 1.3),
                ("rejection_candle", _safe_float(curr["close"]) < _safe_float(curr["open"]), 1.0),
                ("trend_filter", _safe_float(ema21.iloc[-1]) < _safe_float(ema50.iloc[-1]), 1.0),
                ("touch_55_plus", _safe_float(curr["high"]) >= (swing_low + leg * 0.55), 0.8),
                ("rsi_rollover", _safe_float(rsi.iloc[-1], 50.0) < 55.0, 0.7),
                ("candle_range_ok", (_safe_float(curr["high"]) - _safe_float(curr["low"])) >= max(atr * 0.35, 1e-9), 0.7),
            ],
        )

    def _inside_bar_breakdown(
        self,
        df: pd.DataFrame,
        atr: float,
        ema21: pd.Series,
        ema50: pd.Series,
    ) -> TemplateEvidence:
        mother = df.iloc[-3]
        inside = df.iloc[-2]
        curr = df.iloc[-1]

        inside_ok = (
            _safe_float(inside["high"]) < _safe_float(mother["high"])
            and _safe_float(inside["low"]) > _safe_float(mother["low"])
        )
        body = abs(_safe_float(curr["close"]) - _safe_float(curr["open"]))
        inside_range = max(_safe_float(inside["high"]) - _safe_float(inside["low"]), 1e-9)

        return self._score_template(
            template_id="inside_bar_breakdown",
            family="bearish_pullback",
            conditions=[
                ("inside_bar", inside_ok, 1.2),
                ("close_below_inside_low", _safe_float(curr["close"]) < _safe_float(inside["low"]), 1.3),
                ("bearish_body", _safe_float(curr["close"]) < _safe_float(curr["open"]), 0.8),
                ("body_expansion", body > inside_range * 0.4, 0.8),
                ("ema_trend_down", _safe_float(ema21.iloc[-1]) < _safe_float(ema50.iloc[-1]), 0.9),
                ("range_vs_atr", (_safe_float(curr["high"]) - _safe_float(curr["low"])) >= max(atr * 0.3, 1e-9), 0.6),
            ],
        )

    def _rsi_failure_swing_bear(
        self,
        df: pd.DataFrame,
        atr: float,
        rsi: pd.Series,
        ema21: pd.Series,
        ema50: pd.Series,
    ) -> TemplateEvidence:
        highs = df["high"].tail(8)
        closes = df["close"].tail(8)
        recent_rsi = rsi.tail(8)

        return self._score_template(
            template_id="rsi_failure_swing_bear",
            family="bearish_pullback",
            conditions=[
                ("rsi_recent_push", _safe_float(recent_rsi.max(), 0.0) > 60.0, 1.1),
                ("rsi_below_50", _safe_float(recent_rsi.iloc[-1], 50.0) < 50.0, 1.1),
                ("price_lower_high", _safe_float(highs.iloc[-1]) <= _safe_float(highs.iloc[-3]), 0.9),
                ("close_weakness", _safe_float(closes.iloc[-1]) < _safe_float(closes.iloc[-2]), 0.9),
                ("ema_trend_down", _safe_float(ema21.iloc[-1]) < _safe_float(ema50.iloc[-1]), 1.0),
                ("atr_presence", atr > 0.0, 0.5),
            ],
        )

    def _bullish_engulfing_support(self, df: pd.DataFrame, atr: float) -> TemplateEvidence:
        prev = df.iloc[-2]
        curr = df.iloc[-1]
        recent_low = _safe_float(df["low"].tail(30).min(), _safe_float(curr["low"], 0.0))

        prev_body = abs(_safe_float(prev["close"]) - _safe_float(prev["open"]))
        curr_body = abs(_safe_float(curr["close"]) - _safe_float(curr["open"]))
        near_low = (min(_safe_float(curr["open"]), _safe_float(curr["close"])) - recent_low) <= max(atr * 1.2, 1e-9)

        return self._score_template(
            template_id="bullish_engulfing_support",
            family="bullish_confirmation",
            conditions=[
                ("prev_bearish", _safe_float(prev["close"]) < _safe_float(prev["open"]), 1.0),
                ("curr_bullish", _safe_float(curr["close"]) > _safe_float(curr["open"]), 1.0),
                (
                    "engulfing",
                    _safe_float(curr["open"]) <= _safe_float(prev["close"]) and _safe_float(curr["close"]) >= _safe_float(prev["open"]),
                    1.4,
                ),
                ("body_dominance", curr_body >= max(prev_body * 0.9, 1e-9), 0.9),
                ("near_support", near_low, 0.9),
            ],
        )

    def _higher_low_breakout(
        self,
        df: pd.DataFrame,
        atr: float,
        ema21: pd.Series,
        ema50: pd.Series,
    ) -> TemplateEvidence:
        lows = df["low"].tail(8)
        highs = df["high"].tail(8)
        curr = df.iloc[-1]
        body = abs(_safe_float(curr["close"]) - _safe_float(curr["open"]))

        cond_higher_low = _safe_float(lows.iloc[-2]) > _safe_float(lows.iloc[-4])
        cond_breakout = _safe_float(curr["close"]) > _safe_float(highs.iloc[-2])

        return self._score_template(
            template_id="higher_low_breakout",
            family="bullish_confirmation",
            conditions=[
                ("higher_low", cond_higher_low, 1.1),
                ("break_prev_high", cond_breakout, 1.2),
                ("ema_trend_up", _safe_float(ema21.iloc[-1]) > _safe_float(ema50.iloc[-1]), 1.1),
                ("bullish_close", _safe_float(curr["close"]) > _safe_float(curr["open"]), 0.8),
                ("impulse_body", body >= max(atr * 0.35, 1e-9), 0.8),
            ],
        )

    def _ema21_reclaim_continuation(
        self,
        df: pd.DataFrame,
        atr: float,
        ema21: pd.Series,
        ema50: pd.Series,
    ) -> TemplateEvidence:
        curr = df.iloc[-1]
        lows = df["low"].tail(5)

        body = abs(_safe_float(curr["close"]) - _safe_float(curr["open"]))
        lower_wick = min(_safe_float(curr["open"]), _safe_float(curr["close"])) - _safe_float(curr["low"])
        dipped_below = _safe_float(lows.iloc[:-1].min(), 0.0) <= _safe_float(ema21.iloc[-2], 0.0)

        return self._score_template(
            template_id="ema21_reclaim_continuation",
            family="bullish_confirmation",
            conditions=[
                ("ema_stack_bull", _safe_float(ema21.iloc[-1]) > _safe_float(ema50.iloc[-1]), 1.2),
                ("dip_below_ema21", dipped_below, 1.0),
                ("close_above_ema21", _safe_float(curr["close"]) > _safe_float(ema21.iloc[-1]), 1.1),
                ("bullish_candle", _safe_float(curr["close"]) > _safe_float(curr["open"]), 0.8),
                ("absorption_wick", lower_wick > body * 0.5 and lower_wick > max(atr * 0.1, 1e-9), 0.8),
            ],
        )

    def _volume_momentum_breakout(
        self,
        df: pd.DataFrame,
        rsi: pd.Series,
        ema21: pd.Series,
        ema50: pd.Series,
        volume_ratio: float,
    ) -> TemplateEvidence:
        curr = df.iloc[-1]
        prior_high = _safe_float(df["high"].tail(21).iloc[:-1].max(), _safe_float(curr["high"], 0.0))

        return self._score_template(
            template_id="volume_momentum_breakout",
            family="bullish_confirmation",
            conditions=[
                ("range_breakout", _safe_float(curr["close"]) > prior_high, 1.4),
                ("rsi_confirm", _safe_float(rsi.iloc[-1], 50.0) > 55.0, 1.0),
                ("volume_confirm", volume_ratio >= 1.05, 1.0),
                ("ema_trend_up", _safe_float(ema21.iloc[-1]) > _safe_float(ema50.iloc[-1]), 0.9),
                ("close_progression", _safe_float(curr["close"]) > _safe_float(df["close"].iloc[-3]), 0.7),
            ],
        )

    def _atr(self, df: pd.DataFrame, period: int = 14) -> float:
        if len(df) < period + 1:
            return max(_safe_float(df["high"].tail(1).iloc[0], 1.0) * 0.001, 1e-9)

        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift(1)).abs()
        low_close = (df["low"] - df["close"].shift(1)).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = _safe_float(tr.rolling(period).mean().iloc[-1], 0.0)
        return max(atr, 1e-9)

    def _rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0.0, 0.0)
        loss = -delta.where(delta < 0.0, 0.0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss.replace(0.0, float("nan"))
        rsi = 100.0 - (100.0 / (1.0 + rs))
        return rsi.fillna(50.0).astype(float)

    def _volume_ratio(self, df: pd.DataFrame) -> float:
        source_col = None
        if "volume" in df.columns and df["volume"].notna().any():
            source_col = "volume"
        elif "tick_volume" in df.columns and df["tick_volume"].notna().any():
            source_col = "tick_volume"

        if source_col is None:
            return 1.0

        recent = _safe_float(df[source_col].tail(1).iloc[0], 0.0)
        baseline = _safe_float(df[source_col].tail(20).mean(), 0.0)
        if baseline <= 0:
            return 1.0
        return _clamp(recent / baseline, 0.0, 5.0)
