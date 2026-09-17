import json
import asyncio
import logging
from config.system_config import AGENT_NAME
from livekit import agents, rtc
from livekit.agents import AgentServer

from agent import Jarvis
from session import create_session

from prompts.generate_reply_prompt import GENERATE_REPLY
from config.session_config import *

from utils.greet import build_greeting_prompt

logger = logging.getLogger("jarvis.server")
server = AgentServer()


@server.rtc_session()
async def jarvis_session(ctx: agents.JobContext):

    mode = SESSION_MODE
    session = create_session(mode)

    await session.start(
        room=ctx.room,
        agent=Jarvis(),
    )

    async def send_chat_to_frontend(sender: str, text: str):
        if not text:
            return
        payload = json.dumps({
            "sender": sender,
            "text": text,
            "reply": text
        }).encode("utf-8")
        try:
            await ctx.room.local_participant.publish_data(payload, reliable=True)
        except Exception as e:
            logger.warning(f"Error publishing chat message: {e}")

    async def handle_user_command(user_text: str):
        try:
            handle = session.generate_reply(instructions=user_text)
            if asyncio.iscoroutine(handle) or hasattr(handle, "__await__"):
                await handle
        except Exception as e:
            logger.error(f"Error during generate_reply: {e}")

    @ctx.room.on("data_received")
    def on_data_received(data_packet: rtc.DataPacket):
        try:
            raw = data_packet.data.decode("utf-8")
            data = json.loads(raw)
            user_text = data.get("text", "").strip()
            if user_text:
                logger.info(f"Received text from Chat Window: {user_text}")
                asyncio.create_task(handle_user_command(user_text))
        except Exception as err:
            logger.error(f"Failed to process chat data: {err}")

    @session.on("conversation_item_added")
    def on_conversation_item_added(event_or_item):
        try:
            item = getattr(event_or_item, "item", event_or_item)
            role = getattr(item, "role", "")
            if hasattr(role, "value"):
                role = role.value
            role = str(role).lower()

            text = ""
            if hasattr(item, "text") and item.text:
                text = item.text
            elif hasattr(item, "content") and item.content:
                if isinstance(item.content, list):
                    text = " ".join(str(c) for c in item.content if c)
                else:
                    text = str(item.content)
            elif hasattr(item, "text_content") and item.text_content:
                text = item.text_content

            text = text.strip()
            if text and role in ["assistant", "user"]:
                sender = "jarvis" if role == "assistant" else "user"
                asyncio.create_task(send_chat_to_frontend(sender, text))
        except Exception as e:
            logger.error(f"Error forwarding conversation item: {e}")

    greeting_prompt = build_greeting_prompt(
        GENERATE_REPLY
    )

    await session.generate_reply(
        instructions=greeting_prompt
    )