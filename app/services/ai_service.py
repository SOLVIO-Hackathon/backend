"""AI service using Langchain and Google Gemini 2.5 Flash for structured outputs"""

import base64
from typing import Optional, Dict, Any
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

from app.core.config import settings
from app.schemas.ai_outputs import (
    WasteClassificationOutput,
    EWasteClassificationOutput,
    BeforeAfterComparisonOutput,
)


class GeminiAIService:
    """Service for AI-powered waste classification and verification using Gemini 2.5 Flash"""

    def __init__(self):
        """Initialize Gemini AI service with Langchain"""
        self.api_key = settings.GOOGLE_API_KEY
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")

        # Initialize Gemini 2.5 Flash model
        self.model = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=self.api_key,
            temperature=0.2,  # Lower temperature for more consistent structured outputs
            max_retries=3,
        )

    @staticmethod
    def _encode_image(image_path: str) -> str:
        """Encode image to base64 string"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")

    @staticmethod
    def _load_image_from_url(image_url: str) -> Dict[str, Any]:
        """Prepare image data for Gemini API from URL"""
        return {
            "type": "image_url",
            "image_url": {"url": image_url}
        }

    async def classify_waste(
        self,
        image_url: str,
        additional_context: Optional[str] = None
    ) -> WasteClassificationOutput:
        """
        Classify waste from an image using Gemini Vision API with structured output.

        Args:
            image_url: URL or path to the waste image
            additional_context: Optional additional context about the location or situation

        Returns:
            WasteClassificationOutput: Structured classification results
        """
        # Create parser for structured output
        parser = PydanticOutputParser(pydantic_object=WasteClassificationOutput)

        # Create prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are an expert waste classification AI. Analyze images of waste and provide detailed,
                accurate classifications. Consider volume, type, severity, and potential hazards.

                Your task is to classify waste into categories (organic, recyclable, mixed, e_waste),
                assess severity (low, medium, high), and recommend appropriate bounty points for cleanup.

                {format_instructions}"""
            ),
            (
                "human",
                [
                    {
                        "type": "text",
                        "text": """Analyze this waste image and provide a comprehensive classification.

                        {additional_context}

                        Be thorough in identifying:
                        - The primary waste category
                        - Specific items visible
                        - Estimated volume/quantity
                        - Any hazards or safety concerns
                        - Appropriate difficulty/bounty points
                        """
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "{image_url}"}
                    }
                ]
            )
        ])

        # Format the prompt
        context_text = f"Additional context: {additional_context}" if additional_context else "No additional context provided."

        formatted_prompt = prompt_template.format_messages(
            format_instructions=parser.get_format_instructions(),
            image_url=image_url,
            additional_context=context_text
        )

        # Invoke the model
        response = await self.model.ainvoke(formatted_prompt)

        # Parse the response
        result = parser.parse(response.content)
        return result

    async def classify_ewaste(
        self,
        image_url: str,
        user_description: Optional[str] = None
    ) -> EWasteClassificationOutput:
        """
        Classify e-waste device from an image using Gemini Vision API with structured output.

        Args:
            image_url: URL or path to the device image
            user_description: Optional user-provided description of the device

        Returns:
            EWasteClassificationOutput: Structured e-waste classification results
        """
        # Create parser for structured output
        parser = PydanticOutputParser(pydantic_object=EWasteClassificationOutput)

        # Create prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are an expert e-waste valuation and classification AI. Analyze images of electronic devices
                and provide accurate assessments of device type, condition, and estimated market value.

                Consider factors like:
                - Device age and model (if identifiable)
                - Visible condition and damage
                - Working status indicators
                - Market demand for the device type
                - Recyclable component value

                {format_instructions}"""
            ),
            (
                "human",
                [
                    {
                        "type": "text",
                        "text": """Analyze this electronic device image and provide a comprehensive classification and valuation.

                        {user_description}

                        Identify:
                        - Device type and model (if possible)
                        - Working condition
                        - Visible components and features
                        - Estimated resale or recycling value
                        - Any damage or wear indicators
                        """
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "{image_url}"}
                    }
                ]
            )
        ])

        # Format the prompt
        description_text = f"User description: {user_description}" if user_description else "No description provided."

        formatted_prompt = prompt_template.format_messages(
            format_instructions=parser.get_format_instructions(),
            image_url=image_url,
            user_description=description_text
        )

        # Invoke the model
        response = await self.model.ainvoke(formatted_prompt)

        # Parse the response
        result = parser.parse(response.content)
        return result

    async def verify_before_after_cleanup(
        self,
        before_image_url: str,
        after_image_url: str,
        expected_waste_type: Optional[str] = None,
        metadata_comparison: Optional[Dict[str, Any]] = None
    ) -> BeforeAfterComparisonOutput:
        """
        Verify cleanup completion by comparing before and after photos.

        Args:
            before_image_url: URL to the 'before' cleanup photo
            after_image_url: URL to the 'after' cleanup photo
            expected_waste_type: Optional expected waste type for validation
            metadata_comparison: Optional EXIF metadata comparison results

        Returns:
            BeforeAfterComparisonOutput: Structured verification results
        """
        # Create parser for structured output
        parser = PydanticOutputParser(pydantic_object=BeforeAfterComparisonOutput)

        # Create prompt template
        prompt_template = ChatPromptTemplate.from_messages([
            (
                "system",
                """You are an expert photo verification AI for waste cleanup validation. Your job is to compare
                before and after photos to verify legitimate cleanup efforts and detect fraud.

                Carefully analyze:
                1. Location consistency - Are these photos from the same location?
                2. Waste removal - How much waste was actually removed?
                3. Cleanup quality - How thorough was the cleanup?
                4. Fraud indicators - Any signs of photo manipulation, different locations, or staged photos?

                Be strict but fair. Genuine cleanup efforts should be rewarded, but fraud must be detected.

                {format_instructions}"""
            ),
            (
                "human",
                [
                    {
                        "type": "text",
                        "text": """Compare these before and after cleanup photos and verify the cleanup effort.

                        Expected waste type: {expected_waste_type}

                        Metadata comparison results: {metadata_comparison}

                        BEFORE PHOTO (showing waste):"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "{before_image_url}"}
                    },
                    {
                        "type": "text",
                        "text": "AFTER PHOTO (should show cleanup):"
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": "{after_image_url}"}
                    },
                    {
                        "type": "text",
                        "text": """
                        Provide a thorough verification assessment:
                        - Are these from the same location?
                        - What percentage of waste was removed?
                        - Is this a legitimate cleanup or potential fraud?
                        - What is the quality of the cleanup work?
                        - Should this quest completion be approved?
                        """
                    }
                ]
            )
        ])

        # Format the prompt
        waste_type_text = expected_waste_type if expected_waste_type else "Not specified"
        metadata_text = str(metadata_comparison) if metadata_comparison else "No metadata comparison available"

        formatted_prompt = prompt_template.format_messages(
            format_instructions=parser.get_format_instructions(),
            before_image_url=before_image_url,
            after_image_url=after_image_url,
            expected_waste_type=waste_type_text,
            metadata_comparison=metadata_text
        )

        # Invoke the model
        response = await self.model.ainvoke(formatted_prompt)

        # Parse the response
        result = parser.parse(response.content)
        return result


# Singleton instance
_ai_service_instance: Optional[GeminiAIService] = None


def get_ai_service() -> GeminiAIService:
    """Get or create AI service singleton instance"""
    global _ai_service_instance
    if _ai_service_instance is None:
        _ai_service_instance = GeminiAIService()
    return _ai_service_instance
