from pydantic import BaseModel, Field
from datetime import datetime


class ComplaintCreate(BaseModel):
    text: str = Field(..., min_length=1)
    language: str
    sentiment: str
    confidence: float
    severity: str


class ComplaintOut(BaseModel):
    id: int
    text: str
    language: str
    sentiment: str
    confidence: float
    severity: str
    created_at: datetime

    class Config:
        from_attributes = True
