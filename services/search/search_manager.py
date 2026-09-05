import logging

from .exa import search_exa
from .tavily import search_tavily
from .serper import search_serper
from .searxng import search_searxng


logger = logging.getLogger(__name__)


SEARCH_PROVIDERS = [
    ("Tavily", search_tavily),
    ("Exa", search_exa),
    ("Serper", search_serper),
    ("SearXNG", search_searxng),
]


async def search_web(query: str) -> dict:
    """
    Search the web using a prioritized provider fallback chain.

    Priority:
        1. Tavily 
        2. Exa 
        3. Serper
        4. SearXNG
    """

    query = query.strip()

    if not query:
        return {
            "success": False,
            "query": query,
            "provider": None,
            "results": [],
            "error": "Search query cannot be empty.",
        }

    provider_errors = []

    for provider_name, provider_function in SEARCH_PROVIDERS:

        try:
            logger.info(
                "Trying search provider: %s",
                provider_name,
            )

            results = await provider_function(query)

            if results:
                logger.info(
                    "Search successful with provider: %s",
                    provider_name,
                )

                return {
                    "success": True,
                    "query": query,
                    "provider": provider_name,
                    "results": results,
                }

            logger.warning(
                "%s returned no results.",
                provider_name,
            )

        except Exception as exc:

            logger.warning(
                "%s failed: %s",
                provider_name,
                exc,
            )

            provider_errors.append(
                {
                    "provider": provider_name,
                    "error": str(exc),
                }
            )

    return {
        "success": False,
        "query": query,
        "provider": None,
        "results": [],
        "error": "All search providers failed.",
        "provider_errors": provider_errors,
    }