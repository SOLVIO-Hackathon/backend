"""
External Price Prediction API Service
Calls the trained model API with fallback to Gemini
"""

import logging
import httpx
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ExternalPricePredictionRequest(BaseModel):
    """Request schema for external price prediction API"""
    brand: str
    build_quality: int  # 1-10
    condition: int  # 1-10
    expiry_years: int
    original_price: float
    product_type: str  # e.g., "Laptop", "Mobile", etc.
    usage_pattern: str  # e.g., "Moderate", "Heavy", "Light"
    used_duration: int
    user_lifespan: int


class ExternalPricePredictionResponse(BaseModel):
    """Response schema from external price prediction API"""
    predicted_price: float


class ExternalPriceAPIService:
    """Service to interact with external price prediction API"""

    def __init__(self, api_url: str = "https://7cf7fa5eb76d.ngrok-free.app/price-prediction/predict"):
        self.api_url = api_url
        self.timeout = 10.0  # 10 second timeout

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
        user_lifespan: int
    ) -> Optional[Decimal]:
        """
        Call external API to predict price

        Returns:
            Decimal: Predicted price if successful
            None: If API call fails
        """
        try:
            request_data = ExternalPricePredictionRequest(
                brand=brand,
                build_quality=build_quality,
                condition=condition,
                expiry_years=expiry_years,
                original_price=original_price,
                product_type=product_type,
                usage_pattern=usage_pattern,
                used_duration=used_duration,
                user_lifespan=user_lifespan
            )

            logger.info(f"Calling external price API with data: {request_data.model_dump()}")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.api_url,
                    json=request_data.model_dump(),
                    headers={
                        "accept": "application/json",
                        "Content-Type": "application/json"
                    }
                )

                # Check if request was successful
                response.raise_for_status()

                # Parse response
                response_data = response.json()
                predicted_price = response_data.get("predicted_price")

                if predicted_price is None:
                    logger.error("External API returned no predicted_price field")
                    return None

                # Convert to Decimal for precision
                result = Decimal(str(predicted_price))
                logger.info(f"External API prediction successful: {result}")
                return result

        except httpx.TimeoutException:
            logger.warning(f"External API timeout after {self.timeout}s")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"External API HTTP error: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"External API request error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error calling external API: {str(e)}")
            return None


# Global service instance
_external_price_service: Optional[ExternalPriceAPIService] = None


def get_external_price_service() -> ExternalPriceAPIService:
    """Get the global external price API service instance"""
    global _external_price_service
    if _external_price_service is None:
        _external_price_service = ExternalPriceAPIService()
    return _external_price_service
