from livekit.plugins import sarvam
from config import TTS_MODEL, TTS_LANGUAGE, TTS_SPEAKER


def get_tts() -> sarvam.TTS:
    return sarvam.TTS(
        target_language_code=TTS_LANGUAGE,
        model=TTS_MODEL,
        speaker=TTS_SPEAKER,
    )