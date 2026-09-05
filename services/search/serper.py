import httpx
from config.api_key_config import SERPER_API_KEY
from config.search_config import SERPER_SEARCH_URL

async def search_serper(query: str) -> list[dict]:
    """
    Search Google results using Serper API.
    """

    if not SERPER_API_KEY:
        raise RuntimeError("SERPER_API_KEY is not configured.")

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "q": query,
        "gl": "in",
        "hl": "en",
        "num": 5,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            SERPER_SEARCH_URL,
            headers=headers,
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

    results = []

    for item in data.get("organic", []):
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "description": item.get("snippet", ""),
                "provider": "Serper",
            }
        )

    return results