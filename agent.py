from livekit import agents
from livekit.agents import (
    AgentServer,
    AgentSession,
    Agent,
    TurnHandlingOptions,
)
from livekit.plugins import silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

from config import AGENT_NAME
from prompts.system_prompt import JARVIS_INSTRUCTIONS
from services.stt_service import get_stt
from services.llm_service import get_llm
from services.tts_service import get_tts


class Jarvis(Agent):
    def __init__(self) -> None:
        super().__init__(instructions=JARVIS_INSTRUCTIONS)


server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def jarvis_session(ctx: agents.JobContext):
    session = AgentSession(
        stt=get_stt(),
        llm=get_llm(),
        tts=get_tts(),
        vad=silero.VAD.load(
            min_speech_duration=0.3,
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=MultilingualModel(),
            allow_interruptions=False,
        ),
        
    )

    await session.start(
        room=ctx.room,
        agent=Jarvis(),
    )

    await session.generate_reply(
        instructions="Greet the user briefly and let them know you're online."
    )