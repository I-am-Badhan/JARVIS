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
            "Greet the user as JARVIS, as if the system has just been activated or the user has returned. "
            "Address the user as 'sir' or occasionally 'boss'. "
            "Use a short, natural greeting similar in feel to 'Welcome, sir' or 'Welcome back, sir'. "
            "Then briefly ask what the user has planned for today or what they would like to get started with. "
            "Keep it calm, confident, sophisticated, and conversational. "
            "Do not give a long introduction, do not explain your role, and do not use generic chatbot phrases."
        )
    )