"""Guardrail tools for filtering off-topic queries"""

from langchain_core.tools import tool


@tool
def check_relevance(user_message: str) -> str:
    """
    Check if user message is relevant to waste management.

    Args:
        user_message: Message from the user

    Returns:
        Relevance assessment
    """
    return f"Checking relevance of: {user_message}"
