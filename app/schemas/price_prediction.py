"""
E-Waste Price Prediction Schemas
"""

from pydantic import BaseModel, Field
from typing import List


class EWasteInput(BaseModel):
    """Input model for e-waste price prediction"""
    product_type: str = Field(..., description="Type of e-waste product")
    brand: str = Field(..., description="Brand name")
    build_quality: int = Field(..., ge=1, le=10, description="Build quality rating (1-10)")
    user_lifespan: float = Field(..., gt=0, description="Expected user lifespan in years")
    usage_pattern: str = Field(..., description="Usage pattern (e.g., Light, Moderate, Heavy)")
    expiry_years: float = Field(..., gt=0, description="Years until product expiry")
    condition: int = Field(..., ge=1, le=10, description="Current condition rating (1-10)")
    original_price: float = Field(..., gt=0, description="Original purchase price")
    used_duration: int = Field(..., ge=0, description="Duration of use in years")

    class Config:
        json_schema_extra = {
            "example": {
                "product_type": "Laptop",
                "brand": "Dell",
                "build_quality": 8,
                "user_lifespan": 5.0,
                "usage_pattern": "Moderate",
                "expiry_years": 7.0,
                "condition": 7,
                "original_price": 800.0,
                "used_duration": 2
            }
        }


class PredictionResponse(BaseModel):
    """Response model for single prediction"""
    predicted_price: float = Field(..., description="Predicted resale price")


class BatchInput(BaseModel):
    """Input model for batch predictions"""
    items: List[EWasteInput] = Field(..., description="List of e-waste items to predict")


class BatchResponse(BaseModel):
    """Response model for batch predictions"""
    predictions: List[float] = Field(..., description="List of predicted prices")

