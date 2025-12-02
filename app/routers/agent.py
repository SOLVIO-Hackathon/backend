"""Agent Router - HTTP POST API for ReAct Agent

This module provides the HTTP endpoint for interacting with the ReAct agent.
Users send messages via HTTP POST with JWT authentication, and the agent
responds using the LangGraph workflow.
"""

from typing import Dict, Any
from uuid import uuid4
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from langchain_core.messages import HumanMessage, AIMessage

from app.core.auth import get_current_active_user
from app.core.database import get_async_session
from app.models.user import User, UserType
from app.schemas.agent import AgentChatRequest, AgentChatResponse
from app.agents.graph import create_agent_graph
from app.agents.state import AgentState, QuestDraft


# Router configuration
router = APIRouter(
    prefix="/agent",
    tags=["ReAct Agent"],
    responses={404: {"description": "Not found"}},
)


# In-memory session storage
# Format: {session_id: {state: AgentState, last_accessed: datetime}}
_session_storage: Dict[str, Dict[str, Any]] = {}


# Session timeout (1 hour)
SESSION_TIMEOUT = timedelta(hours=1)


def cleanup_old_sessions():
    """Remove sessions older than SESSION_TIMEOUT"""
    now = datetime.utcnow()
    expired_sessions = [
        session_id
        for session_id, data in _session_storage.items()
        if now - data["last_accessed"] > SESSION_TIMEOUT
    ]
    for session_id in expired_sessions:
        del _session_storage[session_id]


def load_or_create_session(session_id: str, current_user: User) -> Dict[str, Any]:
    """
    Load existing session or create a new one.
    
    Args:
        session_id: Session identifier
        current_user: Authenticated user
        
    Returns:
        Session data dictionary
    """
    # Cleanup old sessions periodically
    cleanup_old_sessions()
    
    if session_id in _session_storage:
        # Load existing session
        session_data = _session_storage[session_id]
        
        # Verify session belongs to this user
        if str(session_data["state"]["user_id"]) != str(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Session belongs to another user"
            )
        
        # Update last accessed time
        session_data["last_accessed"] = datetime.utcnow()
        return session_data
    
    # Create new session
    initial_state: AgentState = {
        "messages": [],
        "user_id": current_user.id,
        "user_email": current_user.email,
        "user_type": current_user.user_type.value,
        "session_id": session_id,
        "quest_draft": None,
        "workflow_stage": "idle",
        "tool_call_count": 0,
        "max_tool_calls": 15
    }
    
    session_data = {
        "state": initial_state,
        "last_accessed": datetime.utcnow()
    }
    
    _session_storage[session_id] = session_data
    return session_data


def save_session(session_id: str, state: AgentState):
    """
    Save session state.
    
    Args:
        session_id: Session identifier
        state: Updated agent state
    """
    if session_id in _session_storage:
        _session_storage[session_id]["state"] = state
        _session_storage[session_id]["last_accessed"] = datetime.utcnow()


@router.post("/chat", response_model=AgentChatResponse)
async def agent_chat(
    request: AgentChatRequest,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    """
    Chat with the ReAct agent to create quests, query data, and get information.
    
    **Authentication:** Requires JWT Bearer token in Authorization header.
    
    **User Type:** Only CITIZEN users can use this endpoint.
    
    **Features:**
    - Multi-step quest creation workflow
    - Query your own quests and transactions
    - Search for waste management information
    - Conversational interface
    
    **Example Flow:**
    1. POST with message: "I want to report waste"
    2. Agent asks for image URL
    3. POST with image URL
    4. Agent asks for location
    5. POST with coordinates
    6. Agent analyzes image and shows preview
    7. POST "yes" to confirm and create quest
    
    **Session Management:**
    - First request: Don't provide session_id, agent will create one
    - Subsequent requests: Use session_id from previous response
    - Sessions expire after 1 hour of inactivity
    """
    # Verify user type
    if current_user.user_type != UserType.CITIZEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only citizens can use this agent. This endpoint is for reporting waste and creating quests."
        )
    
    # Validate message length
    if len(request.message) > 5000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message too long. Maximum 5000 characters allowed."
        )
    
    # Get or create session
    session_id = request.session_id or str(uuid4())
    
    try:
        session_data = load_or_create_session(session_id, current_user)
        agent_state = session_data["state"]
        
        # Add user message to state
        agent_state["messages"].append(HumanMessage(content=request.message))
        
        # Create and run agent graph
        graph = create_agent_graph(session, current_user)
        
        # Run the agent with the updated state
        # LangGraph will handle the conversation flow
        config = {"configurable": {"thread_id": session_id}}
        result = await graph.ainvoke(agent_state, config=config)
        
        # Extract the agent's response (last AI message)
        agent_response = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage):
                agent_response = msg.content
                break
        
        if not agent_response:
            agent_response = "I'm here to help! How can I assist you with waste management today?"
        
        # Save updated state
        save_session(session_id, result)
        
        # Prepare metadata
        metadata = {
            "tool_call_count": result.get("tool_call_count", 0),
            "max_tool_calls": result.get("max_tool_calls", 15),
        }
        
        # Add quest draft info if exists
        if result.get("quest_draft"):
            draft = result["quest_draft"]
            metadata["quest_draft"] = {
                "has_image": draft.image_url is not None,
                "has_location": draft.location_lat is not None and draft.location_lng is not None,
                "has_analysis": draft.description is not None,
                "confirmed": draft.user_confirmed
            }
        
        return AgentChatResponse(
            response=agent_response,
            session_id=session_id,
            workflow_stage=result["workflow_stage"],
            metadata=metadata
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Handle unexpected errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent error: {str(e)}"
        )


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """
    Delete a chat session.
    
    Use this to clear conversation history and start fresh.
    Sessions are automatically deleted after 1 hour of inactivity.
    """
    if session_id not in _session_storage:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    # Verify session belongs to this user
    session_data = _session_storage[session_id]
    if str(session_data["state"]["user_id"]) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session belongs to another user"
        )
    
    # Delete session
    del _session_storage[session_id]
    
    return {"message": "Session deleted successfully"}


@router.get("/sessions")
async def list_sessions(
    current_user: User = Depends(get_current_active_user)
):
    """
    List all active sessions for the current user.
    
    Useful for debugging or managing multiple conversations.
    """
    # Cleanup old sessions first
    cleanup_old_sessions()
    
    # Find user's sessions
    user_sessions = []
    for session_id, data in _session_storage.items():
        if str(data["state"]["user_id"]) == str(current_user.id):
            user_sessions.append({
                "session_id": session_id,
                "workflow_stage": data["state"]["workflow_stage"],
                "message_count": len(data["state"]["messages"]),
                "last_accessed": data["last_accessed"].isoformat()
            })
    
    return {
        "count": len(user_sessions),
        "sessions": user_sessions
    }
