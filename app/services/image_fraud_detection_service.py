"""
Image Fraud Detection Service

Detects AI-generated images and internet-downloaded images using:
1. Sightengine API - AI-generated image detection
2. SerpAPI Google Lens - Reverse image search (web detection)
"""

import aiohttp
import asyncio
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import os
import json
from app.core.config import settings


@dataclass
class ImageFraudResult:
    """Result of image fraud detection"""
    is_fraudulent: bool
    fraud_type: Optional[str]  # "ai_generated", "web_image", "both", None
    confidence_score: float  # 0-1, higher = more confident it's fraud
    ai_generated_score: Optional[float]  # Sightengine score
    web_detection_matches: Optional[List[Dict]]  # SerpAPI matches
    detailed_reason: str
    should_block: bool  # True if image should be rejected


class ImageFraudDetectionService:
    """Service for detecting fraudulent images (AI-generated or downloaded from web)"""

    def __init__(self):
        # Sightengine credentials
        self.sightengine_api_user = settings.SIGHTENGINE_API_USER
        self.sightengine_api_secret = settings.SIGHTENGINE_API_SECRET

        # SerpAPI credentials
        self.serpapi_key = settings.SERPAPI_KEY

    async def detect_ai_generated_image(self, image_url: str) -> Tuple[bool, float, str]:
        """
        Check if image is AI-generated using Sightengine API

        Returns:
            (is_ai_generated, confidence_score, reason)
        """
        if not self.sightengine_api_user or not self.sightengine_api_secret:
            return False, 0.0, "Sightengine API credentials not configured"

        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    'url': image_url,
                    'models': 'genai',
                    'api_user': self.sightengine_api_user,
                    'api_secret': self.sightengine_api_secret
                }

                async with session.get('https://api.sightengine.com/1.0/check.json', params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        return False, 0.0, f"Sightengine API error: {error_text}"

                    data = await response.json()

                    # Check for API errors
                    if data.get('status') == 'failure':
                        return False, 0.0, f"Sightengine API failure: {data.get('error', {}).get('message', 'Unknown error')}"

                    # Extract AI-generated detection score
                    # Sightengine returns: { "genai": { "ai_generated": float (0-1) } }
                    ai_score = data.get('genai', {}).get('ai_generated', 0.0)

                    # Threshold: Consider AI-generated if score > 0.5
                    is_ai_generated = ai_score > 0.5

                    reason = f"AI-generated detection score: {ai_score:.2f}"
                    if is_ai_generated:
                        reason += f" (threshold: 0.5) - Image appears to be AI-generated"

                    return is_ai_generated, ai_score, reason

        except Exception as e:
            return False, 0.0, f"Error checking AI-generated image: {str(e)}"

    async def detect_web_image(self, image_url: str) -> Tuple[bool, List[Dict], str]:
        """
        Check if image exists on the web using SerpAPI Google Lens

        Returns:
            (is_web_image, matches, reason)
        """
        if not self.serpapi_key:
            return False, [], "SerpAPI key not configured"

        try:
            # Call SerpAPI Google Lens
            async with aiohttp.ClientSession() as session:
                params = {
                    'engine': 'google_lens',
                    'url': image_url,
                    'api_key': self.serpapi_key
                }

                async with session.get('https://serpapi.com/search', params=params) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        print(f"[SerpAPI] Error: Status {response.status}, {error_text}")
                        return False, [], f"SerpAPI error: {error_text}"

                    data = await response.json()

                    # Debug: log what we got
                    try:
                        visual_matches_count = len(data.get('visual_matches', []))
                        print(f"[SerpAPI] Found {visual_matches_count} visual matches")
                    except Exception:
                        pass

                    # Extract matches
                    matches = []
                    
                    # Visual matches (similar images found on the web)
                    visual_matches = data.get('visual_matches', [])
                    for idx, match in enumerate(visual_matches[:10]):  # Limit to top 10
                        matches.append({
                            'type': 'visual_match',
                            'url': match.get('link'),
                            'source': match.get('source'),
                            'title': match.get('title'),
                            'score': 0.9 - (idx * 0.05)  # Decreasing confidence
                        })

                    # Reverse image search results
                    reverse_results = data.get('reverse_image_search_results', {})
                    if reverse_results:
                        # Extract page matches
                        for idx, result in enumerate(reverse_results.get('inline_image_results', [])[:5]):
                            matches.append({
                                'type': 'page_match',
                                'url': result.get('source'),
                                'thumbnail': result.get('thumbnail'),
                                'score': 0.7 - (idx * 0.05)
                            })

                    # Check for suspicious domains
                    suspicious_domains = [
                        'unsplash.com', 'pexels.com', 'pixabay.com',
                        'shutterstock.com', 'gettyimages.com', 'istockphoto.com',
                        'freepik.com', 'pinterest.com', 'imgur.com'
                    ]
                    has_suspicious_source = any(
                        any(domain in str(m.get('url', '')).lower() or domain in str(m.get('source', '')).lower() 
                            for domain in suspicious_domains)
                        for m in matches
                    )

                    # Consider it a web image if we have any visual matches
                    is_web_image = len(visual_matches) > 0 or has_suspicious_source

                    reason = f"Found {len(visual_matches)} visual matches on the web"
                    if is_web_image:
                        if has_suspicious_source:
                            reason += " including stock photo sites"
                        reason += " - Image appears to be downloaded from the internet"

                    return is_web_image, matches, reason

        except Exception as e:
            print(f"[SerpAPI] Exception: {str(e)}")
            return False, [], f"Error checking web image: {str(e)}"

    async def check_image_fraud(self, image_url: str) -> ImageFraudResult:
        """
        Comprehensive fraud check combining AI-generated and web image detection

        Args:
            image_url: URL of the image to check

        Returns:
            ImageFraudResult with detection results
        """
        # Run both checks in parallel
        ai_task = self.detect_ai_generated_image(image_url)
        web_task = self.detect_web_image(image_url)

        (is_ai_generated, ai_score, ai_reason), (is_web_image, web_matches, web_reason) = await asyncio.gather(
            ai_task, web_task
        )

        # Determine fraud type and overall result
        fraud_type = None
        is_fraudulent = False
        should_block = False
        detailed_reasons = []

        if is_ai_generated:
            fraud_type = "ai_generated"
            is_fraudulent = True
            should_block = ai_score > 0.7  # Block if highly confident
            detailed_reasons.append(ai_reason)

        if is_web_image:
            if fraud_type == "ai_generated":
                fraud_type = "both"
            else:
                fraud_type = "web_image"
            is_fraudulent = True
            # Block if we have visual matches
            visual_matches = len([m for m in web_matches if m['type'] == 'visual_match'])
            should_block = should_block or (visual_matches > 0)
            detailed_reasons.append(web_reason)

        # Calculate overall confidence score
        if fraud_type == "both":
            confidence_score = max(ai_score, 0.8)  # High confidence if both detected
        elif fraud_type == "ai_generated":
            confidence_score = ai_score
        elif fraud_type == "web_image":
            # Calculate based on match quality
            visual_matches = len([m for m in web_matches if m['type'] == 'visual_match'])
            page_matches = len([m for m in web_matches if m['type'] == 'page_match'])
            confidence_score = min(1.0, (visual_matches * 0.8 + page_matches * 0.4))
        else:
            confidence_score = 0.0

        detailed_reason = " | ".join(detailed_reasons) if detailed_reasons else "Image appears authentic"

        return ImageFraudResult(
            is_fraudulent=is_fraudulent,
            fraud_type=fraud_type,
            confidence_score=confidence_score,
            ai_generated_score=ai_score if is_ai_generated else None,
            web_detection_matches=web_matches if is_web_image else None,
            detailed_reason=detailed_reason,
            should_block=should_block
        )


# Singleton instance
_image_fraud_detection_service: Optional[ImageFraudDetectionService] = None


def get_image_fraud_detection_service() -> ImageFraudDetectionService:
    """Get singleton instance of ImageFraudDetectionService"""
    global _image_fraud_detection_service
    if _image_fraud_detection_service is None:
        _image_fraud_detection_service = ImageFraudDetectionService()
    return _image_fraud_detection_service
