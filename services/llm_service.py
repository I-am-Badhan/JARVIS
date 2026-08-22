from livekit.plugins import groq
from config import LLM_MODEL


def get_llm() -> groq.LLM:
    return groq.LLM(model=LLM_MODEL)