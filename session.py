from livekit.agents import AgentSession
from livekit.plugins import silero

from services.stt_service import *
from services.llm_service import *
from services.tts.tts_service import *
from utils.interruption import *
from services.realtime_llm_service import *

def create_session(mode: str) -> AgentSession:

    if mode == "pipeline":

        return AgentSession(
            stt=get_stt(),
            llm=get_groq_llm(),
            tts=get_cartesia_tts(),
            vad=silero.VAD.load(),
            turn_handling=get_turn_handling(),
        )

    elif mode == "realtime":

        return AgentSession(
            llm=get_realtime_llm(),
        )

    else:
        raise ValueError(
            f"Unknown JARVIS mode: {mode}"
        )