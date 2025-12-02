"""LangGraph StateGraph for ReAct Agent

This module implements the core ReAct (Reasoning + Acting) loop using LangGraph.
The agent alternates between reasoning (LLM) and acting (tool execution) until
the task is complete or the loop limit is reached.

Flow:
    START -> agent_node -> should_continue -> [tools_node OR END]
                ^                                    |
                |____________________________________|
"""

from typing import Literal, Dict, Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.services.ai_service import get_ai_service
from app.agents.state import AgentState, QuestDraft, WorkflowStage
from app.agents.tools.quest_tools import (
    collect_image_url,
    collect_location,
    analyze_waste_image,
    create_quest_in_database
)
from app.agents.tools.database_tools import (
    get_my_quests,
    get_my_transactions,
    get_quest_statistics
)
from app.agents.tools.search_tools import search_waste_information
from app.agents.tools.guardrails import check_relevance


def get_system_prompt(workflow_stage: WorkflowStage) -> str:
    """
    Generate context-aware system prompts based on current workflow stage.
    
    Args:
        workflow_stage: Current stage of the quest creation workflow
        
    Returns:
        System prompt string
    """
    base_prompt = """You are a helpful waste management assistant for the Solvio platform.
You help citizens create waste cleanup quests, track their progress, and provide information about waste management.

**Your Capabilities:**
1. **Quest Creation**: Guide users through creating waste cleanup quests
   - Collect image URL
   - Collect GPS coordinates
   - Analyze waste using AI
   - Create quest in database
   
2. **Data Access**: Help users query their own data
   - View their quests
   - Check their transactions
   - Get statistics about their activities
   
3. **Information**: Answer waste management questions using web search

**Important Guidelines:**
- Be conversational and friendly
- Keep responses concise and clear
- Always confirm before creating quests
- Users can only access their own data
- Stay focused on waste management topics
"""
    
    stage_prompts = {
        "idle": """
Currently not in any workflow. You can:
- Start a new quest creation by asking for the image URL
- Help users check their existing quests
- Answer waste management questions
""",
        "awaiting_image": """
**CURRENT STEP: Awaiting Image URL**
Ask the user for the waste image URL. The URL must start with http:// or https://.
Example: "Please provide the URL of the waste image you'd like to report."
""",
        "awaiting_location": """
**CURRENT STEP: Awaiting Location**
You have the image URL. Now ask for GPS coordinates (latitude and longitude).
Example: "Great! Now I need the location. Please provide the latitude and longitude coordinates."
""",
        "analyzing_image": """
**CURRENT STEP: Analyzing Image**
You have both image and location. Use the analyze_waste_image tool to get AI classification.
The tool will return a preview for the user to confirm.
""",
        "awaiting_confirmation": """
**CURRENT STEP: Awaiting Confirmation**
You've shown the user a preview of their quest. Ask them to confirm before creating it.
Example: "Does this look correct? Say 'yes' or 'confirm' to create the quest, or 'no' to start over."
""",
        "completed": """
**Quest Creation Completed!**
The quest has been created successfully. You can now help with other tasks or start a new quest.
"""
    }
    
    return base_prompt + stage_prompts.get(workflow_stage, stage_prompts["idle"])


async def agent_node(state: AgentState, session: AsyncSession, user: User) -> Dict[str, Any]:
    """
    Agent reasoning node - LLM decides what to do next.
    
    This node:
    1. Generates context-aware system prompt
    2. Invokes LLM with tools
    3. Updates tool call count
    4. Returns LLM response (may include tool calls)
    
    Args:
        state: Current agent state
        session: Database session (passed for context)
        user: Authenticated user (passed for context)
        
    Returns:
        Updated state dict
    """
    # Initialize LLM with Gemini 2.5 Flash
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=0.3,  # Balance between consistency and creativity
    )
    
    # Get all available tools
    tools = [
        collect_image_url,
        collect_location,
        # analyze_waste_image and create_quest_in_database need dependencies
        # They will be handled specially in tools_node
        get_my_quests,
        get_my_transactions,
        get_quest_statistics,
        search_waste_information,
        check_relevance,
    ]
    
    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Generate context-aware system prompt
    system_prompt = get_system_prompt(state["workflow_stage"])
    
    # Add context about quest draft if exists
    if state.get("quest_draft"):
        draft = state["quest_draft"]
        context_parts = []
        if draft.image_url:
            context_parts.append(f"Image URL: {draft.image_url}")
        if draft.location_lat and draft.location_lng:
            context_parts.append(f"Location: {draft.location_lat}, {draft.location_lng}")
        if draft.description:
            context_parts.append(f"Description: {draft.description}")
        
        if context_parts:
            system_prompt += f"\n\n**Current Quest Draft:**\n" + "\n".join(context_parts)
    
    # Build messages with system prompt
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    
    # Invoke LLM
    response = await llm_with_tools.ainvoke(messages)
    
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
    1. Extracts tool calls from last message
    2. Executes each tool with proper dependency injection
    3. Updates workflow stage based on tool results
    4. Updates quest draft based on tool results
    5. Returns tool responses
    
    Args:
        state: Current agent state
        session: Database session for database tools
        user: Authenticated user for authorization
        
    Returns:
        Updated state dict
    """
    last_message = state["messages"][-1]
    
    # Extract tool calls
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}
    
    tool_responses = []
    quest_draft = state.get("quest_draft") or QuestDraft()
    workflow_stage = state["workflow_stage"]
    
    ai_service = get_ai_service()
    
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]
        tool_id = tool_call["id"]
        
        try:
            # Execute tool with dependency injection
            if tool_name == "collect_image_url":
                result = collect_image_url.invoke(tool_args)
                if result["success"]:
                    quest_draft.image_url = result["image_url"]
                    workflow_stage = result["next_step"]
                
            elif tool_name == "collect_location":
                result = collect_location.invoke(tool_args)
                if result["success"]:
                    quest_draft.location_lat = result["latitude"]
                    quest_draft.location_lng = result["longitude"]
                    workflow_stage = result["next_step"]
                
            elif tool_name == "analyze_waste_image":
                # Inject AI service dependency
                result = await analyze_waste_image.ainvoke({
                    "image_url": quest_draft.image_url,
                    "ai_service": ai_service
                })
                if result["success"]:
                    quest_draft.description = result["description"]
                    quest_draft.waste_type = result["waste_type"]
                    quest_draft.severity = result["severity"]
                    quest_draft.confidence_score = result["confidence_score"]
                    quest_draft.bounty_points = result["bounty_points"]
                    workflow_stage = result["next_step"]
                
            elif tool_name == "create_quest_in_database":
                # Mark as confirmed if user approved
                quest_draft.user_confirmed = True
                
                # Inject dependencies
                result = await create_quest_in_database.ainvoke({
                    "quest_draft": quest_draft,
                    "user": user,
                    "session": session
                })
                if result["success"]:
                    workflow_stage = result["next_step"]
                    # Reset draft after successful creation
                    quest_draft = QuestDraft()
                
            elif tool_name == "get_my_quests":
                # Inject user_id and session
                result = await get_my_quests.ainvoke({
                    "user_id": str(state["user_id"]),
                    "session": session,
                    **tool_args
                })
                
            elif tool_name == "get_my_transactions":
                # Inject user_id and session
                result = await get_my_transactions.ainvoke({
                    "user_id": str(state["user_id"]),
                    "session": session,
                    **tool_args
                })
                
            elif tool_name == "get_quest_statistics":
                # Inject user_id and session
                result = await get_quest_statistics.ainvoke({
                    "user_id": str(state["user_id"]),
                    "session": session
                })
                
            elif tool_name == "search_waste_information":
                result = await search_waste_information.ainvoke(tool_args)
                
            elif tool_name == "check_relevance":
                result = check_relevance.invoke(tool_args)
                
            else:
                result = {"error": f"Unknown tool: {tool_name}"}
            
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
        "quest_draft": quest_draft,
        "workflow_stage": workflow_stage
    }


def should_continue(state: AgentState) -> Literal["tools", "end"]:
    """
    Routing logic to decide next step.
    
    Continues to tools if:
    1. Last message has tool calls
    2. Tool call count is below max limit
    
    Otherwise, ends the conversation turn.
    
    Args:
        state: Current agent state
        
    Returns:
        "tools" to continue to tools_node, "end" to finish
    """
    # Check tool call limit
    if state.get("tool_call_count", 0) >= state.get("max_tool_calls", 15):
        return "end"
    
    # Check if last message has tool calls
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    
    return "end"


def create_agent_graph(session: AsyncSession, user: User) -> StateGraph:
    """
    Create and compile the LangGraph StateGraph for the ReAct agent.
    
    The graph structure:
        START -> agent_node -> should_continue -> [tools_node OR END]
                    ^                                    |
                    |____________________________________|
    
    Args:
        session: Database session for tool execution
        user: Authenticated user for authorization
        
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create the graph
    workflow = StateGraph(AgentState)
    
    # Define nodes with dependency injection
    async def agent_with_deps(state: AgentState) -> Dict[str, Any]:
        return await agent_node(state, session, user)
    
    async def tools_with_deps(state: AgentState) -> Dict[str, Any]:
        return await tools_node(state, session, user)
    
    # Add nodes
    workflow.add_node("agent", agent_with_deps)
    workflow.add_node("tools", tools_with_deps)
    
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
    
    # Add edge from tools back to agent
    workflow.add_edge("tools", "agent")
    
    # Compile with memory checkpointer
    return workflow.compile(checkpointer=MemorySaver())
