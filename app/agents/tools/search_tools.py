"""Web Search Tool for ReAct Agent

Uses DuckDuckGo Instant Answer API (free, no authentication required).
For production, can be upgraded to Tavily API with TAVILY_API_KEY.
"""

from typing import Dict, Any
import httpx

from langchain_core.tools import tool


@tool
async def search_waste_information(query: str, max_results: int = 3) -> Dict[str, Any]:
    """
    Search for waste management information on the web using DuckDuckGo.
    
    Use this tool to answer questions about:
    - Waste disposal methods
    - Recycling guidelines
    - Environmental information
    - Waste management best practices
    
    Args:
        query: Search query about waste management
        max_results: Maximum number of results to return (default 3)
        
    Returns:
        Dictionary with search results
    """
    try:
        # Limit max results
        max_results = min(max_results, 5)
        
        # Use DuckDuckGo Instant Answer API
        # This is a simple API that doesn't require authentication
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Extract relevant information
        results = []
        
        # Add abstract if available
        if data.get("Abstract"):
            results.append({
                "title": data.get("Heading", "General Information"),
                "snippet": data.get("Abstract"),
                "url": data.get("AbstractURL", ""),
                "source": data.get("AbstractSource", "DuckDuckGo")
            })
        
        # Add related topics
        for topic in data.get("RelatedTopics", [])[:max_results-len(results)]:
            if isinstance(topic, dict) and "Text" in topic:
                results.append({
                    "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                    "source": "DuckDuckGo"
                })
        
        # Format response
        if not results:
            return {
                "success": True,
                "message": f"No specific results found for '{query}'. Try rephrasing your question or ask me something else about waste management.",
                "results": []
            }
        
        # Format results as readable text
        formatted_results = []
        for i, result in enumerate(results[:max_results], 1):
            formatted_results.append(
                f"{i}. **{result['title']}**\n"
                f"   {result['snippet']}\n"
                f"   Source: {result['source']}"
            )
        
        message = f"Found {len(results)} result(s) for '{query}':\n\n" + "\n\n".join(formatted_results)
        
        return {
            "success": True,
            "message": message,
            "results": results
        }
        
    except httpx.TimeoutException:
        return {
            "success": False,
            "error": "Search request timed out. Please try again.",
            "results": []
        }
    except httpx.HTTPError as e:
        return {
            "success": False,
            "error": f"Search failed: {str(e)}",
            "results": []
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unexpected error during search: {str(e)}",
            "results": []
        }
