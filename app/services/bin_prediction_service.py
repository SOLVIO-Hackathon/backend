"""
Bin Fill Prediction Service
"""

import os
import logging
import warnings
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
import tensorflow as tf
from tensorflow import keras

logger = logging.getLogger(__name__)

# Suppress scikit-learn version mismatch warnings when loading pickled models
# This is safe for minor version differences (1.6.1 -> 1.7.2)
warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')


class BinPredictionService:
    """
    Bin fill prediction service using LSTM model
    """

    def __init__(self):
        self.model = None
        self.scaler_X = None
        self.scaler_y = None
        self.le_traffic = None
        self.best_params = None
        self.LOOKBACK = None
        self.model_loaded = False

    def load_model(self):
        """Load the LSTM model and preprocessing artifacts"""
        try:
            # Get the base directory (backend folder)
            base_dir = Path(__file__).parent.parent.parent
            model_dir = base_dir / "LSTM Bin fill level prediction"

            logger.info(f"Loading bin prediction model from: {model_dir}")

            if not model_dir.exists():
                raise FileNotFoundError(f"Model directory not found: {model_dir}")

            # Fix for Keras compatibility issue
            from tensorflow.keras import losses, metrics
            
            # Custom objects mapping for older Keras models
            custom_objects = {
                'mse': losses.MeanSquaredError(),
                'mae': metrics.MeanAbsoluteError()
            }
            
            # Load model with custom objects
            model_path = model_dir / 'bin_prediction_lstm_optuna.h5'
            if not model_path.exists():
                raise FileNotFoundError(f"Model file not found: {model_path}")
            
            self.model = keras.models.load_model(
                str(model_path),
                custom_objects=custom_objects,
                compile=False  # Don't compile during load
            )
            
            # Recompile the model
            self.model.compile(
                optimizer=keras.optimizers.Adam(learning_rate=0.001),
                loss='mse',
                metrics=['mae']
            )
            
            # Load scalers and encoders
            # Suppress version warnings for pickle loading (models were trained with sklearn 1.6.1)
            with warnings.catch_warnings():
                warnings.filterwarnings('ignore', category=UserWarning, module='sklearn')
                self.scaler_X = joblib.load(model_dir / 'scaler_X_optuna.pkl')
                self.scaler_y = joblib.load(model_dir / 'scaler_y_optuna.pkl')
                self.le_traffic = joblib.load(model_dir / 'label_encoder_traffic_optuna.pkl')
                self.best_params = joblib.load(model_dir / 'best_params_optuna.pkl')
            
            self.LOOKBACK = self.best_params.get('lookback', 12)
            
            logger.info(f"Successfully loaded bin prediction model (lookback: {self.LOOKBACK} hours)")
            self.model_loaded = True

        except Exception as e:
            logger.error(f"Error loading bin prediction model: {str(e)}")
            raise

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply feature engineering to input dataframe"""
        df = df.copy()
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Cyclical features
        df['hour_sin'] = np.sin(2 * np.pi * df['hour'] / 24)
        df['hour_cos'] = np.cos(2 * np.pi * df['hour'] / 24)
        
        df['day_of_week_num'] = df['timestamp'].dt.dayofweek
        df['day_sin'] = np.sin(2 * np.pi * df['day_of_week_num'] / 7)
        df['day_cos'] = np.cos(2 * np.pi * df['day_of_week_num'] / 7)
        
        # Encode traffic level
        df['foot_traffic_level_encoded'] = self.le_traffic.transform(df['foot_traffic_level'])
        
        # Convert boolean to int
        df['is_weekend'] = df['is_weekend'].astype(int)
        df['is_holiday'] = df['is_holiday'].astype(int)
        
        return df

    def prepare_input_sequence(self, df: pd.DataFrame, lookback: int) -> np.ndarray:
        """Prepare input sequence for model prediction"""
        feature_columns = [
            'hour', 'hour_sin', 'hour_cos',
            'day_of_week_num', 'day_sin', 'day_cos',
            'is_weekend', 'is_holiday',
            'temperature_c', 'precipitation_mm',
            'foot_traffic_level_encoded',
            'dustbin_capacity_liters', 'fill_rate_per_hour',
            'current_fill_level_percent'
        ]
        
        # Engineer features
        df = self.engineer_features(df)
        
        # Take last 'lookback' hours
        if len(df) > lookback:
            df = df.iloc[-lookback:]
        
        # Extract features
        X = df[feature_columns].values
        
        # Scale features
        X_scaled = self.scaler_X.transform(X)
        
        # Reshape for LSTM: (1, lookback, n_features)
        X_seq = X_scaled.reshape(1, lookback, -1)
        
        return X_seq

    def predict(self, data: list) -> dict:
        """
        Predict time until bin is full
        
        Args:
            data: List of BinDataPoint dictionaries
            
        Returns:
            Dictionary with prediction results
        """
        if not self.model_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if len(data) < self.LOOKBACK:
            raise ValueError(f"Minimum {self.LOOKBACK} hours of historical data required")

        df = pd.DataFrame(data)
        X_seq = self.prepare_input_sequence(df, self.LOOKBACK)
        
        # Make prediction
        prediction_scaled = self.model.predict(X_seq, verbose=0)
        prediction = self.scaler_y.inverse_transform(prediction_scaled)[0][0]
        
        current_fill = data[-1]['current_fill_level_percent']
        last_timestamp = pd.to_datetime(data[-1]['timestamp'])
        predicted_full_datetime = last_timestamp + pd.Timedelta(hours=float(prediction))
        
        # SMART CONFIDENCE CALCULATION
        MODEL_MAE = self.best_params.get('best_mae', 30.16)
        relative_error = (MODEL_MAE / max(prediction, 1)) * 100
        
        # Error-based confidence
        if relative_error < 20:
            error_conf = 1.0
        elif relative_error < 40:
            error_conf = 0.7
        else:
            error_conf = 0.4
        
        # Fill level confidence
        if current_fill > 70:
            fill_conf = 1.0
        elif current_fill > 40:
            fill_conf = 0.8
        elif current_fill > 20:
            fill_conf = 0.6
        else:
            fill_conf = 0.4
        
        # Time confidence
        if prediction < 48:
            time_conf = 1.0
        elif prediction < 120:
            time_conf = 0.8
        elif prediction < 240:
            time_conf = 0.6
        else:
            time_conf = 0.3
        
        # Combined score
        confidence_score = (error_conf * 0.4 + fill_conf * 0.3 + time_conf * 0.3)
        
        if confidence_score >= 0.7:
            confidence = "High"
        elif confidence_score >= 0.5:
            confidence = "Medium"
        else:
            confidence = "Low"
        
        # Add detailed info
        confidence_detail = f"{confidence} (score: {confidence_score:.2f})"
        
        return {
            "predicted_time_to_full_hours": round(float(prediction), 2),
            "current_fill_level_percent": round(current_fill, 2),
            "predicted_full_datetime": predicted_full_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "confidence": confidence_detail,
            "model_version": "1.0.0"
        }

    def predict_batch(self, requests: list) -> dict:
        """
        Batch prediction for multiple bin sequences
        
        Args:
            requests: List of prediction requests (each with data field)
            
        Returns:
            Dictionary with batch results
        """
        if not self.model_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        results = []
        
        for idx, request in enumerate(requests):
            try:
                # Convert to DataFrame
                df = pd.DataFrame(request['data'])
                
                # Prepare input sequence
                X_seq = self.prepare_input_sequence(df, self.LOOKBACK)
                
                # Make prediction
                prediction_scaled = self.model.predict(X_seq, verbose=0)
                prediction = self.scaler_y.inverse_transform(prediction_scaled)[0][0]
                
                # Get current fill level
                current_fill = request['data'][-1]['current_fill_level_percent']
                
                # Calculate predicted full datetime
                last_timestamp = pd.to_datetime(request['data'][-1]['timestamp'])
                predicted_full_datetime = last_timestamp + pd.Timedelta(hours=float(prediction))
                
                results.append({
                    "index": idx,
                    "predicted_time_to_full_hours": round(float(prediction), 2),
                    "current_fill_level_percent": round(current_fill, 2),
                    "predicted_full_datetime": predicted_full_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                    "confidence": "High" if 0 < prediction < 200 else "Medium",
                    "status": "success"
                })
                
            except Exception as e:
                results.append({
                    "index": idx,
                    "status": "error",
                    "error": str(e)
                })
        
        return {
            "results": results,
            "total": len(requests),
            "successful": sum(1 for r in results if r.get("status") == "success")
        }

    def get_model_info(self) -> dict:
        """Get model information"""
        if not self.model_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        return {
            "model_type": "LSTM",
            "lookback_hours": self.LOOKBACK,
            "features": [
                "hour", "hour_sin", "hour_cos",
                "day_of_week_num", "day_sin", "day_cos",
                "is_weekend", "is_holiday",
                "temperature_c", "precipitation_mm",
                "foot_traffic_level_encoded",
                "dustbin_capacity_liters", "fill_rate_per_hour",
                "current_fill_level_percent"
            ],
            "hyperparameters": self.best_params,
            "version": "1.0.0",
            "trained_date": "2025-11-11"
        }


# Global service instance
service: BinPredictionService = None


def get_bin_prediction_service() -> BinPredictionService:
    """Get the global bin prediction service instance"""
    global service
    if service is None:
        service = BinPredictionService()
    
    # Ensure model is loaded (retry if previous load failed)
    if not service.model_loaded:
        try:
            service.load_model()
        except Exception as e:
            logger.error(f"Failed to load bin prediction model: {e}")
            raise
    
    return service

