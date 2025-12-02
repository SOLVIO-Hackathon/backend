"""
Bangla Sentiment Analysis Service
"""

import os
import logging
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

logger = logging.getLogger(__name__)


class BanglaSentimentAnalyzer:
    """
    Bangla sentiment analysis service using fine-tuned transformer model
    """

    def __init__(self):
        self.tokenizer = None
        self.model = None
        self.device = None
        self.model_loaded = False
        self.sentiment_map = {0: 'negative', 1: 'neutral', 2: 'positive'}

    def load_model(self):
        """Load the fine-tuned sentiment model and tokenizer"""
        try:
            # Get the base directory (backend folder)
            base_dir = Path(__file__).parent.parent.parent
            model_path = base_dir / "Bangla Sentiment Analysis" / "waste_sentiment_model_finetune"

            logger.info(f"Loading Bangla sentiment model from: {model_path}")

            if not model_path.exists():
                raise FileNotFoundError(f"Model directory not found: {model_path}")

            # Set device
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
            logger.info(f"Using device: {self.device}")

            # Load tokenizer and model
            self.tokenizer = AutoTokenizer.from_pretrained(str(model_path))
            self.model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
            
            # Move model to device and set to eval mode
            self.model.to(self.device)
            self.model.eval()

            logger.info("Successfully loaded Bangla sentiment analysis model")
            self.model_loaded = True

        except Exception as e:
            logger.error(f"Error loading sentiment model: {str(e)}")
            raise

    def predict(self, text: str) -> dict:
        """
        Predict sentiment for input text
        
        Args:
            text: Input text in Bangla or English
            
        Returns:
            Dictionary with sentiment and confidence
        """
        if not self.model_loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")

        try:
            # Tokenize input
            inputs = self.tokenizer(
                text,
                return_tensors='pt',
                padding=True,
                truncation=True,
                max_length=128
            ).to(self.device)
            
            # Run inference
            with torch.no_grad():
                outputs = self.model(**inputs)
                probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
                predicted_class = torch.argmax(probs, dim=-1).item()
                confidence = probs[0][predicted_class].item()
            
            sentiment = self.sentiment_map[predicted_class]
            
            return {
                "text": text,
                "sentiment": sentiment,
                "confidence": float(confidence)
            }

        except Exception as e:
            logger.error(f"Error during sentiment prediction: {str(e)}")
            raise


# Global analyzer instance
analyzer: BanglaSentimentAnalyzer = None


def get_sentiment_analyzer() -> BanglaSentimentAnalyzer:
    """Get the global sentiment analyzer instance"""
    global analyzer
    if analyzer is None:
        analyzer = BanglaSentimentAnalyzer()
        analyzer.load_model()
    return analyzer

