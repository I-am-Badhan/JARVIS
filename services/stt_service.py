from livekit.plugins import deepgram
from config.stt_config import *


def get_stt() -> deepgram.STT:
    return deepgram.STT(
        model=STT_MODEL, 
        language=STT_LANGUAGE,
    )