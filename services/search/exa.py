import httpx
from config.api_key_config import EXA_API_KEY
from config.search_config import EXA_SEARCH_URL

async def search_exa(query: str) -> list[dict]:
    """
    Search the web using Exa.
    """

    if not EXA_API_KEY:
        raise RuntimeError("EXA_API_KEY is not configured.")

    headers = {
        "x-api-key": EXA_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "query": query,
        "type": "instant",
        "numResults": 5,
        "contents": {
            "highlights": True,
        },
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            EXA_SEARCH_URL,
            headers=headers,
            json=payload,
        )

        response.raise_for_status()

        data = response.json()

    results = []

    for item in data.get("results", []):
        highlights = item.get("highlights", [])

        description = " ".join(highlights)

        if not description:
            description = item.get("text", "")

        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": description,
                "published_date": item.get("publishedDate"),
                "provider": "Exa",
            }
        )

    return results