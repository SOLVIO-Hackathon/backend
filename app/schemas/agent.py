"""Agent API Schemas for Request/Response"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """Request schema for agent chat endpoint"""
    message: str = Field(
        ...,
        description="User's message to the agent",
        max_length=5000,
        examples=["I want to report some waste I found"]
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for continuing conversations. If not provided, a new session will be created."
    )
    conversation_history: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Previous messages in the conversation (for display purposes only, not used by agent)"
    )


class AgentChatResponse(BaseModel):
    """Response schema for agent chat endpoint"""
    response: str = Field(
        ...,
        description="Agent's response to the user"
    )
    session_id: str = Field(
        ...,
        description="Session ID for this conversation. Use this in subsequent requests to continue the conversation."
    )
    workflow_stage: str = Field(
        ...,
        description="Current workflow stage (idle, awaiting_image, awaiting_location, etc.)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata about the response (e.g., quest_draft status, tool calls made)"
    )
