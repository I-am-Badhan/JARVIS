from livekit.plugins import groq, google
from config.llm_config import *
from config.api_key_config import GROQ_API_KEY


def get_groq_llm() -> groq.LLM:
    return groq.LLM(
        api_key=GROQ_API_KEY,
        model=GROQ_LLM_MODEL,
        temperature=GROQ_LLM_TEMPARATURE,
    )

def get_google_llm() -> google.LLM:
    return google.LLM(
        model=GOOGLE_LLM_MODEL,
        temperature=GOOGLE_LLM_TEMPARATURE,
    )