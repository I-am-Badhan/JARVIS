import asyncio
import json
import logging
import time

from livekit import agents, rtc
from livekit.agents import AgentServer

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

    def mark(step: str):
        logger.info("[STARTUP] %s | %.3fs", step, time.perf_counter() - started)

    mark("Job entry")
    session = create_session(SESSION_MODE)
    mark(f"Session object created: mode={SESSION_MODE}")

    async def send_chat_to_frontend(sender: str, text: str):
        if not text:
            return
        payload = json.dumps({"sender": sender, "text": text, "reply": text}).encode("utf-8")
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
    last_greeted_identity = None

    async def greet_on_ui_connection(participant):
        nonlocal last_greeted_identity
        identity = getattr(participant, "identity", "unknown")
        async with greeting_lock:
            # One greeting per connection event. The UI is expected to connect only
            # after the wake word, while this agent/session is already warm.
            logger.info("UI participant connected: %s", identity)
            try:
                prompt = build_greeting_prompt(GENERATE_REPLY)
                mark("UI connected; sending greeting")
                result = session.generate_reply(instructions=prompt)
                if asyncio.iscoroutine(result) or hasattr(result, "__await__"):
                    await result
                mark("Wake-triggered greeting completed")
                last_greeted_identity = identity
            except Exception:
                logger.exception("Wake-triggered greeting failed")

    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        # This handler is fired when the UI joins the room. The agent is already
        # running, so there is no need to start a second agent process on wake.
        asyncio.create_task(greet_on_ui_connection(participant))

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
        await session.start(room=ctx.room, agent=Jarvis())
        mark("session.start completed; waiting for wake-triggered UI connection")
    except Exception:
        logger.exception("Failed to start AgentSession")
        raise
