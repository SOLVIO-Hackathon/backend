"""Quest creation tools for the agent

These are stub tools that are not actually used since the graph.py
handles quest creation directly through auto-extraction from messages.
"""

from langchain_core.tools import tool


@tool
def collect_image_url(image_url: str) -> str:
    """
    Collect waste image URL from user.

    Args:
        image_url: URL of the waste image

    Returns:
        Confirmation message
    """
    return f"Image URL collected: {image_url}"


@tool
def collect_location(latitude: float, longitude: float) -> str:
    """
    Collect GPS location coordinates.

    Args:
        latitude: Latitude coordinate
        longitude: Longitude coordinate

    Returns:
        Confirmation message
    """
    return f"Location collected: {latitude}, {longitude}"


@tool
def analyze_waste_image(image_url: str) -> str:
    """
    Analyze waste image using AI (stub - actual analysis happens in graph.py).

    Args:
        image_url: URL of the waste image

    Returns:
        Analysis result
    """
    return "Image analysis in progress..."


@tool
def create_quest_in_database(description: str, waste_type: str, severity: str) -> str:
    """
    Create quest in database (stub - actual creation happens in graph.py).

    Args:
        description: Quest description
        waste_type: Type of waste
        severity: Severity level

    Returns:
        Quest creation confirmation
    """
    return "Quest creation in progress..."
