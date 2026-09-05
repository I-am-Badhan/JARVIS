from livekit.plugins import sarvam, cartesia, google, elevenlabs
from services.tts.edge_tts_service import EdgeTTS
from config.tts_config import *
from config.api_key_config import ELEVEN_API_KEY


def get_sarvam_tts() -> sarvam.TTS:
    return sarvam.TTS(
        target_language_code=SARVAM_TTS_LANGUAGE,
        model=SARVAM_TTS_MODEL,
        speaker=SARVAM_TTS_SPEAKER,
    )


def get_cartesia_tts() -> cartesia.TTS:
    return cartesia.TTS(
        model=CARTESIA_TTS_MODEL,
        voice=CARTESIA_TTS_VOICE,
        language=CARTESIA_TTS_LANGUAGE,
        speed=CARTESIA_TTS_SPEED,
        volume=CARTESIA_TTS_VOLUME,
    )

def get_elevenlabs_tts() -> elevenlabs.TTS:
    return elevenlabs.TTS(
        api_key=ELEVEN_API_KEY,
        voice_id=ELEVEN_TTS_VOICE_ID,
        model=ELEVEN_TTS_MODEL,
        language=ELEVEN_TTS_LANGUAGE,
        auto_mode=ELEVEN_TTS_AUTO_MODE,
        streaming_latency=ELEVEN_TTS_STREAMING_LATENCY,
        voice_settings=elevenlabs.VoiceSettings(
            stability=ELEVEN_TTS_VOICE_STABILITY,
            similarity_boost=ELEVEN_TTS_VOICE_SIMILARITY_BOOST,
            style=ELEVEN_TTS_VOICE_STYLE,
            use_speaker_boost=ELEVEN_TTS_VOICE_USE_SPEAKER_BOOST,
            speed=ELEVEN_TTS_VOICE_SPEED,
        ),
    )

def get_google_tts() -> google.beta.GeminiTTS:
    return google.beta.GeminiTTS(
        model=GOOGLE_TTS_MODEL,
        voice_name= GOOGLE_TTS_VOICE,
    )


def get_edge_tts() -> EdgeTTS:
    return EdgeTTS(
        voice=EDGE_TTS_VOICE,
        rate=EDGE_TTS_RATE,
        volume=EDGE_TTS_VOLUME,
        pitch=EDGE_TTS_PITCH,
    )