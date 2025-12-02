"""
E-Waste Price Prediction Service
"""

import os
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
import joblib
from typing import List

logger = logging.getLogger(__name__)


class EWastePricePredictor:
    """
    E-Waste price prediction service using ensemble of LightGBM models
    """

    def __init__(self):
        self.models: List[lgb.Booster] = []
        self.feature_names: List[str] = []
        self.categorical_features: List[str] = []
        self.models_loaded = False

    def load_models(self):
        """Load all LightGBM models and artifacts"""
        try:
            # Get the base directory (backend folder)
            base_dir = Path(__file__).parent.parent.parent
            models_dir = base_dir / "E-waste  Price models"

            # Load artifacts (feature names and categorical features)
            artifacts_path = models_dir / "e-waste_price_model_artifacts.pkl"
            logger.info(f"Loading artifacts from: {artifacts_path}")

            if not artifacts_path.exists():
                raise FileNotFoundError(f"Artifacts file not found: {artifacts_path}")

            artifacts = joblib.load(artifacts_path)
            self.feature_names = artifacts['feature_names']
            self.categorical_features = artifacts['categorical_features']

            logger.info(f"Loaded {len(self.feature_names)} feature names")
            logger.info(f"Loaded {len(self.categorical_features)} categorical features")

            # Load all fold models (0-4)
            self.models = []
            for fold in range(5):
                model_path = models_dir / f"e-waste_price_lgb_model_fold_{fold}.txt"
                logger.info(f"Loading model from: {model_path}")

                if not model_path.exists():
                    raise FileNotFoundError(f"Model file not found: {model_path}")

                model = lgb.Booster(model_file=str(model_path))
                self.models.append(model)

            logger.info(f"Successfully loaded {len(self.models)} LightGBM models")
            self.models_loaded = True

        except Exception as e:
            logger.error(f"Error loading models: {str(e)}")
            raise

    def create_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Create engineered features from raw input data
        Must match the feature engineering used during training
        """
        df = df.copy()

        # Age and lifetime ratios
        df['age_ratio'] = df['Used_Duration'] / (df['User_Lifespan'] + 1e-9)
        df['remaining_life'] = (df['User_Lifespan'] - df['Used_Duration']).clip(lower=0)
        df['remaining_life_ratio'] = df['remaining_life'] / (df['User_Lifespan'] + 1e-9)

        # Price-based features
        df['price_per_year'] = df['Original_Price'] / (df['Expiry_Years'] + 1e-9)
        df['depreciation_rate'] = (df['Original_Price'] - 0) / (df['Used_Duration'] + 1e-9)
        df['price_retention_ratio'] = 0 / (df['Original_Price'] + 1e-9)

        # Log transforms
        df['log_original_price'] = np.log1p(df['Original_Price'])

        # Interaction features
        df['quality_condition'] = df['Build_Quality'] * df['Condition']
        df['quality_lifespan'] = df['Build_Quality'] * df['User_Lifespan']

        # Polynomial features
        df['used_duration_squared'] = df['Used_Duration'] ** 2

        # Near expiry flag
        df['near_expiry'] = (df['remaining_life'] < 2).astype(int)

        return df

    def predict(self, input_data: pd.DataFrame) -> List[float]:
        """
        Make price predictions for input data
        
        Args:
            input_data: DataFrame with columns matching training data format
            
        Returns:
            List of predicted prices
        """
        if not self.models_loaded:
            raise RuntimeError("Models not loaded. Call load_models() first.")

        try:
            # Apply feature engineering
            input_data = self.create_features(input_data)

            # Select only the features used in training
            X = input_data[self.feature_names].copy()

            # Convert categorical features to proper type
            for col in self.categorical_features:
                if col in X.columns:
                    X[col] = X[col].astype('category')

            # Predict with all models (predictions are in log scale)
            predictions_log = np.zeros((len(X), len(self.models)))
            for i, model in enumerate(self.models):
                predictions_log[:, i] = model.predict(X)

            # Average predictions across folds (still in log scale)
            avg_predictions_log = predictions_log.mean(axis=1)

            # Convert back to original scale
            predictions = np.expm1(avg_predictions_log)

            return predictions.tolist()

        except Exception as e:
            logger.error(f"Error during prediction: {str(e)}")
            raise


# Global predictor instance
predictor: EWastePricePredictor = None


def get_predictor() -> EWastePricePredictor:
    """Get the global predictor instance"""
    global predictor
    if predictor is None:
        predictor = EWastePricePredictor()
        predictor.load_models()
    return predictor

