"""Pydantic schemas for sentiment analysis"""

from pydantic import BaseModel, Field


class SentimentInput(BaseModel):
    """Input schema for sentiment analysis"""
    
    text: str = Field(
        ...,
        description="Input text for sentiment analysis (Bangla or English)",
        min_length=1,
        max_length=1000
    )


class SentimentOutput(BaseModel):
    """Output schema for sentiment analysis"""
    
    text: str = Field(
        description="The input text that was analyzed"
    )
    
    sentiment: str = Field(
        description="Predicted sentiment: 'negative', 'neutral', or 'positive'"
    )
    
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score of the prediction (0.0 to 1.0)"
    )

