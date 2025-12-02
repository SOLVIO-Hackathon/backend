"""Guardrails for ReAct Agent

Implements relevance checking to ensure conversations stay on-topic
and prevent misuse of the agent.
"""

from typing import Dict, Any
from langchain_core.tools import tool


# Keywords related to waste management
WASTE_KEYWORDS = [
    "waste", "trash", "garbage", "recycl", "disposal", "cleanup",
    "quest", "bounty", "organic", "plastic", "e-waste", "electronic",
    "compost", "landfill", "pollution", "environment", "litter",
    "bin", "dump", "rubbish", "debris", "refuse", "junk",
    "sanitation", "hygiene", "clean", "dirty", "manage",
    "transaction", "payment", "bounty", "points", "reward"
]


@tool
def check_relevance(user_message: str) -> Dict[str, Any]:
    """
    Check if a user message is relevant to waste management topics.
    
    This guardrail helps prevent off-topic conversations and potential misuse.
    The agent should use this tool when a message seems unrelated to:
    - Waste management and cleanup
    - Quest creation and tracking
    - Transactions and rewards
    - Environmental topics
    
    Args:
        user_message: The user's message to check
        
    Returns:
        Dictionary with relevance assessment
    """
    # Convert to lowercase for matching
    message_lower = user_message.lower()
    
    # Check for waste-related keywords
    has_waste_keywords = any(keyword in message_lower for keyword in WASTE_KEYWORDS)
    
    # Check for common off-topic patterns
    off_topic_patterns = [
        "weather", "joke", "story", "recipe", "sports", "politics",
        "movie", "music", "game", "crypto", "stock"
    ]
    has_off_topic = any(pattern in message_lower for pattern in off_topic_patterns)
    
    # Determine relevance
    if has_waste_keywords:
        return {
            "is_relevant": True,
            "reason": "Message is related to waste management topics",
            "confidence": "high"
        }
    elif has_off_topic:
        return {
            "is_relevant": False,
            "reason": "Message appears to be off-topic. This agent is designed to help with waste management, quest creation, and environmental topics.",
            "confidence": "high",
            "suggestion": "Please ask questions related to waste cleanup, quest creation, or environmental topics."
        }
    else:
        # Unclear - give benefit of doubt but with lower confidence
        return {
            "is_relevant": True,
            "reason": "Message topic unclear, but proceeding with caution",
            "confidence": "low",
            "suggestion": "For best results, ask questions about waste management, quest creation, or check your quest status."
        }
