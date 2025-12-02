"""Database Query Tools for ReAct Agent

CRITICAL SECURITY: All database queries MUST filter by authenticated user's user_id.
Users can ONLY access their own data - enforced at the query level.

Tools:
1. get_my_quests - Query user's own quests (reporter_id = user_id)
2. get_my_transactions - Query user's own transactions (user_id = user_id)
3. get_quest_statistics - Get statistics for user's own quests
"""

from typing import Dict, Any, List, Optional
from uuid import UUID

from langchain_core.tools import tool
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.sql import text

from app.models.quest import Quest, QuestStatus
from app.models.transaction import Transaction


@tool
async def get_my_quests(
    user_id: str,
    session: AsyncSession,
    status_filter: Optional[str] = None,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Get the authenticated user's own quests.
    
    SECURITY: Only returns quests where reporter_id = user_id.
    User can ONLY see quests they reported.
    
    Args:
        user_id: UUID of authenticated user
        session: Database session
        status_filter: Optional filter by quest status (reported, assigned, completed, etc.)
        limit: Maximum number of quests to return (default 10, max 50)
        
    Returns:
        Dictionary with list of user's quests
    """
    try:
        # Convert user_id string to UUID
        user_uuid = UUID(user_id)
        
        # Limit to max 50
        limit = min(limit, 50)
        
        # CRITICAL: Always filter by reporter_id = user_id
        query = select(Quest).where(Quest.reporter_id == user_uuid)
        
        # Apply status filter if provided
        if status_filter:
            try:
                status_enum = QuestStatus(status_filter.lower())
                query = query.where(Quest.status == status_enum)
            except ValueError:
                return {
                    "success": False,
                    "error": f"Invalid status filter: {status_filter}. Valid values: reported, assigned, in_progress, completed, verified, rejected"
                }
        
        # Order by creation date (newest first) and apply limit
        query = query.order_by(Quest.created_at.desc()).limit(limit)
        
        # Execute query
        result = await session.execute(query)
        quests = result.scalars().all()
        
        # Format quests for display
        formatted_quests = []
        for quest in quests:
            # Extract coordinates from PostGIS geometry
            coords_query = select(
                func.ST_X(Quest.location).label('lng'),
                func.ST_Y(Quest.location).label('lat')
            ).where(Quest.id == quest.id)
            coords_result = await session.execute(coords_query)
            coords = coords_result.first()
            
            formatted_quests.append({
                "quest_id": str(quest.id),
                "title": quest.title,
                "description": quest.description,
                "waste_type": quest.waste_type.value,
                "severity": quest.severity.value,
                "status": quest.status.value,
                "bounty_points": quest.bounty_points,
                "location": {
                    "lat": coords.lat if coords else None,
                    "lng": coords.lng if coords else None
                },
                "created_at": quest.created_at.isoformat() if quest.created_at else None,
                "completed_at": quest.completed_at.isoformat() if quest.completed_at else None
            })
        
        # Format response
        if not formatted_quests:
            message = "You have no quests yet."
            if status_filter:
                message = f"You have no quests with status '{status_filter}'."
        else:
            count = len(formatted_quests)
            status_msg = f" with status '{status_filter}'" if status_filter else ""
            message = f"Found {count} quest(s){status_msg}:"
        
        return {
            "success": True,
            "message": message,
            "count": len(formatted_quests),
            "quests": formatted_quests
        }
        
    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid user_id format: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch quests: {str(e)}"
        }


@tool
async def get_my_transactions(
    user_id: str,
    session: AsyncSession,
    limit: int = 10
) -> Dict[str, Any]:
    """
    Get the authenticated user's own transactions.
    
    SECURITY: Only returns transactions where user_id = user_id.
    User can ONLY see their own transactions.
    
    Args:
        user_id: UUID of authenticated user
        session: Database session
        limit: Maximum number of transactions to return (default 10, max 50)
        
    Returns:
        Dictionary with list of user's transactions
    """
    try:
        # Convert user_id string to UUID
        user_uuid = UUID(user_id)
        
        # Limit to max 50
        limit = min(limit, 50)
        
        # CRITICAL: Always filter by user_id = user_id
        query = select(Transaction).where(
            Transaction.user_id == user_uuid
        ).order_by(Transaction.created_at.desc()).limit(limit)
        
        # Execute query
        result = await session.execute(query)
        transactions = result.scalars().all()
        
        # Format transactions for display
        formatted_transactions = []
        for txn in transactions:
            formatted_transactions.append({
                "transaction_id": str(txn.id),
                "type": txn.transaction_type.value,
                "amount": float(txn.amount),
                "currency": txn.currency,
                "status": txn.payment_status.value,
                "payment_method": txn.payment_method.value,
                "quest_id": str(txn.quest_id) if txn.quest_id else None,
                "listing_id": str(txn.listing_id) if txn.listing_id else None,
                "created_at": txn.created_at.isoformat() if txn.created_at else None
            })
        
        # Format response
        if not formatted_transactions:
            message = "You have no transactions yet."
        else:
            count = len(formatted_transactions)
            total_amount = sum(float(t.amount) for t in transactions)
            message = f"Found {count} transaction(s). Total amount: {total_amount:.2f} BDT"
        
        return {
            "success": True,
            "message": message,
            "count": len(formatted_transactions),
            "transactions": formatted_transactions
        }
        
    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid user_id format: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch transactions: {str(e)}"
        }


@tool
async def get_quest_statistics(
    user_id: str,
    session: AsyncSession
) -> Dict[str, Any]:
    """
    Get statistics for the authenticated user's own quests.
    
    SECURITY: Only calculates statistics for quests where reporter_id = user_id.
    User can ONLY see statistics for their own quests.
    
    Args:
        user_id: UUID of authenticated user
        session: Database session
        
    Returns:
        Dictionary with quest statistics
    """
    try:
        # Convert user_id string to UUID
        user_uuid = UUID(user_id)
        
        # CRITICAL: Always filter by reporter_id = user_id
        # Count total quests
        total_query = select(func.count(Quest.id)).where(
            Quest.reporter_id == user_uuid
        )
        total_result = await session.execute(total_query)
        total_quests = total_result.scalar() or 0
        
        # Count by status
        status_query = select(
            Quest.status,
            func.count(Quest.id).label('count')
        ).where(
            Quest.reporter_id == user_uuid
        ).group_by(Quest.status)
        status_result = await session.execute(status_query)
        status_counts = {row.status.value: row.count for row in status_result}
        
        # Calculate total bounty (sum of all quests)
        bounty_query = select(
            func.sum(Quest.bounty_points)
        ).where(
            Quest.reporter_id == user_uuid
        )
        bounty_result = await session.execute(bounty_query)
        total_bounty = bounty_result.scalar() or 0
        
        # Calculate earned bounty (completed and verified quests only)
        earned_query = select(
            func.sum(Quest.bounty_points)
        ).where(
            Quest.reporter_id == user_uuid,
            Quest.status.in_([QuestStatus.COMPLETED, QuestStatus.VERIFIED])
        )
        earned_result = await session.execute(earned_query)
        earned_bounty = earned_result.scalar() or 0
        
        # Format statistics
        stats = {
            "total_quests": total_quests,
            "status_breakdown": status_counts,
            "total_bounty_potential": int(total_bounty),
            "earned_bounty": int(earned_bounty),
            "completed_quests": status_counts.get("completed", 0) + status_counts.get("verified", 0),
            "pending_quests": status_counts.get("reported", 0) + status_counts.get("assigned", 0) + status_counts.get("in_progress", 0)
        }
        
        # Format message
        message = f"""
**Your Quest Statistics:**
📊 Total Quests: {stats['total_quests']}
✅ Completed: {stats['completed_quests']}
⏳ Pending: {stats['pending_quests']}
💰 Earned Bounty: {stats['earned_bounty']} points
🎯 Potential Bounty: {stats['total_bounty_potential']} points
"""
        
        return {
            "success": True,
            "message": message.strip(),
            "statistics": stats
        }
        
    except ValueError as e:
        return {
            "success": False,
            "error": f"Invalid user_id format: {str(e)}"
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to fetch statistics: {str(e)}"
        }
