from livekit.plugins import deepgram
from config import STT_MODEL, STT_LANGUAGE


def get_stt() -> deepgram.STT:
    return deepgram.STT(model=STT_MODEL, language=STT_LANGUAGE)