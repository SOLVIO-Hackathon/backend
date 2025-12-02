"""
External E-Waste Price Prediction Service
Calls external API for price prediction
"""

import logging
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel
import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class PricePredictionRequest(BaseModel):
    """Request schema for external price prediction API"""
    brand: str
    build_quality: int
    condition: int
    expiry_years: int
    original_price: float
    product_type: str
    usage_pattern: str
    used_duration: int
    user_lifespan: int


class PricePredictionResponse(BaseModel):
    """Response schema from external price prediction API"""
    predicted_price: float


class ExternalPricePredictionService:
    """Service to call external price prediction API"""

    def __init__(self):
        self.api_url = settings.PRICE_PREDICTION_API_URL
        self.timeout = 10.0  # 10 seconds timeout

    async def predict_price(
        self,
        brand: str,
        build_quality: int,
        condition: int,
        expiry_years: int,
        original_price: float,
        product_type: str,
        usage_pattern: str,
        used_duration: int,
        user_lifespan: int,
    ) -> Optional[Decimal]:
        """
        Call external API to predict e-waste price
        
        Returns:
            Predicted price as Decimal, or None if API call fails
        """
        try:
            request_data = PricePredictionRequest(
                brand=brand,
                build_quality=build_quality,
                condition=condition,
                expiry_years=expiry_years,
                original_price=original_price,
                product_type=product_type,
                usage_pattern=usage_pattern,
                used_duration=used_duration,
                user_lifespan=user_lifespan,
            )

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url,
                    json=request_data.model_dump(),
                    headers={
                        "accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                
                result = PricePredictionResponse(**response.json())
                predicted_price = Decimal(str(result.predicted_price))
                
                logger.info(
                    f"Price prediction successful: {predicted_price} for {product_type}"
                )
                return predicted_price

        except httpx.HTTPError as e:
            logger.error(f"HTTP error calling price prediction API: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error calling price prediction API: {str(e)}")
            return None


# Global service instance
_service: Optional[ExternalPricePredictionService] = None


def get_external_price_prediction_service() -> ExternalPricePredictionService:
    """Get the global external price prediction service instance"""
    global _service
    if _service is None:
        _service = ExternalPricePredictionService()
    return _service
