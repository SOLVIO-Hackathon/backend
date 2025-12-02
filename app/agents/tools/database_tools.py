"""Database query tools for the agent

NOTE: These tools are designed to work with dependency injection.
The session and user_id parameters are injected by the graph's tools_node.
"""

from langchain_core.tools import tool
from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.quest import Quest, QuestStatus


@tool
async def get_my_quests(status: Optional[str] = None, limit: int = 5) -> str:
    """
    Get quests created by the current user.

    This tool automatically uses the authenticated user's ID from the session context.

    Args:
        status: Optional status filter (pending, in_progress, completed, cancelled)
        limit: Maximum number of quests to return (default: 5)

    Returns:
        List of user's quests
    """
    # Note: user_id and session will be injected by tools_node
    # This is just a placeholder - the actual implementation is in graph.py tools_node
    return "Tool requires session injection"


async def _get_my_quests_impl(user_id: str, session: AsyncSession, status: Optional[str] = None, limit: int = 5) -> str:
    """
    Internal implementation of get_my_quests with session injection.

    Args:
        user_id: ID of the current user
        session: Database session
        status: Optional status filter (pending, in_progress, completed, cancelled)
        limit: Maximum number of quests to return (default: 5)

    Returns:
        List of user's quests
    """
    try:
        # Build query
        query = select(Quest).where(Quest.reporter_id == UUID(user_id))

        # Apply status filter if provided
        if status:
            try:
                status_enum = QuestStatus(status.lower())
                query = query.where(Quest.status == status_enum)
            except ValueError:
                pass  # Ignore invalid status

        # Order by creation date (most recent first) and limit
        query = query.order_by(Quest.created_at.desc()).limit(limit)

        # Execute query
        result = await session.execute(query)
        quests = result.scalars().all()

        if not quests:
            return f"You haven't created any quests yet{' with status ' + status if status else ''}."

        # Format response
        quest_list = []
        for quest in quests:
            quest_info = (
                f"• Quest #{quest.id.hex[:8]}\n"
                f"  Description: {quest.description}\n"
                f"  Type: {quest.waste_type.value if quest.waste_type else 'N/A'}\n"
                f"  Status: {quest.status.value}\n"
                f"  Bounty: {quest.bounty_points} points\n"
                f"  Created: {quest.created_at.strftime('%Y-%m-%d %H:%M')}"
            )
            quest_list.append(quest_info)

        header = f"Found {len(quests)} quest(s){' with status ' + status if status else ''}:\n\n"
        return header + "\n\n".join(quest_list)

    except Exception as e:
        return f"Error fetching quests: {str(e)}"


@tool
async def get_my_transactions() -> str:
    """
    Get payment transactions for the current user.

    This tool automatically uses the authenticated user's ID from the session context.

    Returns:
        List of user's transactions
    """
    return "Tool requires session injection"


async def _get_my_transactions_impl(user_id: str, session: AsyncSession) -> str:
    """
    Internal implementation of get_my_transactions with session injection.

    Args:
        user_id: ID of the current user
        session: Database session

    Returns:
        List of user's transactions
    """
    # Placeholder - implement when transaction model is available
    return "Transaction history feature coming soon!"


@tool
async def get_quest_statistics() -> str:
    """
    Get quest statistics for the current user.

    This tool automatically uses the authenticated user's ID from the session context.

    Returns:
        Statistics about user's quests and bounty points
    """
    return "Tool requires session injection"


async def _get_quest_statistics_impl(user_id: str, session: AsyncSession) -> str:
    """
    Internal implementation of get_quest_statistics with session injection.

    Args:
        user_id: ID of the current user
        session: Database session

    Returns:
        Statistics about user's quests and bounty points
    """
    try:
        # Count quests by status
        query = select(
            Quest.status,
            func.count(Quest.id).label('count'),
            func.sum(Quest.bounty_points).label('total_bounty')
        ).where(
            Quest.reporter_id == UUID(user_id)
        ).group_by(Quest.status)

        result = await session.execute(query)
        stats = result.all()

        # Format statistics
        total_quests = 0
        total_bounty = 0
        status_breakdown = []

        for status, count, bounty in stats:
            total_quests += count
            total_bounty += (bounty or 0)
            status_breakdown.append(f"  {status.value.replace('_', ' ').title()}: {count} quest(s)")

        if total_quests == 0:
            return "You haven't created any quests yet."

        response = f"""Your Quest Statistics:

📊 Total Quests: {total_quests}
💰 Total Bounty Points: {total_bounty}

Status Breakdown:
{chr(10).join(status_breakdown)}"""

        return response

    except Exception as e:
        return f"Error fetching statistics: {str(e)}"
