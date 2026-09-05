from __future__ import annotations

from tools.date_time import get_current_time
from config.date_time_config import DEFAULT_TIMEZONE

def get_time_period(hour: int) -> str:
    """
    Determine greeting period from hour.

    05:00 - 11:59 -> morning
    12:00 - 16:59 -> afternoon
    17:00 - 20:59 -> evening
    21:00 - 04:59 -> night
    """

    if 5 <= hour < 12:
        return "morning"

    elif 12 <= hour < 17:
        return "afternoon"

    elif 17 <= hour < 21:
        return "evening"

    else:
        return "night"


def get_time_greeting(
    timezone_name: str = DEFAULT_TIMEZONE,
) -> str:

    now = get_current_time(timezone_name)

    period = get_time_period(now.hour)

    greetings = {
        "morning": "Good morning",
        "afternoon": "Good afternoon",
        "evening": "Good evening",
        "night": "Good night",
    }

    return greetings[period]


def get_greeting_context(
    timezone_name: str = DEFAULT_TIMEZONE,
) -> dict:
    """
    Generate fresh greeting context.

    IMPORTANT:
    This function checks the current time every time it is called.
    """

    now = get_current_time(timezone_name)

    period = get_time_period(now.hour)

    greeting = get_time_greeting(timezone_name)

    return {
        "timezone": timezone_name,

        "period": period,

        "greeting": greeting,

        "hour": now.hour,
        "minute": now.minute,

        "time_24h": now.strftime("%H:%M"),
        "time_12h": now.strftime("%I:%M %p"),

        "date": now.strftime("%d %B %Y"),

        "day": now.strftime("%A"),
    }


def build_greeting_prompt(
    base_prompt: str,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> str:
    """
    Inject current date/time information into the greeting prompt.

    Call this function immediately before asking the LLM
    to generate the greeting.
    """

    context = get_greeting_context(timezone_name)

    dynamic_context = f"""

CURRENT REAL-WORLD TIME CONTEXT:

Timezone: {context["timezone"]}
Current time: {context["time_12h"]}
Current date: {context["date"]}
Current day: {context["day"]}
Current time period: {context["period"]}
Correct greeting: {context["greeting"]}

IMPORTANT:
The above information was calculated programmatically.
Use it as the source of truth.

Do NOT guess the current time or greeting period.

"""

    return f"{base_prompt}\n{dynamic_context}".strip()