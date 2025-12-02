"""
E-Waste Price Prediction Router
"""

from fastapi import APIRouter, HTTPException
import pandas as pd
import logging
import httpx

HF_SPACE_BASE_URL = "https://eyasir2047-e-waste-price-estimation.hf.space"
HF_PREDICT_ENDPOINT = f"{HF_SPACE_BASE_URL}/predict"
HF_HEALTH_ENDPOINT = f"{HF_SPACE_BASE_URL}/"

from app.schemas.price_prediction import (
    EWasteInput,
    PredictionResponse,
    BatchInput,
    BatchResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/price-prediction",
    tags=["E-Waste Price Prediction"]
)


@router.post("/predict", response_model=PredictionResponse)
async def predict_price(item: EWasteInput):
    """
    Predict the resale price for a single e-waste item
    
    This endpoint delegates prediction to the HuggingFace Space
    "eyasir2047/e-waste-price-estimation" service.
    """
    try:
        # Prepare payload expected by the Space
        payload = {
            'Product_Type': item.product_type,
            'Brand': item.brand,
            'Build_Quality': item.build_quality,
            'User_Lifespan': item.user_lifespan,
            'Usage_Pattern': item.usage_pattern,
            'Expiry_Years': item.expiry_years,
            'Condition': item.condition,
            'Original_Price': item.original_price,
            'Used_Duration': item.used_duration,
        }
        
        logger.info(f"[HF SPACE] Calling {HF_PREDICT_ENDPOINT} with payload: {payload}")
        print(f"[HF SPACE] Calling {HF_PREDICT_ENDPOINT} with payload: {payload}")

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(HF_PREDICT_ENDPOINT, json=payload)
            if resp.status_code != 200:
                error_msg = f"[HF SPACE ERROR] Status={resp.status_code}, Response={resp.text}, Payload={payload}"
                logger.error(error_msg)
                print(error_msg)
                raise HTTPException(status_code=resp.status_code, detail="Prediction service error")
            data = resp.json()
            logger.info(f"[HF SPACE SUCCESS] Response: {data}")
            print(f"[HF SPACE SUCCESS] Response: {data}")

        # The Space likely returns a numeric prediction; handle common shapes
        if isinstance(data, dict):
            price = data.get('predicted_price') or data.get('price') or data.get('prediction')
        else:
            price = data

        if price is None:
            error_msg = f"[HF SPACE ERROR] Invalid response format: {data}"
            logger.error(error_msg)
            print(error_msg)
            raise HTTPException(status_code=502, detail="Invalid response from prediction service")

        predicted_price = round(float(price), 2)

        logger.info(f"Predicted price for {item.product_type} ({item.brand}): ${predicted_price}")

        return PredictionResponse(predicted_price=predicted_price)
        
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"[HF SPACE ERROR] Exception in price prediction: {str(e)}"
        logger.error(error_msg, exc_info=True)
        print(error_msg)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Prediction failed: {str(e)}")


@router.post("/batch", response_model=BatchResponse)
async def predict_batch(batch: BatchInput):
    """
    Predict resale prices for multiple e-waste items in a single request
    
    This endpoint processes multiple items by delegating to the HuggingFace Space.
    """
    try:
        # Prepare batch payload; prefer an array if the Space supports it
        payload_items = [{
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

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(HF_PREDICT_ENDPOINT, json={'items': payload_items})
            if resp.status_code != 200:
                logger.error(f"HF Space batch prediction failed: status={resp.status_code}, response={resp.text}, items_count={len(payload_items)}")
                raise HTTPException(status_code=resp.status_code, detail="Batch prediction service error")
            data = resp.json()
            logger.info(f"HF Space batch response: {data}")

        # Accept both list and dict formats
        if isinstance(data, dict):
            prices = data.get('predictions') or data.get('prices') or data.get('results')
        else:
            prices = data

        if not isinstance(prices, list):
            logger.error(f"Invalid HF Space batch response format: expected list, got {type(prices)}, data={data}")
            raise HTTPException(status_code=502, detail="Invalid response format from prediction service")

        rounded_prices = [round(float(p), 2) for p in prices]

        logger.info(f"Predicted prices for {len(batch.items)} items")

        return BatchResponse(predictions=rounded_prices)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch prediction: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch prediction failed: {str(e)}")


@router.get("/health")
async def health_check():
    """
    Check if the external price prediction service is healthy
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(HF_HEALTH_ENDPOINT)
        return {
            "status": "healthy" if resp.status_code == 200 else "degraded",
            "upstream_status_code": resp.status_code,
            "upstream_url": HF_SPACE_BASE_URL,
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")

