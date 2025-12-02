"""Agent State Management for LangGraph ReAct Agent"""

from typing import Optional, List, Literal, Annotated
from typing_extensions import TypedDict
from uuid import UUID
from pydantic import BaseModel, Field
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


# Workflow stages for quest creation
WorkflowStage = Literal[
    "idle",
    "awaiting_image",
    "awaiting_location",
    "analyzing_image",
    "awaiting_confirmation",
    "completed"
]


class QuestDraft(BaseModel):
    """Draft quest being created through the agent conversation"""
    image_url: Optional[str] = None
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    description: Optional[str] = None
    waste_type: Optional[str] = None
    severity: Optional[str] = None
    confidence_score: Optional[float] = None
    bounty_points: Optional[int] = None
    user_confirmed: bool = False


class AgentState(TypedDict):
    """State for the LangGraph ReAct agent"""
    # Conversation history - uses add_messages for proper merging
    messages: Annotated[List[BaseMessage], add_messages]
    
    # User context from JWT authentication
    user_id: UUID
    user_email: str
    user_type: str  # Must be "CITIZEN"
    
    # Session tracking
    session_id: str
    
    # Quest creation workflow
    quest_draft: Optional[QuestDraft]
    workflow_stage: WorkflowStage
    
    # Safety limits
    tool_call_count: int
    max_tool_calls: int  # Default 15 to prevent infinite loops
