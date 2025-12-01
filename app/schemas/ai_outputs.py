"""Pydantic schemas for AI-generated structured outputs"""

from typing import List, Optional
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class WasteCategory(str, Enum):
    """Waste classification categories"""
    ORGANIC = "organic"
    RECYCLABLE = "recyclable"
    GENERAL = "general"
    E_WASTE = "e_waste"


class SeverityLevel(str, Enum):
    """Waste severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WasteClassificationOutput(BaseModel):
    """Structured output for waste classification from Gemini Vision API"""

    waste_type: WasteCategory = Field(
        description="The primary category of waste identified in the image"
    )

    severity: SeverityLevel = Field(
        description="The severity level based on volume and hazard potential"
    )

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score of the classification (0.0 to 1.0)"
    )

    detected_items: List[str] = Field(
        description="List of specific waste items detected in the image",
        min_length=1
    )

    estimated_volume: str = Field(
        description="Estimated volume of waste (e.g., 'small bag', '2 large bags', 'pile approximately 1m³')"
    )

    hazard_indicators: List[str] = Field(
        default_factory=list,
        description="List of potential hazards identified (e.g., 'broken glass', 'chemical containers', 'sharp objects')"
    )

    recommended_bounty: int = Field(
        ge=10,
        le=500,
        description="Recommended bounty points based on severity and volume (10-500 points)"
    )

    cleanup_notes: Optional[str] = Field(
        default=None,
        description="Additional notes or special instructions for cleanup crew"
    )

    @field_validator('confidence_score')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError('Confidence score must be between 0.0 and 1.0')
        return v


class DeviceCategory(str, Enum):
    """E-waste device categories"""
    MOBILE = "mobile"
    LAPTOP = "laptop"
    DESKTOP = "desktop"
    MONITOR = "monitor"
    TABLET = "tablet"
    OTHER = "other"


class DeviceConditionEnum(str, Enum):
    """Device working condition"""
    WORKING = "working"
    PARTIALLY_WORKING = "partially_working"
    NOT_WORKING = "not_working"


class EWasteClassificationOutput(BaseModel):
    """Structured output for e-waste device classification"""

    device_type: DeviceCategory = Field(
        description="The category of electronic device identified"
    )

    device_name: str = Field(
        description="Specific device name/model if identifiable (e.g., 'iPhone 12', 'Dell Inspiron', 'Generic Android Phone')"
    )

    condition: DeviceConditionEnum = Field(
        description="Working condition of the device"
    )

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score of the classification (0.0 to 1.0)"
    )

    identified_components: List[str] = Field(
        description="List of visible components or features identified",
        min_length=1
    )

    estimated_value_min: Decimal = Field(
        ge=0,
        description="Minimum estimated value in USD"
    )

    estimated_value_max: Decimal = Field(
        ge=0,
        description="Maximum estimated value in USD"
    )

    condition_notes: Optional[str] = Field(
        default=None,
        description="Notes about visible damage, wear, or condition indicators"
    )

    recycling_value_notes: Optional[str] = Field(
        default=None,
        description="Notes about recyclable materials or components of value"
    )

    @field_validator('estimated_value_max')
    @classmethod
    def validate_value_range(cls, v: Decimal, info) -> Decimal:
        if 'estimated_value_min' in info.data and v < info.data['estimated_value_min']:
            raise ValueError('Maximum value must be greater than or equal to minimum value')
        return v


class CleanlinessLevel(str, Enum):
    """Cleanliness assessment levels"""
    MUCH_CLEANER = "much_cleaner"
    MODERATELY_CLEANER = "moderately_cleaner"
    SLIGHTLY_CLEANER = "slightly_cleaner"
    NO_CHANGE = "no_change"
    SUSPICIOUS = "suspicious"


class BeforeAfterComparisonOutput(BaseModel):
    """Structured output for before/after photo comparison verification"""

    is_valid_cleanup: bool = Field(
        description="Whether the comparison shows a legitimate cleanup effort"
    )

    cleanliness_level: CleanlinessLevel = Field(
        description="Assessment of cleanliness improvement"
    )

    verification_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall verification score (0.0 to 1.0, where 1.0 is perfect cleanup)"
    )

    waste_removed_percentage: int = Field(
        ge=0,
        le=100,
        description="Estimated percentage of waste removed (0-100)"
    )

    location_match_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence that before/after photos are from the same location"
    )

    fraud_indicators: List[str] = Field(
        default_factory=list,
        description="List of potential fraud indicators detected (e.g., 'different location', 'timestamp mismatch', 'photo editing detected')"
    )

    cleanup_quality_notes: str = Field(
        description="Detailed notes about the cleanup quality and thoroughness"
    )

    bonus_points_recommendation: int = Field(
        ge=0,
        le=100,
        description="Recommended bonus points for exceptional cleanup (0-100)"
    )

    verification_passed: bool = Field(
        description="Final verification decision - whether to approve the quest completion"
    )

    reviewer_notes: Optional[str] = Field(
        default=None,
        description="Additional notes for manual review if needed"
    )

    @field_validator('verification_score')
    @classmethod
    def validate_verification_score(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError('Verification score must be between 0.0 and 1.0')
        return v

    @field_validator('location_match_confidence')
    @classmethod
    def validate_location_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError('Location match confidence must be between 0.0 and 1.0')
        return v
