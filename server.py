from config.system_config import AGENT_NAME
from livekit import agents
from livekit.agents import AgentServer
from agent import Jarvis
from session import create_session
from config.session_config import *

server = AgentServer()

@server.rtc_session(agent_name=AGENT_NAME)
async def jarvis_session(ctx: agents.JobContext):

    mode = SESSION_MODE
    session = create_session(mode)

    await session.start(
        room=ctx.room,
        agent=Jarvis(),
    )

    await session.generate_reply(
        instructions=(
            "Welcome the user and ask for today's plan."
        )
    )