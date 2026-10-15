
from livekit.agents import AgentSession

from services.realtime_llm_service import get_realtime_llm


def create_session(mode: str) -> AgentSession:
    mode = mode.strip().lower()

    if mode == "realtime":
        return AgentSession(
            llm=get_realtime_llm(),
        )

    if mode == "pipeline":
        from livekit.plugins import silero

        from services.stt_service import get_stt
        from services.llm_service import get_groq_llm
        from services.tts.tts_service import get_cartesia_tts
        from utils.interruption import get_turn_handling

        return AgentSession(
            stt=get_stt(),
            llm=get_groq_llm(),
            tts=get_cartesia_tts(),
            vad=silero.VAD.load(),
            turn_handling=get_turn_handling(),
        )

    raise ValueError(f"Unknown JARVIS mode: {mode}")
