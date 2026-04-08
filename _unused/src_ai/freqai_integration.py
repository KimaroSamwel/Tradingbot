"""FreqAI-style ML integration module for feature engineering and predictions."""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

try:
    from sklearn.ensemble import RandomForestClassifier
except Exception:  # pragma: no cover
    RandomForestClassifier = None


class FeatureEngineer:
    """Build a compact technical/microstructure feature set."""

    def transform(self, data: pd.DataFrame) -> pd.DataFrame:
        if data is None or len(data) < 50:
            return pd.DataFrame()

        df = data.copy()
        close = df["close"].astype(float)
        ret = close.pct_change()

        features = pd.DataFrame(index=df.index)
        features["ret_1"] = ret
        features["ret_5"] = close.pct_change(5)
        features["ret_20"] = close.pct_change(20)
        features["vol_20"] = ret.rolling(20).std()
        features["ema_20"] = close.ewm(span=20, adjust=False).mean() / close - 1.0
        features["ema_50"] = close.ewm(span=50, adjust=False).mean() / close - 1.0
        features["range"] = (df["high"] - df["low"]) / close.replace(0, np.nan)
        features["volume_z"] = (
            (df.get("volume", pd.Series(0.0, index=df.index)) - df.get("volume", pd.Series(0.0, index=df.index)).rolling(30).mean())
            / df.get("volume", pd.Series(0.0, index=df.index)).rolling(30).std().replace(0, np.nan)
        )

        return features.replace([np.inf, -np.inf], np.nan).dropna()


class FreqAIModule:
    """ML module with periodic retraining and confidence predictions."""

    def __init__(self, config: Optional[Dict] = None):
        cfg = config or {}
        self.model_type = str(cfg.get("model_type", "random_forest"))
        self.training_window = int(cfg.get("training_window", 5000) or 5000)
        self.retrain_frequency = int(cfg.get("retrain_frequency", 100) or 100)
        self.feature_engineering = FeatureEngineer()
        self.model = None
        self.trained_on_rows = 0

    def engineer_features(self, data: pd.DataFrame) -> pd.DataFrame:
        return self.feature_engineering.transform(data)

    def train_model(self, features: pd.DataFrame, targets: pd.Series) -> bool:
        if features is None or targets is None or len(features) < 100:
            return False
        if RandomForestClassifier is None:
            return False

        aligned_targets = targets.reindex(features.index).dropna()
        aligned_features = features.reindex(aligned_targets.index)
        if len(aligned_features) < 100:
            return False

        model = RandomForestClassifier(
            n_estimators=200,
            max_depth=8,
            random_state=42,
            class_weight="balanced",
        )
        model.fit(aligned_features.values, aligned_targets.values.astype(int))
        self.model = model
        self.trained_on_rows = len(aligned_features)
        return True

    def predict_signal(self, current_features: pd.DataFrame) -> Dict:
        if self.model is None or current_features is None or len(current_features) == 0:
            return {"prediction": 0, "confidence": 0.0, "available": False}

        x = current_features.tail(1).values
        pred = int(self.model.predict(x)[0])
        if hasattr(self.model, "predict_proba"):
            probs = self.model.predict_proba(x)[0]
            confidence = float(max(probs))
        else:
            confidence = 0.5

        return {
            "prediction": pred,
            "confidence": confidence,
            "available": True,
        }
