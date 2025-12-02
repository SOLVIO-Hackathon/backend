"""
Bin Fill Prediction Router

Provides time series forecasting API for predicting bin fill-up time.
"""

from fastapi import APIRouter, HTTPException, status
import logging
from typing import List

from app.schemas.bin_prediction import (
    PredictionRequest,
    PredictionResponse,
    BatchPredictionResponse,
    ModelInfoResponse
)
from app.services.bin_prediction_service import get_bin_prediction_service

router = APIRouter(prefix="/bin-prediction", tags=["Bin Fill Prediction"])
logger = logging.getLogger("router.bin_prediction")


@router.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    """
    Predict time until bin is full
    
    Requires minimum 12 hours of historical data.
    Returns predicted hours until bin is full, current fill level,
    predicted full datetime, and confidence level.
    """
    try:
        service = get_bin_prediction_service()
        data = [item.dict() for item in request.data]
        result = service.predict(data)
        return PredictionResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.exception(f"Bin prediction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction error: {str(e)}"
        )


@router.post("/predict/batch", response_model=BatchPredictionResponse)
async def predict_batch(requests: List[PredictionRequest]):
    """
    Batch prediction for multiple bin sequences
    
    Processes multiple prediction requests in a single call.
    Returns list of predictions with success/error status for each.
    """
    try:
        service = get_bin_prediction_service()
        request_data = [{"data": [item.dict() for item in req.data]} for req in requests]
        result = service.predict_batch(request_data)
        return BatchPredictionResponse(**result)
        
    except Exception as e:
        logger.exception(f"Batch prediction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch prediction error: {str(e)}"
        )


@router.get("/model/info", response_model=ModelInfoResponse)
async def model_info():
    """
    Get model information
    
    Returns model type, lookback hours, features, hyperparameters,
    version, and training date.
    """
    try:
        service = get_bin_prediction_service()
        info = service.get_model_info()
        return ModelInfoResponse(**info)
        
    except Exception as e:
        logger.exception(f"Failed to get model info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get model info: {str(e)}"
        )

