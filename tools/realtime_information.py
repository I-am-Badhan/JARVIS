from livekit.agents import RunContext, function_tool

from services.search.search_manager import search_web


@function_tool(
    name="get_realtime_information",
    description=(
        "Search the web for current, recent, latest, or up-to-date information. "
        "Use this tool when the user's question requires live web research "
        "or information that may have changed recently. Do not use it for "
        "dedicated weather, finance, crypto, sports, news, or date/time requests "
        "when a specialized tool is available. Never guess current information."
    ),
)
async def get_realtime_information(
    context: RunContext,
    query: str,
) -> dict:

    # Immediate acknowledgement before starting web search
    await context.session.say(
        "Thik hai sir, abhi search karta hoon.",
        add_to_chat_ctx=False,
    )
    result = await search_web(query)

    return result