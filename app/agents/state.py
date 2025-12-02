"""State management for LangGraph Agent

This module defines the TypedDict state structure used by the LangGraph agent
for managing conversation flow.
"""

from typing import TypedDict, List, Annotated
from langchain_core.messages import BaseMessage
from langgraph.graph import add_messages
from uuid import UUID


class AgentState(TypedDict):
    """State for the LangGraph ReAct agent"""
    messages: Annotated[List[BaseMessage], add_messages]
    user_id: UUID
    user_email: str
    user_type: str
    session_id: str
    tool_call_count: int
    max_tool_calls: int
