"""Pydantic schemas for bin fill prediction"""

from pydantic import BaseModel, Field, validator
from typing import List
from datetime import datetime


class BinDataPoint(BaseModel):
    """Single hour of bin data"""
    timestamp: str = Field(..., description="Timestamp in ISO format (YYYY-MM-DD HH:MM:SS)")
    day_of_week: str = Field(..., description="Day of week (e.g., Monday)")
    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    is_weekend: bool = Field(..., description="Is it weekend?")
    is_holiday: bool = Field(..., description="Is it a holiday?")
    temperature_c: float = Field(..., description="Temperature in Celsius")
    precipitation_mm: float = Field(..., ge=0, description="Precipitation in mm")
    foot_traffic_level: str = Field(..., description="Traffic level (Low/Medium/High/Very_High)")
    dustbin_capacity_liters: int = Field(..., gt=0, description="Bin capacity in liters")
    fill_rate_per_hour: float = Field(..., ge=0, description="Fill rate per hour")
    current_fill_level_percent: float = Field(..., ge=0, le=100, description="Current fill level %")
    
    @validator('foot_traffic_level')
    def validate_traffic_level(cls, v):
        allowed = ['Low', 'Medium', 'High', 'Very_High']
        if v not in allowed:
            raise ValueError(f"foot_traffic_level must be one of {allowed}")
        return v
    
    @validator('timestamp')
    def validate_timestamp(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
        except:
            raise ValueError("timestamp must be in ISO format (YYYY-MM-DD HH:MM:SS)")
        return v


class PredictionRequest(BaseModel):
    """Request with multiple hours of historical data"""
    data: List[BinDataPoint] = Field(..., min_items=12, description="Historical data (minimum 12 hours)")
    
    class Config:
        schema_extra = {
            "example": {
                "data": [
                    {
                        "timestamp": "2024-07-01 00:00:00",
                        "day_of_week": "Monday",
                        "hour": 0,
                        "month": 7,
                        "is_weekend": False,
                        "is_holiday": False,
                        "temperature_c": 24.9,
                        "precipitation_mm": 0,
                        "foot_traffic_level": "High",
                        "dustbin_capacity_liters": 500,
                        "fill_rate_per_hour": 2.0,
                        "current_fill_level_percent": 0.4
                    }
                ] * 12
            }
        }


class PredictionResponse(BaseModel):
    """Prediction response"""
    predicted_time_to_full_hours: float = Field(..., description="Predicted hours until bin is full")
    current_fill_level_percent: float = Field(..., description="Current fill level")
    predicted_full_datetime: str = Field(..., description="Estimated datetime when bin will be full")
    confidence: str = Field(..., description="Prediction confidence level")
    model_version: str = Field(..., description="Model version")
    
    class Config:
        schema_extra = {
            "example": {
                "predicted_time_to_full_hours": 48.5,
                "current_fill_level_percent": 25.3,
                "predicted_full_datetime": "2024-07-03 00:30:00",
                "confidence": "High",
                "model_version": "1.0.0"
            }
        }


class BatchPredictionResponse(BaseModel):
    """Batch prediction response"""
    results: List[dict] = Field(..., description="List of prediction results")
    total: int = Field(..., description="Total number of requests")
    successful: int = Field(..., description="Number of successful predictions")


class ModelInfoResponse(BaseModel):
    """Model information response"""
    model_type: str
    lookback_hours: int
    features: List[str]
    hyperparameters: dict
    version: str
    trained_date: str

