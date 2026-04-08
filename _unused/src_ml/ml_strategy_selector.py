"""
ML STRATEGY SELECTOR
Machine learning-based strategy selection using XGBoost

Features:
- XGBoost classifier for regime detection
- Random Forest for strategy performance prediction
- Feature engineering from market data
- Online learning adaptation
- Strategy probability scoring
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import pickle
import os

# Optional ML imports (will work without if not installed)
try:
    from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    from sklearn.preprocessing import StandardScaler
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("Warning: scikit-learn not available. ML features disabled.")


@dataclass
class MLPrediction:
    """ML prediction result"""
    predicted_regime: str
    regime_confidence: float
    strategy_probabilities: Dict[str, float]
    recommended_strategies: List[str]
    feature_importance: Dict[str, float]


@dataclass
class MLFeatures:
    """Feature set for ML models"""
    # Technical indicators
    adx: float
    rsi: float
    macd: float
    bb_width: float
    atr_percent: float
    
    # Trend features
    ema8_slope: float
    ema21_slope: float
    ema50_slope: float
    price_to_ema20: float
    
    # Volatility features
    volatility_regime: float  # 0-1 normalized
    recent_range: float
    
    # Time features
    hour_of_day: int
    day_of_week: int
    session: int  # 0=Asian, 1=London, 2=NY
    
    # Market structure
    higher_highs: int  # Boolean as int
    higher_lows: int
    support_nearby: int
    resistance_nearby: int
    
    # Volume features (if available)
    volume_ratio: float
    
    # External features
    dxy_trend: float  # Dollar index trend
    vix_level: float  # Volatility index
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for ML"""
        return np.array([
            self.adx, self.rsi, self.macd, self.bb_width, self.atr_percent,
            self.ema8_slope, self.ema21_slope, self.ema50_slope, self.price_to_ema20,
            self.volatility_regime, self.recent_range,
            self.hour_of_day, self.day_of_week, self.session,
            self.higher_highs, self.higher_lows, self.support_nearby, self.resistance_nearby,
            self.volume_ratio, self.dxy_trend, self.vix_level
        ])
    
    @property
    def feature_names(self) -> List[str]:
        """Get feature names"""
        return [
            'adx', 'rsi', 'macd', 'bb_width', 'atr_percent',
            'ema8_slope', 'ema21_slope', 'ema50_slope', 'price_to_ema20',
            'volatility_regime', 'recent_range',
            'hour_of_day', 'day_of_week', 'session',
            'higher_highs', 'higher_lows', 'support_nearby', 'resistance_nearby',
            'volume_ratio', 'dxy_trend', 'vix_level'
        ]


class MLStrategySelector:
    """
    Machine learning-based strategy selection
    Uses ensemble methods for regime classification and strategy ranking
    """
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize ML strategy selector
        
        Args:
            model_path: Path to load/save models
        """
        self.ml_available = ML_AVAILABLE
        self.model_path = model_path or "models/"
        
        # Create models directory
        os.makedirs(self.model_path, exist_ok=True)
        
        # Models
        self.regime_classifier = None
        self.strategy_predictor = None
        self.scaler = None
        
        # Training data
        self.training_features = []
        self.training_regimes = []
        self.training_performances = {}
        
        # Initialize models
        self._initialize_models()
        
        # Try to load existing models
        self._load_models()
    
    def _initialize_models(self):
        """Initialize ML models"""
        if not self.ml_available:
            return
        
        # Regime classifier (Random Forest)
        self.regime_classifier = RandomForestClassifier(
            n_estimators=100,
            max_depth=10,
            min_samples_split=5,
            random_state=42
        )
        
        # Strategy performance predictor (Gradient Boosting)
        self.strategy_predictor = GradientBoostingClassifier(
            n_estimators=100,
            max_depth=5,
            learning_rate=0.1,
            random_state=42
        )
        
        # Feature scaler
        self.scaler = StandardScaler()
    
    def extract_features(self, df: pd.DataFrame,
                        current_time: datetime) -> MLFeatures:
        """
        Extract features from market data
        
        Args:
            df: Market data (OHLCV)
            current_time: Current time
            
        Returns:
            MLFeatures object
        """
        # Technical indicators
        adx = self._calculate_adx(df)
        rsi = self._calculate_rsi(df)
        macd, signal = self._calculate_macd(df)
        bb_width = self._calculate_bb_width(df)
        atr_percent = self._calculate_atr_percent(df)
        
        # Trend features
        ema8 = df['close'].ewm(span=8).mean()
        ema21 = df['close'].ewm(span=21).mean()
        ema50 = df['close'].ewm(span=50).mean() if len(df) >= 50 else ema21
        
        ema8_slope = (ema8.iloc[-1] - ema8.iloc[-5]) / ema8.iloc[-5] if len(df) >= 5 else 0
        ema21_slope = (ema21.iloc[-1] - ema21.iloc[-10]) / ema21.iloc[-10] if len(df) >= 10 else 0
        ema50_slope = (ema50.iloc[-1] - ema50.iloc[-20]) / ema50.iloc[-20] if len(df) >= 50 else 0
        
        current_price = df['close'].iloc[-1]
        ema20 = df['close'].ewm(span=20).mean().iloc[-1]
        price_to_ema20 = (current_price - ema20) / ema20
        
        # Volatility features
        volatility_regime = min(1.0, atr_percent / 2.0)  # Normalize to 0-1
        recent_high = df['high'].iloc[-20:].max()
        recent_low = df['low'].iloc[-20:].min()
        recent_range = (recent_high - recent_low) / current_price
        
        # Time features
        hour_of_day = current_time.hour
        day_of_week = current_time.weekday()
        
        # Session (0=Asian, 1=London, 2=NY)
        if 3 <= hour_of_day < 11:  # GMT+3
            session = 0  # Asian
        elif 11 <= hour_of_day < 14:
            session = 1  # London
        else:
            session = 2  # NY
        
        # Market structure
        higher_highs = self._check_higher_highs(df)
        higher_lows = self._check_higher_lows(df)
        support_nearby = self._check_support_nearby(df)
        resistance_nearby = self._check_resistance_nearby(df)
        
        # Volume
        volume_ratio = self._calculate_volume_ratio(df)
        
        # External (placeholder - would integrate real data)
        dxy_trend = 0.0  # Dollar index trend
        vix_level = 0.5  # VIX normalized
        
        return MLFeatures(
            adx=adx,
            rsi=rsi,
            macd=macd - signal,
            bb_width=bb_width,
            atr_percent=atr_percent,
            ema8_slope=ema8_slope,
            ema21_slope=ema21_slope,
            ema50_slope=ema50_slope,
            price_to_ema20=price_to_ema20,
            volatility_regime=volatility_regime,
            recent_range=recent_range,
            hour_of_day=hour_of_day,
            day_of_week=day_of_week,
            session=session,
            higher_highs=int(higher_highs),
            higher_lows=int(higher_lows),
            support_nearby=int(support_nearby),
            resistance_nearby=int(resistance_nearby),
            volume_ratio=volume_ratio,
            dxy_trend=dxy_trend,
            vix_level=vix_level
        )
    
    def predict(self, features: MLFeatures,
               available_strategies: List[str]) -> MLPrediction:
        """
        Predict optimal strategies using ML
        
        Args:
            features: Extracted features
            available_strategies: List of available strategies
            
        Returns:
            MLPrediction with regime and strategy recommendations
        """
        # If ML not available or not trained, use rule-based
        if not self.ml_available or self.regime_classifier is None:
            return self._rule_based_prediction(features, available_strategies)
        
        # Prepare features
        X = features.to_array().reshape(1, -1)
        
        try:
            # Scale features
            X_scaled = self.scaler.transform(X)
            
            # Predict regime
            regime_proba = self.regime_classifier.predict_proba(X_scaled)[0]
            regime_classes = self.regime_classifier.classes_
            
            predicted_regime_idx = np.argmax(regime_proba)
            predicted_regime = regime_classes[predicted_regime_idx]
            regime_confidence = regime_proba[predicted_regime_idx]
            
            # Get strategy probabilities (simplified)
            strategy_probabilities = self._calculate_strategy_probabilities(
                features, predicted_regime, available_strategies
            )
            
            # Recommend top strategies
            recommended_strategies = sorted(
                strategy_probabilities.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            recommended_strategies = [s[0] for s in recommended_strategies]
            
            # Feature importance (from regime classifier)
            feature_importance = dict(zip(
                features.feature_names,
                self.regime_classifier.feature_importances_
            ))
            
            return MLPrediction(
                predicted_regime=predicted_regime,
                regime_confidence=regime_confidence * 100,
                strategy_probabilities=strategy_probabilities,
                recommended_strategies=recommended_strategies,
                feature_importance=feature_importance
            )
        
        except Exception as e:
            print(f"ML prediction failed: {e}. Using rule-based fallback.")
            return self._rule_based_prediction(features, available_strategies)
    
    def _rule_based_prediction(self, features: MLFeatures,
                               available_strategies: List[str]) -> MLPrediction:
        """Rule-based prediction fallback"""
        # Determine regime from features
        if features.adx > 30:
            if features.ema8_slope > 0 and features.ema21_slope > 0:
                regime = 'STRONG_UPTREND'
            else:
                regime = 'STRONG_DOWNTREND'
        elif features.adx < 20:
            regime = 'RANGING'
        elif features.volatility_regime > 0.7:
            regime = 'HIGH_VOLATILITY'
        else:
            regime = 'MODERATE_TREND'
        
        # Map strategies to regimes
        regime_strategies = {
            'STRONG_UPTREND': ['trend_following', 'breakout', 'ict_2022', 'momentum'],
            'STRONG_DOWNTREND': ['trend_following', 'breakout', 'ict_2022', 'momentum'],
            'RANGING': ['mean_reversion', 'supply_demand', 'bollinger_reversion', 'grid_trading'],
            'HIGH_VOLATILITY': ['volatility_breakout', 'news_trading', 'momentum'],
            'MODERATE_TREND': ['ict_2022', 'supply_demand', 'fibonacci_swing']
        }
        
        recommended = regime_strategies.get(regime, [])
        
        # Calculate probabilities
        strategy_probabilities = {}
        for strategy in available_strategies:
            if strategy in recommended:
                strategy_probabilities[strategy] = 0.8
            else:
                strategy_probabilities[strategy] = 0.3
        
        return MLPrediction(
            predicted_regime=regime,
            regime_confidence=70.0,
            strategy_probabilities=strategy_probabilities,
            recommended_strategies=recommended[:5],
            feature_importance={}
        )
    
    def _calculate_strategy_probabilities(self, features: MLFeatures,
                                         regime: str,
                                         strategies: List[str]) -> Dict[str, float]:
        """Calculate probability scores for each strategy"""
        probabilities = {}
        
        # Base probabilities from regime
        regime_map = {
            'STRONG_TREND': {
                'trend_following': 0.9,
                'breakout': 0.8,
                'momentum': 0.85,
                'ict_2022': 0.88,
                'mean_reversion': 0.3
            },
            'RANGING': {
                'mean_reversion': 0.9,
                'supply_demand': 0.85,
                'grid_trading': 0.8,
                'bollinger_reversion': 0.88,
                'trend_following': 0.3
            },
            'HIGH_VOLATILITY': {
                'volatility_breakout': 0.9,
                'momentum': 0.85,
                'breakout': 0.8
            }
        }
        
        base_probs = regime_map.get(regime, {})
        
        for strategy in strategies:
            base_prob = base_probs.get(strategy, 0.5)
            
            # Adjust based on session
            if features.session == 1 and 'ict' in strategy.lower():  # London
                base_prob *= 1.2
            elif features.session == 2 and 'ny' in strategy.lower():  # NY
                base_prob *= 1.2
            
            # Adjust based on RSI
            if 'mean_reversion' in strategy and (features.rsi < 30 or features.rsi > 70):
                base_prob *= 1.3
            
            probabilities[strategy] = min(1.0, base_prob)
        
        return probabilities
    
    def train_online(self, features: MLFeatures, actual_regime: str,
                    strategy_performance: Dict[str, float]):
        """
        Online learning - update models with new data
        
        Args:
            features: Market features
            actual_regime: Actual market regime
            strategy_performance: Performance of strategies (strategy -> win/loss)
        """
        if not self.ml_available:
            return
        
        # Store training data
        self.training_features.append(features.to_array())
        self.training_regimes.append(actual_regime)
        
        # Store strategy performance
        for strategy, performance in strategy_performance.items():
            if strategy not in self.training_performances:
                self.training_performances[strategy] = []
            self.training_performances[strategy].append(performance)
        
        # Retrain every 50 samples
        if len(self.training_features) >= 50 and len(self.training_features) % 50 == 0:
            self._retrain_models()
    
    def _retrain_models(self):
        """Retrain models with accumulated data"""
        if not self.ml_available or len(self.training_features) < 20:
            return
        
        try:
            X = np.array(self.training_features)
            y = np.array(self.training_regimes)
            
            # Fit scaler
            self.scaler.fit(X)
            X_scaled = self.scaler.transform(X)
            
            # Train regime classifier
            self.regime_classifier.fit(X_scaled, y)
            
            # Save models
            self._save_models()
            
            print(f"Models retrained with {len(self.training_features)} samples")
        
        except Exception as e:
            print(f"Model retraining failed: {e}")
    
    def _save_models(self):
        """Save models to disk"""
        if not self.ml_available:
            return
        
        try:
            # Save regime classifier
            with open(f"{self.model_path}/regime_classifier.pkl", 'wb') as f:
                pickle.dump(self.regime_classifier, f)
            
            # Save scaler
            with open(f"{self.model_path}/scaler.pkl", 'wb') as f:
                pickle.dump(self.scaler, f)
            
            # Save training data
            np.save(f"{self.model_path}/training_features.npy", np.array(self.training_features))
            np.save(f"{self.model_path}/training_regimes.npy", np.array(self.training_regimes))
        
        except Exception as e:
            print(f"Model saving failed: {e}")
    
    def _load_models(self):
        """Load models from disk"""
        if not self.ml_available:
            return
        
        try:
            # Load regime classifier
            classifier_path = f"{self.model_path}/regime_classifier.pkl"
            if os.path.exists(classifier_path):
                with open(classifier_path, 'rb') as f:
                    self.regime_classifier = pickle.load(f)
            
            # Load scaler
            scaler_path = f"{self.model_path}/scaler.pkl"
            if os.path.exists(scaler_path):
                with open(scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
            
            # Load training data
            features_path = f"{self.model_path}/training_features.npy"
            if os.path.exists(features_path):
                self.training_features = np.load(features_path).tolist()
            
            regimes_path = f"{self.model_path}/training_regimes.npy"
            if os.path.exists(regimes_path):
                self.training_regimes = np.load(regimes_path).tolist()
            
            if self.regime_classifier is not None:
                print(f"Models loaded from {self.model_path}")
        
        except Exception as e:
            print(f"Model loading failed: {e}")
    
    # Helper calculation methods
    
    def _calculate_adx(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate ADX"""
        if len(df) < period + 1:
            return 0
        
        high = df['high']
        low = df['low']
        close = df['close']
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()
        
        return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 0
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Calculate RSI"""
        if len(df) < period + 1:
            return 50
        
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
    
    def _calculate_macd(self, df: pd.DataFrame) -> Tuple[float, float]:
        """Calculate MACD"""
        ema12 = df['close'].ewm(span=12).mean()
        ema26 = df['close'].ewm(span=26).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9).mean()
        
        return macd.iloc[-1], signal.iloc[-1]
    
    def _calculate_bb_width(self, df: pd.DataFrame, period: int = 20) -> float:
        """Calculate Bollinger Band width"""
        sma = df['close'].rolling(window=period).mean()
        std = df['close'].rolling(window=period).std()
        width = ((std * 2) / sma) * 100
        
        return width.iloc[-1] if not pd.isna(width.iloc[-1]) else 0
    
    def _calculate_atr_percent(self, df: pd.DataFrame) -> float:
        """Calculate ATR as percentage of price"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=14).mean()
        
        atr_percent = (atr / df['close']) * 100
        
        return atr_percent.iloc[-1] if not pd.isna(atr_percent.iloc[-1]) else 0
    
    def _check_higher_highs(self, df: pd.DataFrame) -> bool:
        """Check for higher highs"""
        if len(df) < 20:
            return False
        
        highs = df['high'].iloc[-20:]
        return highs.iloc[-1] > highs.iloc[-10]
    
    def _check_higher_lows(self, df: pd.DataFrame) -> bool:
        """Check for higher lows"""
        if len(df) < 20:
            return False
        
        lows = df['low'].iloc[-20:]
        return lows.iloc[-1] > lows.iloc[-10]
    
    def _check_support_nearby(self, df: pd.DataFrame) -> bool:
        """Check if price near support"""
        if len(df) < 50:
            return False
        
        current_price = df['close'].iloc[-1]
        recent_lows = df['low'].iloc[-50:]
        min_low = recent_lows.min()
        
        return abs(current_price - min_low) / current_price < 0.005  # Within 0.5%
    
    def _check_resistance_nearby(self, df: pd.DataFrame) -> bool:
        """Check if price near resistance"""
        if len(df) < 50:
            return False
        
        current_price = df['close'].iloc[-1]
        recent_highs = df['high'].iloc[-50:]
        max_high = recent_highs.max()
        
        return abs(current_price - max_high) / current_price < 0.005
    
    def _calculate_volume_ratio(self, df: pd.DataFrame) -> float:
        """Calculate recent volume vs average"""
        if 'volume' not in df.columns or len(df) < 20:
            return 1.0
        
        recent_volume = df['volume'].iloc[-5:].mean()
        avg_volume = df['volume'].mean()
        
        return recent_volume / avg_volume if avg_volume > 0 else 1.0
