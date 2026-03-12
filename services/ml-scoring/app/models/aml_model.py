"""
AML Ensemble Model – XGBoost + Random Forest with synthetic training data.
In production: replace synthetic data with labeled SAR/non-SAR records.
"""
import logging
import os
from typing import Dict, Any, Optional, Tuple, List

import numpy as np
import joblib

logger = logging.getLogger(__name__)

MODEL_PATH = os.path.join(os.path.dirname(__file__), "saved", "aml_model.joblib")
MODEL_VERSION = "AML_GB_v4.1"

FEATURE_NAMES = [
    "transaction_volume_log",
    "cross_border_ratio",
    "cash_ratio",
    "network_degree",
    "pep_flag",
    "country_risk_score",
    "industry_risk_score",
    "adverse_media_score",
    "transaction_count",
    "distance_to_sanctioned",
    "network_cluster_size",
]


class AMLEnsembleModel:
    """
    XGBoost + Random Forest ensemble for AML suspicious activity detection.
    Trains on synthetic data if no pre-trained model exists.
    """

    def __init__(self):
        self.version = MODEL_VERSION
        self.feature_names = FEATURE_NAMES
        self._xgb_model = None
        self._rf_model = None
        self._xgb_available = False

    def load_or_train(self):
        """Load saved model or train a new one."""
        if os.path.exists(MODEL_PATH):
            try:
                saved = joblib.load(MODEL_PATH)
                self._xgb_model = saved.get("xgb")
                self._rf_model = saved.get("rf")
                self._xgb_available = self._xgb_model is not None
                logger.info(f"Loaded AML model from {MODEL_PATH}")
                return
            except Exception as e:
                logger.warning(f"Failed to load model: {e}. Retraining...")

        self._train()

    def _train(self):
        """Train ensemble on synthetic AML data."""
        logger.info("Training AML ensemble model on synthetic data...")
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.preprocessing import StandardScaler

        np.random.seed(42)
        n_samples = 5000
        n_suspicious = int(n_samples * 0.15)  # 15% suspicious rate (realistic)

        # Generate synthetic feature data
        X_legit = np.column_stack([
            np.random.lognormal(12, 2, n_samples - n_suspicious),    # transaction_volume
            np.random.beta(2, 5, n_samples - n_suspicious),           # cross_border_ratio
            np.random.beta(1, 10, n_samples - n_suspicious),          # cash_ratio
            np.random.poisson(3, n_samples - n_suspicious),            # network_degree
            np.random.binomial(1, 0.05, n_samples - n_suspicious),    # pep_flag
            np.random.uniform(10, 40, n_samples - n_suspicious),      # country_risk
            np.random.uniform(10, 35, n_samples - n_suspicious),      # industry_risk
            np.random.uniform(0, 20, n_samples - n_suspicious),       # adverse_media
            np.random.poisson(20, n_samples - n_suspicious),           # transaction_count
            np.random.randint(3, 10, n_samples - n_suspicious),       # distance_to_sanctioned
            np.random.poisson(3, n_samples - n_suspicious),            # cluster_size
        ])

        X_suspicious = np.column_stack([
            np.random.lognormal(15, 2, n_suspicious),                  # high volume
            np.random.beta(5, 2, n_suspicious),                        # high cross-border
            np.random.beta(3, 3, n_suspicious),                        # high cash
            np.random.poisson(15, n_suspicious),                       # large network
            np.random.binomial(1, 0.35, n_suspicious),                 # high PEP rate
            np.random.uniform(50, 95, n_suspicious),                   # high country risk
            np.random.uniform(50, 90, n_suspicious),                   # high industry risk
            np.random.uniform(40, 90, n_suspicious),                   # high adverse media
            np.random.poisson(80, n_suspicious),                       # high tx count
            np.random.randint(1, 3, n_suspicious),                     # close to sanctioned
            np.random.poisson(20, n_suspicious),                       # large cluster
        ])

        X = np.vstack([X_legit, X_suspicious])
        # Log-transform volume
        X[:, 0] = np.log1p(X[:, 0])
        y = np.array([0] * (n_samples - n_suspicious) + [1] * n_suspicious)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Train Random Forest
        self._rf_model = RandomForestClassifier(
            n_estimators=200, max_depth=8, min_samples_leaf=5, random_state=42, n_jobs=-1
        )
        self._rf_model.fit(X_train, y_train)
        rf_score = self._rf_model.score(X_test, y_test)
        logger.info(f"Random Forest accuracy: {rf_score:.3f}")

        # Try XGBoost
        try:
            import xgboost as xgb
            self._xgb_model = xgb.XGBClassifier(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                subsample=0.8, colsample_bytree=0.8,
                use_label_encoder=False, eval_metric="logloss", random_state=42,
            )
            self._xgb_model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)
            xgb_score = self._xgb_model.score(X_test, y_test)
            self._xgb_available = True
            logger.info(f"XGBoost accuracy: {xgb_score:.3f}")
        except ImportError:
            logger.warning("XGBoost not available, using Random Forest only")
            self._xgb_available = False

        # Save model
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump({"xgb": self._xgb_model, "rf": self._rf_model}, MODEL_PATH)
        logger.info(f"Model saved to {MODEL_PATH}")

    def _extract_features(self, data: Dict[str, Any]) -> np.ndarray:
        """Convert feature dict to numpy array matching training schema."""
        volume = data.get("transaction_volume", 0)
        features = [
            np.log1p(float(volume)),
            float(data.get("cross_border_ratio", 0)),
            float(data.get("cash_ratio", 0)),
            float(data.get("network_degree", 0)),
            float(data.get("pep_flag", 0)),
            float(data.get("country_risk_score", 0)),
            float(data.get("industry_risk_score", 0)),
            float(data.get("adverse_media_score", 0)),
            float(data.get("transaction_count", 0)),
            float(data.get("distance_to_sanctioned") or 5),
            float(data.get("network_cluster_size", 0)),
        ]
        return np.array(features).reshape(1, -1)

    def predict(self, feature_data: Dict[str, Any]) -> Tuple[float, Optional[Dict[str, float]]]:
        """
        Returns (probability_suspicious, feature_importances_dict).
        Ensemble: weighted average of XGBoost (0.6) + RF (0.4).
        """
        X = self._extract_features(feature_data)

        rf_prob = self._rf_model.predict_proba(X)[0][1]

        if self._xgb_available and self._xgb_model is not None:
            xgb_prob = self._xgb_model.predict_proba(X)[0][1]
            ensemble_prob = (xgb_prob * 0.6) + (rf_prob * 0.4)
        else:
            ensemble_prob = rf_prob

        # Feature importances from RF
        importances = {}
        if self._rf_model is not None and hasattr(self._rf_model, "feature_importances_"):
            for name, imp in zip(self.feature_names, self._rf_model.feature_importances_):
                importances[name] = round(float(imp), 4)

        return float(np.clip(ensemble_prob, 0.0, 1.0)), importances
