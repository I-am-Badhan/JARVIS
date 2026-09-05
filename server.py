from config.system_config import AGENT_NAME
from livekit import agents
from livekit.agents import AgentServer

from agent import Jarvis
from session import create_session

from prompts.generate_reply_prompt import GENERATE_REPLY
from config.session_config import *

from utils.greet import build_greeting_prompt


server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def jarvis_session(ctx: agents.JobContext):

    mode = SESSION_MODE

    session = create_session(mode)

    await session.start(
        room=ctx.room,
        agent=Jarvis(),
    )

    greeting_prompt = build_greeting_prompt(
        GENERATE_REPLY
    )

    await session.generate_reply(
        instructions=greeting_prompt
    )