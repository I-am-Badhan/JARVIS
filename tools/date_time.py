from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from livekit.agents import function_tool
from config.date_time_config import DEFAULT_TIMEZONE, TIMEZONE_ALIASES


def resolve_timezone(timezone_name: Optional[str] = None) -> str:
    """
    Convert user-friendly timezone/city names into an IANA timezone.

    Examples:
        India       -> Asia/Kolkata
        London      -> Europe/London
        New York    -> America/New_York

    Direct IANA timezone names are also supported.
    """

    if not timezone_name:
        return DEFAULT_TIMEZONE

    timezone_name = timezone_name.strip()
    cleaned = timezone_name.lower()

    if cleaned in TIMEZONE_ALIASES:
        return TIMEZONE_ALIASES[cleaned]

    try:
        ZoneInfo(timezone_name)
        return timezone_name

    except ZoneInfoNotFoundError:
        raise ValueError(
            f"Unknown timezone or location: {timezone_name}"
        )


def get_current_time(
    timezone_name: Optional[str] = None,
) -> datetime:
    """
    Return timezone-aware current datetime.
    """

    timezone_id = resolve_timezone(timezone_name)

    return datetime.now(
        ZoneInfo(timezone_id)
    )


def get_current_hour(
    timezone_name: Optional[str] = None,
) -> int:
    """
    Return current hour (0-23).
    """

    return get_current_time(timezone_name).hour


def get_datetime_data(
    timezone_name: Optional[str] = None,
) -> dict:
    """
    Return detailed structured datetime information.
    """

    timezone_id = resolve_timezone(timezone_name)
    now = datetime.now(ZoneInfo(timezone_id))

    return {
        "success": True,

        "timezone": timezone_id,
        "timezone_abbreviation": now.tzname(),

        "date": now.strftime("%Y-%m-%d"),
        "date_readable": now.strftime("%d %B %Y"),

        "day": now.strftime("%A"),

        "time_24h": now.strftime("%H:%M:%S"),
        "time_12h": now.strftime("%I:%M:%S %p"),

        "hour": now.hour,
        "minute": now.minute,
        "second": now.second,

        "day_of_month": now.day,
        "month": now.strftime("%B"),
        "month_number": now.month,
        "year": now.year,

        "iso_datetime": now.isoformat(),

        "utc_offset": now.strftime("%z"),
    }

@function_tool(
    name="get_date_time",
    description=(
        "Get the current local date and time for a requested "
        "city, country, or timezone. Use this tool whenever the "
        "user asks about the current time, date, day, or timezone "
        "in India or another location. If no location is specified, "
        "use India."
    ),
)
async def get_date_time(
    timezone_name: Optional[str] = None,
) -> dict:
    """
    Get current date and time.

    Args:
        timezone_name:
            Location or timezone requested by the user.

            Examples:
            India
            London
            New York
            Tokyo
            Dubai
            Asia/Kolkata
            America/New_York

    Returns:
        Current local date/time information.
    """

    try:
        return get_datetime_data(timezone_name)

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }