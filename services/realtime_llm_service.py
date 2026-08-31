from livekit.plugins import google
from config.realtime_config import *

def get_realtime_llm() -> google.beta.realtime.RealtimeModel:
    return google.beta.realtime.RealtimeModel(
        model=GOOGLE_REALTIME_MODEL,
        voice=GOOGLE_REALTIME_VOICE,
        temperature=GOOGLE_REALTIME_TEMPARATURE,
    )