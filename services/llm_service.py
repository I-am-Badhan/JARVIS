from livekit.plugins import groq, google
from config.llm_config import *


def get_groq_llm() -> groq.LLM:
    return groq.LLM(
        model=GROQ_LLM_MODEL,
        temperature=GROQ_LLM_TEMPARATURE,
    )

def get_google_llm() -> google.LLM:
    return google.LLM(
        model=GOOGLE_LLM_MODEL,
        temperature=GOOGLE_LLM_TEMPARATURE,
    )