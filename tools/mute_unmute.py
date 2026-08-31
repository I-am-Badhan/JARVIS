# import asyncio
# import logging
# from typing import Any

# from livekit import agents, rtc
# from livekit.agents import RunContext

# logger = logging.getLogger("jarvis.tools")

# _PENDING_TEXT_BY_SESSION: dict[int, str] = {}


# def _session_key(session: Any) -> int:
#     return id(session)


# def _normalize_text(value: Any) -> str:
#     if value is None:
#         return ""

#     if isinstance(value, str):
#         return value.strip()

#     if isinstance(value, (list, tuple)):
#         chunks: list[str] = []
#         for item in value:
#             chunk = _normalize_text(item)
#             if chunk:
#                 chunks.append(chunk)
#         return " ".join(chunks)

#     if isinstance(value, dict):
#         for key in ("text", "content", "message", "value"):
#             if key in value and value[key] is not None:
#                 return _normalize_text(value[key])
#         return " ".join(
#             _normalize_text(v)
#             for v in value.values()
#             if _normalize_text(v)
#         )

#     if hasattr(value, "text_content"):
#         return _normalize_text(getattr(value, "text_content"))

#     if hasattr(value, "raw_text_content"):
#         return _normalize_text(getattr(value, "raw_text_content"))

#     if hasattr(value, "text"):
#         return _normalize_text(getattr(value, "text"))

#     if hasattr(value, "content"):
#         return _normalize_text(getattr(value, "content"))

#     return str(value).strip()


# def _capture_pending_text(ctx: RunContext) -> str:
#     speech_handle = getattr(ctx, "speech_handle", None)
#     if speech_handle is None:
#         return ""

#     chat_items = getattr(speech_handle, "chat_items", []) or []
#     for item in reversed(chat_items):
#         role = getattr(item, "role", None)
#         if role != "assistant":
#             continue

#         text = getattr(item, "text_content", None)
#         if text:
#             return text.strip()

#         text = getattr(item, "raw_text_content", None)
#         if text:
#             return text.strip()

#     return ""


# async def _toggle_local_audio(ctx: RunContext, *, muted: bool) -> bool:
#     room = getattr(ctx, "room", None)
#     if room is None:
#         return False

#     local_participant = getattr(room, "local_participant", None)
#     if local_participant is None:
#         return False

#     for track_pub in list(local_participant.track_publications.values()):
#         track = getattr(track_pub, "track", None)
#         if track is not None and getattr(track, "kind", None) == rtc.TrackKind.KIND_AUDIO:
#             if muted:
#                 track.mute()
#             else:
#                 track.unmute()

#     return True


# @agents.function_tool
# async def mute_agent(ctx: RunContext) -> str:
#     """
#     Interrupt current speech immediately, mute the local audio, and keep the
#     unfinished assistant text so it can be resumed after unmute.
#     """
#     try:
#         session = getattr(ctx, "session", None)
#         pending_text = _capture_pending_text(ctx)

#         if pending_text:
#             _PENDING_TEXT_BY_SESSION[_session_key(session)] = pending_text
#             logger.info("Captured pending assistant text before interrupt: %s", pending_text)

#         if session is not None:
#             try:
#                 # IMPORTANT: session.interrupt() returns a Future, not a coroutine.
#                 # Do not wrap in asyncio.create_task() and do not await it here.
#                 session.interrupt(force=True)
#             except Exception:
#                 logger.debug("Unable to interrupt current speech", exc_info=True)

#         if not await _toggle_local_audio(ctx, muted=True):
#             return "I can't mute because there is no active room."

#         logger.info("🔊 [TOOL EXECUTION] -> Mute command triggered. Local audio track muted.")
#         return "I am now muted. I will not speak until you unmute me."
#     except Exception as exc:
#         logger.exception("Mute tool failed")
#         return f"Failed to mute agent: {exc}"


# @agents.function_tool
# async def unmute_agent(ctx: RunContext) -> str:
#     """
#     Unmute local audio and continue the exact pending sentence that was cut off.
#     """
#     try:
#         session = getattr(ctx, "session", None)
#         pending_text = ""
#         if session is not None:
#             pending_text = _PENDING_TEXT_BY_SESSION.pop(_session_key(session), "").strip()

#         if not await _toggle_local_audio(ctx, muted=False):
#             return "I can't unmute because there is no active room."

#         if session is not None and pending_text:
#             logger.info("Resuming pending assistant text after unmute: %s", pending_text)
#             session.say(pending_text)
#             logger.info("📢 [TOOL EXECUTION] -> Unmute command triggered. Resuming exact pending text.")
#             return "I am now unmuted and continuing my last sentence."

#         logger.info("📢 [TOOL EXECUTION] -> Unmute command triggered. Local audio track re-enabled.")
#         return "I am now unmuted and ready to speak."
#     except Exception as exc:
#         logger.exception("Unmute tool failed")
#         return f"Failed to unmute agent: {exc}"