import httpx
from config.api_key_config import TAVILY_API_KEY
from config.search_config import TAVILY_SEARCH_URL

async def search_tavily(query: str) -> list[dict]:
    """
    Search the web using Tavily Search API.
    """

    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not configured.")

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TAVILY_API_KEY}",
    }

    payload = {
        "query": query,
        "search_depth": "fast",
        "max_results": 5,
        "include_answer": False,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            TAVILY_SEARCH_URL,
            headers=headers,
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

    results = []

    for item in data.get("results", []):
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("content", ""),
                "provider": "Tavily",
            }
        )

    return results