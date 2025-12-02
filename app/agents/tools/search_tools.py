"""Web search tools for the agent"""

from langchain_core.tools import tool


@tool
def search_waste_information(query: str) -> str:
    """
    Search for waste management information on the web.

    Args:
        query: Search query about waste management

    Returns:
        Search results
    """
    return f"Searching for: {query}"
