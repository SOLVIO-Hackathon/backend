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

import pygeohash
from geoalchemy2.shape import from_shape
from shapely.geometry import Point

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import User
from app.models.quest import Quest, WasteType, Severity, QuestStatus
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
    
    # Get simple tools that don't need dependency injection
    # Complex tools (analyze_waste_image, create_quest_in_database) are handled in tools_node
    tools = [
        collect_image_url,
        collect_location,
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
            context_parts.append(f"Waste Type: {draft.waste_type}")
            context_parts.append(f"Severity: {draft.severity}")
            context_parts.append(f"Bounty Points: {draft.bounty_points}")
        
        if context_parts:
            system_prompt += f"\n\n**Current Quest Draft:**\n" + "\n".join(context_parts)
    
    # Add special instructions based on workflow stage
    if state["workflow_stage"] == "analyzing_image":
        # We have image and location, tell the agent to proceed with analysis
        system_prompt += "\n\n**ACTION REQUIRED:** The user has provided both image URL and location. Proceed to analyze the image and show the preview to the user."
    elif state["workflow_stage"] == "awaiting_confirmation":
        # We have the analysis, ask for confirmation
        system_prompt += "\n\n**ACTION REQUIRED:** The image has been analyzed. Show the preview to the user and ask them to confirm (yes/confirm) or restart (no/cancel)."
    
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
    Tool execution node - executes tools requested by LLM or performs workflow actions.

    This node:
    1. Handles workflow-based automatic actions (analyze image, create quest)
    2. Executes simple tools called by the LLM
    3. Updates workflow stage based on results
    4. Updates quest draft based on results
    5. Returns tool responses

    Args:
        state: Current agent state
        session: Database session for database tools
        user: Authenticated user for authorization

    Returns:
        Updated state dict
    """
    import re

    tool_responses = []
    quest_draft = state.get("quest_draft") or QuestDraft()
    workflow_stage = state["workflow_stage"]

    # Auto-extract data from user messages
    if state["messages"]:
        last_msg = state["messages"][-1]
        if hasattr(last_msg, "content"):
            content = last_msg.content
            content_lower = content.lower()

            # Check if user wants to start reporting waste
            if workflow_stage == "idle" and any(keyword in content_lower for keyword in ["report", "waste", "i want to", "found"]):
                workflow_stage = "awaiting_image"
                tool_responses.append(AIMessage(content="Great! To start a new waste cleanup quest, I'll need a picture of the waste. Can you please provide the image URL?"))

            # Extract image URL if in awaiting_image stage
            elif workflow_stage == "awaiting_image" and not quest_draft.image_url:
                url_match = re.search(r'https?://[^\s<>"]+', content)
                if url_match:
                    image_url = url_match.group(0)
                    quest_draft.image_url = image_url
                    workflow_stage = "awaiting_location"
                    tool_responses.append(AIMessage(content=f"Got it! Image received. Now I need the location coordinates (latitude and longitude)."))

            # Extract location coordinates if in awaiting_location stage
            elif workflow_stage == "awaiting_location" and not quest_draft.location_lat:
                # Try to extract coordinates from various formats
                # Format 1: [Location captured via GPS: 23.790720, 90.405645]
                coord_match1 = re.search(r'Location.*?:\s*(-?\d+\.?\d*),\s*(-?\d+\.?\d*)', content, re.IGNORECASE)
                # Format 2: lat: 23.790720, lng: 90.405645
                coord_match2 = re.search(r'lat.*?:\s*(-?\d+\.?\d*)[,\s]+l(?:ng|on).*?:\s*(-?\d+\.?\d*)', content, re.IGNORECASE)
                # Format 3: simple coordinates 23.790720, 90.405645
                coord_match3 = re.search(r'(-?\d+\.?\d{4,}),\s*(-?\d+\.?\d{4,})', content)

                coord_match = coord_match1 or coord_match2 or coord_match3

                if coord_match:
                    try:
                        lat = float(coord_match.group(1))
                        lng = float(coord_match.group(2))

                        # Validate ranges
                        if -90 <= lat <= 90 and -180 <= lng <= 180:
                            quest_draft.location_lat = lat
                            quest_draft.location_lng = lng
                            workflow_stage = "analyzing_image"
                            tool_responses.append(AIMessage(content=f"Perfect! Location received ({lat:.6f}, {lng:.6f}). Let me analyze the waste image..."))
                    except ValueError:
                        pass

    # Handle workflow-based automatic actions first
    if workflow_stage == "analyzing_image" and quest_draft.image_url and quest_draft.location_lat:
        # Automatically analyze the image
        try:
            ai_service = get_ai_service()
            classification = await ai_service.classify_waste(
                image_url=quest_draft.image_url,
                additional_context=None
            )
            
            # Generate description from detected items
            items_str = ", ".join(classification.detected_items[:3])
            description = f"{classification.estimated_volume} of {items_str}"
            if len(classification.detected_items) > 3:
                description += f" and {len(classification.detected_items) - 3} more items"
            
            # Calculate bounty points based on waste type
            waste_type = classification.waste_type.value
            bounty_map = {"organic": 20, "recyclable": 50, "general": 30, "e_waste": 100}
            bounty_points = bounty_map.get(waste_type, 30)
            
            # Update quest draft
            quest_draft.description = description
            quest_draft.waste_type = waste_type
            quest_draft.severity = classification.severity.value
            quest_draft.confidence_score = classification.confidence_score
            quest_draft.bounty_points = bounty_points
            workflow_stage = "awaiting_confirmation"
            
            # Create preview message
            preview = f"""
**Quest Preview:**
📸 **Description:** {description}
🗑️ **Waste Type:** {classification.waste_type.value.replace('_', ' ').title()}
⚠️ **Severity:** {classification.severity.value.title()}
💰 **Bounty Points:** {bounty_points}
🎯 **AI Confidence:** {classification.confidence_score:.1%}

Does this look correct? Please say 'yes' or 'confirm' to create the quest, or 'no' to start over.
"""
            
            tool_responses.append(AIMessage(content=preview))
            
        except Exception as e:
            error_msg = f"Failed to analyze image: {str(e)}. Please try again with a different image."
            tool_responses.append(AIMessage(content=error_msg))
            workflow_stage = "awaiting_image"
            quest_draft = QuestDraft()
    
    # Check if user confirmed the quest
    elif workflow_stage == "awaiting_confirmation" and quest_draft.description:
        last_msg = state["messages"][-1].content.lower() if state["messages"] else ""
        
        if any(word in last_msg for word in ["yes", "confirm", "ok", "correct", "proceed"]):
            # User confirmed - create the quest
            try:
                # Calculate geohash
                geohash = pygeohash.encode(
                    quest_draft.location_lat,
                    quest_draft.location_lng,
                    precision=8
                )
                ward_geohash = geohash[:5]
                
                # Create Point geometry
                point = Point(quest_draft.location_lng, quest_draft.location_lat)
                location_geom = from_shape(point, srid=4326)
                
                # Generate title
                title = quest_draft.description[:100] + "..." if len(quest_draft.description) > 100 else quest_draft.description
                
                # Create Quest
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
                
                session.add(new_quest)
                await session.commit()
                await session.refresh(new_quest)
                
                success_msg = f"✅ Quest created successfully!\n\n**Quest ID:** {new_quest.id}\n**Bounty Points:** {quest_draft.bounty_points}\n\nYour quest has been reported and is now available for collectors to accept. You'll be notified when a collector starts working on it!"
                tool_responses.append(AIMessage(content=success_msg))
                
                # Reset draft and workflow
                quest_draft = QuestDraft()
                workflow_stage = "idle"
                
            except Exception as e:
                error_msg = f"Failed to create quest: {str(e)}. Please try again."
                tool_responses.append(AIMessage(content=error_msg))
                workflow_stage = "awaiting_confirmation"
                
        elif any(word in last_msg for word in ["no", "cancel", "restart", "wrong"]):
            # User wants to restart
            quest_draft = QuestDraft()
            workflow_stage = "idle"
            tool_responses.append(AIMessage(content="No problem! Let's start over. What would you like to do?"))
    
    # Handle tool calls from LLM
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            try:
                # Execute simple tools
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
    1. Last message has tool calls (from LLM), OR
    2. Last message is from user (HumanMessage) and we need to extract/process data
    3. Workflow stage requires automatic action (analyzing_image)

    Otherwise, ends the conversation turn.

    Args:
        state: Current agent state

    Returns:
        "tools" to continue to tools_node, "end" to finish
    """
    from langchain_core.messages import HumanMessage

    # Check tool call limit
    if state.get("tool_call_count", 0) >= state.get("max_tool_calls", 15):
        return "end"

    # Get last message
    last_message = state["messages"][-1]

    # Check if last message has tool calls from LLM
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"

    # Only process user messages (HumanMessage) for extraction
    if isinstance(last_message, HumanMessage):
        workflow_stage = state.get("workflow_stage", "idle")
        content_lower = last_message.content.lower()

        # Check if user wants to start a quest in idle state
        if workflow_stage == "idle":
            if any(keyword in content_lower for keyword in ["report", "waste", "i want to", "found", "cleanup", "quest"]):
                return "tools"

        # Extract data if waiting for image or location
        elif workflow_stage == "awaiting_image":
            # Check if message contains a URL
            import re
            if re.search(r'https?://', content_lower):
                return "tools"

        elif workflow_stage == "awaiting_location":
            # Check if message contains coordinates
            import re
            if re.search(r'(-?\d+\.?\d+)[,\s]+(-?\d+\.?\d+)', content_lower):
                return "tools"

        elif workflow_stage == "awaiting_confirmation":
            # Check for confirmation/rejection
            if any(word in content_lower for word in ["yes", "confirm", "ok", "correct", "proceed", "no", "cancel", "restart"]):
                return "tools"

    # Auto-analyze image if we have both image and location
    workflow_stage = state.get("workflow_stage", "idle")
    if workflow_stage == "analyzing_image":
        quest_draft = state.get("quest_draft")
        if quest_draft and quest_draft.image_url and quest_draft.location_lat:
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
    
    # Add conditional edges from agent
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "end": END
        }
    )

    # Tools node ends directly - no loop back to agent
    # This prevents infinite loops where tools_node adds a response and we're done
    workflow.add_edge("tools", END)
    
    # Compile with memory checkpointer
    return workflow.compile(checkpointer=MemorySaver())
