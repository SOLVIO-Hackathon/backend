from typing import Generic, TypeVar, List
from pydantic import BaseModel, Field

T = TypeVar("T")


class LocationSchema(BaseModel):
    """Location with latitude and longitude"""
    latitude: float = Field(..., ge=-90, le=90, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude coordinate")

    model_config = {
        "json_schema_extra": {
            "example": {
                "latitude": 23.8103,
                "longitude": 90.4125
            }
        }
    }


class PaginationParams(BaseModel):
    """Pagination parameters"""
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(100, ge=1, le=100, description="Maximum number of records to return")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response"""
    items: List[T]
    total: int
    skip: int
    limit: int


class MessageResponse(BaseModel):
    """Simple message response"""
    message: str

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "Operation completed successfully"
            }
        }
    }
