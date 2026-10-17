import asyncio
import json
import logging
import time

from livekit import agents, rtc
from livekit.agents import AgentServer, room_io

from agent import Jarvis
from session import create_session
from config.session_config import SESSION_MODE
from prompts.generate_reply_prompt import GENERATE_REPLY
from utils.greet import build_greeting_prompt

logger = logging.getLogger("jarvis.server")
server = AgentServer()


@server.rtc_session()
async def jarvis_session(ctx: agents.JobContext):
    started = time.perf_counter()
    session_ready = asyncio.Event()

    def mark(step: str):
        logger.info("[STARTUP] %s | %.3fs", step, time.perf_counter() - started)

    mark("Job entry")
    session = create_session(SESSION_MODE)
    mark(f"Session object created: mode={SESSION_MODE}")

    async def send_chat_to_frontend(sender: str, text: str):
        if not text:
            return
        payload = json.dumps(
            {"sender": sender, "text": text, "reply": text},
            ensure_ascii=False,
        ).encode("utf-8")
        try:
            await ctx.room.local_participant.publish_data(payload, reliable=True)
        except Exception:
            logger.exception("Error publishing chat message")

    async def handle_user_command(user_text: str):
        try:
            logger.info("Calling generate_reply for user command")
            result = session.generate_reply(instructions=user_text)
            if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
                await result
        except Exception:
            logger.exception("Error during generate_reply")

    greeting_lock = asyncio.Lock()
    greeted_identities = set()

    async def greet_on_ui_connection(participant):
        identity = str(getattr(participant, "identity", "unknown"))
        await session_ready.wait()
        async with greeting_lock:
            # participant_connected and the post-start participant scan can both
            # notice the same UI. Send exactly one greeting per identity per session.
            if identity in greeted_identities:
                return
            greeted_identities.add(identity)
            logger.info("UI participant connected: %s", identity)
            try:
                prompt = build_greeting_prompt(GENERATE_REPLY)
                mark("UI connected; sending greeting")
                result = session.generate_reply(instructions=prompt)
                if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
                    await result
                mark("Wake-triggered greeting completed")
            except Exception:
                greeted_identities.discard(identity)
                logger.exception("Wake-triggered greeting failed")

    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        # Session readiness is awaited inside greet_on_ui_connection, so this is
        # safe even if the UI connects during the agent's startup/recovery window.
        asyncio.create_task(greet_on_ui_connection(participant))

    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        # The same UI identity can reconnect on the next wake cycle. Re-arm its
        # greeting while retaining this Realtime session and its context.
        identity = str(getattr(participant, "identity", "unknown"))
        greeted_identities.discard(identity)
        logger.info("UI participant disconnected: %s; greeting re-armed", identity)

    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        try:
            raw = data_packet.data.decode("utf-8")
            data = json.loads(raw)
            user_text = data.get("text", "").strip()
            if user_text:
                logger.info("Received text from Chat Window: %s", user_text)
                asyncio.create_task(handle_user_command(user_text))
        except Exception:
            logger.exception("Failed to process chat data")

    @session.on("conversation_item_added")
    def on_conversation_item_added(event_or_item):
        try:
            item = getattr(event_or_item, "item", event_or_item)
            role = getattr(item, "role", "")
            if hasattr(role, "value"):
                role = role.value
            role = str(role).lower()

            text = ""
            if getattr(item, "text", None):
                text = item.text
            elif getattr(item, "content", None):
                content = item.content
                text = " ".join(str(part) for part in content if part) if isinstance(content, list) else str(content)
            elif getattr(item, "text_content", None):
                text = item.text_content

            text = text.strip()
            if text and role in ("assistant", "user"):
                sender = "jarvis" if role == "assistant" else "user"
                asyncio.create_task(send_chat_to_frontend(sender, text))
        except Exception:
            logger.exception("Error forwarding conversation item")

    try:
        await session.start(
            room=ctx.room,
            agent=Jarvis(),
            room_options=room_io.RoomOptions(close_on_disconnect=False),
        )
        session_ready.set()
        mark("session.start completed; waiting for wake-triggered UI connection")

        # If the launcher has to recover the agent while the UI is already open,
        # participant_connected may have fired before session.start completed.
        # Scan existing participants to avoid leaving that UI without a greeting.
        for participant in list(ctx.room.remote_participants.values()):
            asyncio.create_task(greet_on_ui_connection(participant))
    except Exception:
        logger.exception("Failed to start AgentSession")
        raise
