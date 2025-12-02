"""LangGraph StateGraph for ReAct Agent

This module implements a simple ReAct (Reasoning + Acting) loop using LangGraph.
The agent can answer questions and query database information.

Flow:
    START -> agent_node -> should_continue -> [tools_node OR END]
                ^                                    |
                |____________________________________|
"""

from typing import Literal, Dict, Any

from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.agents.state import AgentState
from app.agents.tools.database_tools import (
    get_my_quests,
    get_my_transactions,
    get_quest_statistics,
    _get_my_quests_impl,
    _get_my_transactions_impl,
    _get_quest_statistics_impl
)
from app.agents.tools.search_tools import search_waste_information


# System prompt for the agent
SYSTEM_PROMPT = """You are a helpful waste management assistant for the Solvio platform.
You help citizens with waste management questions and can query their data.

**What you can do:**
1. Answer waste management and recycling questions
2. Query user's quest data (their reported waste cleanup tasks)
3. Provide statistics about user's quests and bounty points
4. Provide general advice about waste disposal and recycling

**Guidelines:**
- Be friendly, helpful, and encouraging
- Keep responses concise and clear
- If asked about something off-topic, politely redirect to waste management topics
- Use the database tools to answer questions about the user's data
- Use search tools for specific waste management information

**Available Tools:**
- get_my_quests: View quests created by the user
- get_quest_statistics: Get user's quest statistics and bounty points
- get_my_transactions: View user's payment history
- search_waste_information: Search for waste management information online

Remember: You're here to help with waste management. Stay on topic!
"""


# Initialize LLM
def get_llm():
    """Get the configured LLM instance"""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.7,
    )


async def agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Agent reasoning node - uses LLM to decide what to do next.

    This node:
    1. Takes conversation history from state
    2. Sends to Gemini with available tools
    3. Gets response (either text or tool calls)
    4. Returns updated messages and tool call count

    Args:
        state: Current agent state

    Returns:
        Updated state dict with new messages
    """
    # Get messages from state
    messages = state["messages"]

    # Add system prompt if this is the first turn
    if not any(isinstance(msg, SystemMessage) for msg in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    # Filter out messages with empty content for Gemini
    filtered_messages = []
    for msg in messages:
        # Skip ToolMessages and messages with empty content
        if isinstance(msg, ToolMessage):
            filtered_messages.append(msg)
        elif hasattr(msg, "content") and msg.content:
            filtered_messages.append(msg)
        elif isinstance(msg, AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            # AIMessage with tool calls but no content - add placeholder content
            new_msg = AIMessage(content="[Using tools]", tool_calls=msg.tool_calls)
            filtered_messages.append(new_msg)
            print("[AGENT] Fixed AIMessage with empty content but tool calls")

    print(f"[AGENT] Sending {len(filtered_messages)} messages to Gemini:")
    for i, msg in enumerate(filtered_messages):
        msg_type = type(msg).__name__
        content_preview = msg.content[:100] if hasattr(msg, "content") and msg.content else "(no content)"
        print(f"  [{i}] {msg_type}: {content_preview}...")

    # Get LLM with tools
    llm = get_llm()
    tools = [get_my_quests, get_quest_statistics, get_my_transactions, search_waste_information]
    llm_with_tools = llm.bind_tools(tools)

    # Invoke LLM
    response = await llm_with_tools.ainvoke(filtered_messages)

    # Increment tool call count if tools were called
    tool_call_count = state.get("tool_call_count", 0)
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_call_count += len(response.tool_calls)

    return {
        "messages": [response],
        "tool_call_count": tool_call_count
    }


async def tools_node(state: AgentState, session: AsyncSession, user: User) -> Dict[str, Any]:
    """
    Tool execution node - executes tools requested by LLM.

    This node:
    1. Executes database query tools with dependency injection
    2. Returns tool responses

    Args:
        state: Current agent state
        session: Database session for database tools
        user: Authenticated user for authorization

    Returns:
        Updated state dict
    """
    tool_responses = []

    # Handle tool calls from LLM
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call.get("args", {})
            tool_id = tool_call["id"]

            try:
                # Execute database tools with dependency injection
                if tool_name == "get_my_quests":
                    result = await _get_my_quests_impl(
                        user_id=str(user.id),
                        session=session,
                        status=tool_args.get("status"),
                        limit=tool_args.get("limit", 5)
                    )
                elif tool_name == "get_quest_statistics":
                    result = await _get_quest_statistics_impl(
                        user_id=str(user.id),
                        session=session
                    )
                elif tool_name == "get_my_transactions":
                    result = await _get_my_transactions_impl(
                        user_id=str(user.id),
                        session=session
                    )
                elif tool_name == "search_waste_information":
                    # Execute search tool (doesn't need injection)
                    result = await search_waste_information.ainvoke(tool_args)
                else:
                    result = f"Unknown tool: {tool_name}"

                # Create tool message
                tool_message = ToolMessage(
                    content=str(result),
                    tool_call_id=tool_id,
                    name=tool_name
                )
                tool_responses.append(tool_message)

            except Exception as e:
                # Handle tool execution errors
                error_message = ToolMessage(
                    content=f"Error executing {tool_name}: {str(e)}",
                    tool_call_id=tool_id,
                    name=tool_name
                )
                tool_responses.append(error_message)

    return {
        "messages": tool_responses,
    }


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Routing logic to decide next step.

    Continues to tools if:
    1. Last message has tool calls (from LLM)

    Otherwise, ends the conversation turn.

    Args:
        state: Current agent state

    Returns:
        "tools" to continue to tools_node, "end" to finish
    """
    # Check tool call limit
    if state.get("tool_call_count", 0) >= state.get("max_tool_calls", 15):
        print("[ROUTING] Tool call limit reached, ending")
        return "end"

    # Get last message
    last_message = state["messages"][-1]
    print(f"[ROUTING] Last message type: {type(last_message).__name__}")

    # Check if last message has tool calls from LLM
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    return "end"


def create_agent_graph(session: AsyncSession, user: User):
    """
    Create the LangGraph StateGraph for the ReAct agent.

    Args:
        session: Database session for tools
        user: Authenticated user

    Returns:
        Compiled StateGraph
    """
    # Create graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("agent", agent_node)

    # Create tools_node with dependency injection
    async def tools_node_with_deps(state: AgentState) -> Dict[str, Any]:
        return await tools_node(state, session, user)

    workflow.add_node("tools", tools_node_with_deps)

    # Set entry point
    workflow.set_entry_point("agent")

    # Add conditional edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )

    # After tools, always go back to agent
    workflow.add_edge("tools", "agent")

    # Compile with checkpointer for memory
    checkpointer = MemorySaver()
    app = workflow.compile(checkpointer=checkpointer)

    return app
