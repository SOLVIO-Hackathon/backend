"""Quest Creation Tools for ReAct Agent

These tools guide the user through a multi-step workflow to create waste cleanup quests:
1. collect_image_url - Collect and validate image URL
2. collect_location - Collect and validate GPS coordinates  
3. analyze_waste_image - Use AI to analyze waste and generate description
4. create_quest_in_database - Create the quest in the database
"""

from typing import Dict, Any, Optional
from uuid import UUID
import re
import pygeohash

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from app.models.user import User
from app.models.quest import Quest, WasteType, Severity, QuestStatus
from app.services.ai_service import GeminiAIService
from app.agents.state import QuestDraft


# Bounty points mapping
BOUNTY_MAP = {
    "organic": 20,
    "recyclable": 50,
    "general": 30,
    "e_waste": 100,
}


@tool
def collect_image_url(image_url: str) -> Dict[str, Any]:
    """
    Collect and validate the waste image URL from the user.
    
    Args:
        image_url: URL to the waste image (must start with http:// or https://)
        
    Returns:
        Dictionary with validation status and next steps
    """
    # Validate URL format
    url_pattern = re.compile(r'^https?://')
    
    if not url_pattern.match(image_url):
        return {
            "success": False,
            "error": "Invalid URL format. URL must start with http:// or https://",
            "next_step": "awaiting_image"
        }
    
    return {
        "success": True,
        "message": "Image URL received successfully! Now I need the location coordinates.",
        "image_url": image_url,
        "next_step": "awaiting_location"
    }


@tool
def collect_location(latitude: float, longitude: float) -> Dict[str, Any]:
    """
    Collect and validate GPS coordinates for the waste location.
    
    Args:
        latitude: Latitude coordinate (-90 to 90)
        longitude: Longitude coordinate (-180 to 180)
        
    Returns:
        Dictionary with validation status and next steps
    """
    # Validate coordinate ranges
    if not (-90 <= latitude <= 90):
        return {
            "success": False,
            "error": f"Invalid latitude: {latitude}. Must be between -90 and 90",
            "next_step": "awaiting_location"
        }
    
    if not (-180 <= longitude <= 180):
        return {
            "success": False,
            "error": f"Invalid longitude: {longitude}. Must be between -180 and 180",
            "next_step": "awaiting_location"
        }
    
    return {
        "success": True,
        "message": "Location received! Let me analyze the waste image using AI...",
        "latitude": latitude,
        "longitude": longitude,
        "next_step": "analyzing_image"
    }


@tool
async def analyze_waste_image(
    image_url: str,
    ai_service: GeminiAIService
) -> Dict[str, Any]:
    """
    Analyze the waste image using AI to extract waste classification.
    
    Args:
        image_url: URL to the waste image
        ai_service: AI service instance for image classification
        
    Returns:
        Dictionary with AI analysis results and preview
    """
    try:
        # Call existing GeminiAIService.classify_waste method
        classification = await ai_service.classify_waste(
            image_url=image_url,
            additional_context=None
        )
        
        # Generate description from detected items
        items_str = ", ".join(classification.detected_items[:3])
        description = f"{classification.estimated_volume} of {items_str}"
        if len(classification.detected_items) > 3:
            description += f" and {len(classification.detected_items) - 3} more items"
        
        # Calculate bounty points based on waste type
        waste_type = classification.waste_type.value
        bounty_points = BOUNTY_MAP.get(waste_type, 30)
        
        # Format preview for user confirmation
        preview = f"""
**Quest Preview:**
📸 **Description:** {description}
🗑️ **Waste Type:** {classification.waste_type.value.replace('_', ' ').title()}
⚠️ **Severity:** {classification.severity.value.title()}
💰 **Bounty Points:** {bounty_points}
🎯 **AI Confidence:** {classification.confidence_score:.1%}

Does this look correct? Please confirm to create the quest.
"""
        
        return {
            "success": True,
            "description": description,
            "waste_type": waste_type,
            "severity": classification.severity.value,
            "confidence_score": classification.confidence_score,
            "bounty_points": bounty_points,
            "preview": preview,
            "next_step": "awaiting_confirmation"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to analyze image: {str(e)}",
            "next_step": "awaiting_image"
        }


@tool
async def create_quest_in_database(
    quest_draft: QuestDraft,
    user: User,
    session: AsyncSession
) -> Dict[str, Any]:
    """
    Create the quest in the database after user confirmation.
    
    Args:
        quest_draft: Draft quest with all collected information
        user: Authenticated user (reporter)
        session: Database session
        
    Returns:
        Dictionary with created quest details
    """
    try:
        # Validate quest draft has all required fields
        if not all([
            quest_draft.image_url,
            quest_draft.location_lat is not None,
            quest_draft.location_lng is not None,
            quest_draft.description,
            quest_draft.waste_type,
            quest_draft.severity,
            quest_draft.bounty_points
        ]):
            return {
                "success": False,
                "error": "Quest draft is missing required fields",
                "next_step": "awaiting_image"
            }
        
        if not quest_draft.user_confirmed:
            return {
                "success": False,
                "error": "User must confirm the quest details before creation",
                "next_step": "awaiting_confirmation"
            }
        
        # Calculate geohash for location indexing
        geohash = pygeohash.encode(
            quest_draft.location_lat,
            quest_draft.location_lng,
            precision=8
        )
        ward_geohash = geohash[:5]  # First 5 chars for ward-level grouping
        
        # Create Point geometry for PostGIS
        point = Point(quest_draft.location_lng, quest_draft.location_lat)
        location_geom = from_shape(point, srid=4326)
        
        # Generate title from description
        title = quest_draft.description[:100] + "..." if len(quest_draft.description) > 100 else quest_draft.description
        
        # Create Quest model
        new_quest = Quest(
            reporter_id=user.id,
            title=title,
            description=quest_draft.description,
            location=location_geom,
            geohash=geohash,
            ward_geohash=ward_geohash,
            waste_type=WasteType(quest_draft.waste_type),
            severity=Severity(quest_draft.severity),
            status=QuestStatus.REPORTED,
            bounty_points=quest_draft.bounty_points,
            image_url=quest_draft.image_url,
            ai_verification_score=quest_draft.confidence_score
        )
        
        # Add to session and commit
        session.add(new_quest)
        await session.commit()
        await session.refresh(new_quest)
        
        return {
            "success": True,
            "message": f"✅ Quest created successfully! Quest ID: {new_quest.id}",
            "quest_id": str(new_quest.id),
            "bounty_points": quest_draft.bounty_points,
            "next_step": "completed"
        }
        
    except Exception as e:
        await session.rollback()
        return {
            "success": False,
            "error": f"Failed to create quest: {str(e)}",
            "next_step": "awaiting_confirmation"
        }
