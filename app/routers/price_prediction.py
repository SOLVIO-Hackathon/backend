"""
E-Waste Price Prediction Router
"""

from fastapi import APIRouter, HTTPException
import pandas as pd
import logging

from app.schemas.price_prediction import (
    EWasteInput,
    PredictionResponse,
    BatchInput,
    BatchResponse
)
from app.services.price_prediction_service import get_predictor

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/price-prediction",
    tags=["E-Waste Price Prediction"]
)


@router.post("/predict", response_model=PredictionResponse)
async def predict_price(item: EWasteInput):
    """
    Predict the resale price for a single e-waste item
    
    This endpoint uses an ensemble of LightGBM models trained on historical e-waste data
    to estimate the current resale value based on product characteristics and condition.
    """
    try:
        predictor = get_predictor()
        
        # Convert input to DataFrame with column names matching training data
        df = pd.DataFrame([{
            'Product_Type': item.product_type,
            'Brand': item.brand,
            'Build_Quality': item.build_quality,
            'User_Lifespan': item.user_lifespan,
            'Usage_Pattern': item.usage_pattern,
            'Expiry_Years': item.expiry_years,
            'Condition': item.condition,
            'Original_Price': item.original_price,
            'Used_Duration': item.used_duration,
        }])
        
        # Get prediction
        prices = predictor.predict(df)
        predicted_price = round(prices[0], 2)
        
        logger.info(f"Predicted price for {item.product_type} ({item.brand}): ${predicted_price}")
        
        return PredictionResponse(predicted_price=predicted_price)
        
    except Exception as e:
        logger.error(f"Error in price prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/batch", response_model=BatchResponse)
async def predict_batch(batch: BatchInput):
    """
    Predict resale prices for multiple e-waste items in a single request
    
    This endpoint processes multiple items efficiently in batch mode.
    Useful for estimating prices for a collection of items or comparison purposes.
    """
    try:
        predictor = get_predictor()
        
        # Convert all items to DataFrame
        data = [{
            'Product_Type': item.product_type,
            'Brand': item.brand,
            'Build_Quality': item.build_quality,
            'User_Lifespan': item.user_lifespan,
            'Usage_Pattern': item.usage_pattern,
            'Expiry_Years': item.expiry_years,
            'Condition': item.condition,
            'Original_Price': item.original_price,
            'Used_Duration': item.used_duration,
        } for item in batch.items]
        
        df = pd.DataFrame(data)
        
        # Get predictions
        prices = predictor.predict(df)
        rounded_prices = [round(p, 2) for p in prices]
        
        logger.info(f"Predicted prices for {len(batch.items)} items")
        
        return BatchResponse(predictions=rounded_prices)
        
    except Exception as e:
        logger.error(f"Error in batch prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")


@router.get("/health")
async def health_check():
    """
    Check if the price prediction service is healthy and models are loaded
    """
    try:
        predictor = get_predictor()
        return {
            "status": "healthy",
            "models_loaded": predictor.models_loaded,
            "num_models": len(predictor.models),
            "num_features": len(predictor.feature_names)
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

