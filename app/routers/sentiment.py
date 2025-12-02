"""
Bangla Sentiment Analysis Router

Provides sentiment analysis for text input using a fine-tuned transformer model.
"""

from fastapi import APIRouter, HTTPException, status
import logging
import os
import torch

from app.schemas.sentiment import SentimentInput, SentimentOutput
from app.services.sentiment_service import get_sentiment_analyzer

router = APIRouter(prefix="/sentiment", tags=["Sentiment Analysis"])
logger = logging.getLogger("router.sentiment")


@router.post("/predict", response_model=SentimentOutput)
async def predict_sentiment(input_data: SentimentInput):
    """
    Predict sentiment for input text
    
    Analyzes the input text and returns:
    - sentiment: negative, neutral, or positive
    - confidence: probability score (0.0 to 1.0)
    
    Supports Bangla and English text.
    """
    try:
        analyzer = get_sentiment_analyzer()
        result = analyzer.predict(input_data.text)
        return SentimentOutput(**result)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model error: {str(e)}"
        )
    except Exception as e:
        logger.exception(f"Sentiment prediction failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Prediction failed: {str(e)}"
        )


@router.get("/debug")
async def sentiment_debug():
    """
    Get debug information about sentiment analysis service
    
    Returns model status, device information, and configuration details.
    """
    info = {
        "service": "Bangla Sentiment Analysis",
        "model_path": "Bangla Sentiment Analysis/waste_sentiment_model_finetune",
        "torch_available": False,
        "torch_version": None,
        "cuda_available": False,
        "device": None,
        "transformers_available": False,
        "transformers_version": None,
        "model_loaded": False,
    }
    
    try:
        import torch as _torch
        info["torch_available"] = True
        info["torch_version"] = _torch.__version__
        info["cuda_available"] = _torch.cuda.is_available()
        info["device"] = str(_torch.device('cuda' if _torch.cuda.is_available() else 'cpu'))
    except Exception:
        pass
    
    try:
        import transformers as _transformers
        info["transformers_available"] = True
        info["transformers_version"] = _transformers.__version__
    except Exception:
        pass
    
    try:
        from app.services.sentiment_service import analyzer
        if analyzer and analyzer.model_loaded:
            info["model_loaded"] = True
    except Exception:
        pass
    
    return info

