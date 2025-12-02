"""Web Search Tool for ReAct Agent

Uses SerpAPI's DuckDuckGo Search Engine Results API.
Requires SERPAPI_API_KEY environment variable.
"""

from typing import Dict, Any
import httpx
import os

from langchain_core.tools import tool


@tool
async def search_waste_information(query: str, max_results: int = 3) -> Dict[str, Any]:
    """
    Search for waste management information on the web using DuckDuckGo via SerpAPI.
    
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
        
        # Get SerpAPI key from environment
        api_key = os.getenv("SERPAPI_API_KEY", "")
        
        if not api_key:
            return {
                "success": False,
                "error": "SerpAPI key not configured. Please contact administrator.",
                "results": []
            }
        
        # Use SerpAPI DuckDuckGo Search Engine endpoint
        url = "https://serpapi.com/search.json"
        params = {
            "engine": "duckduckgo",
            "q": query,
            "kl": "us-en",  # US English region
            "api_key": api_key
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # Extract organic results from SerpAPI response
        results = []
        organic_results = data.get("organic_results", [])
        
        for result in organic_results[:max_results]:
            results.append({
                "title": result.get("title", ""),
                "snippet": result.get("snippet", ""),
                "url": result.get("link", ""),
                "source": "DuckDuckGo via SerpAPI"
            })
        
        # Format response
        if not results:
            return {
                "success": True,
                "message": f"No results found for '{query}'. Try rephrasing your question or ask me something else about waste management.",
                "results": []
            }
        
        # Format results as readable text
        formatted_results = []
        for i, result in enumerate(results, 1):
            formatted_results.append(
                f"{i}. **{result['title']}**\n"
                f"   {result['snippet']}\n"
                f"   URL: {result['url']}"
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
