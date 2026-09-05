import os

import httpx
from dotenv import load_dotenv

load_dotenv()


SEARXNG_URL = os.getenv(
    "SEARXNG_URL",
    "http://localhost:8080",
).rstrip("/")


async def search_searxng(query: str) -> list[dict]:
    """
    Search the web using a SearXNG instance.
    """

    if not SEARXNG_URL:
        raise RuntimeError("SEARXNG_URL is not configured.")

    url = f"{SEARXNG_URL}/search"

    params = {
        "q": query,
        "format": "json",
        "language": "en",
        "safesearch": 1,
        "pageno": 1,
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            url,
            params=params,
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
                "provider": "SearXNG",
            }
        )

    return results