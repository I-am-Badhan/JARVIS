import os
from dotenv import load_dotenv

load_dotenv(".env.local")

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

LIVEKIT_INFERENCE_URL = os.getenv("LIVEKIT_INFERENCE_URL")
LIVEKIT_INFERENCE_API_KEY = os.getenv("LIVEKIT_INFERENCE_API_KEY")
LIVEKIT_INFERENCE_API_SECRET = os.getenv("LIVEKIT_INFERENCE_API_SECRET")

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")


STT_MODEL = "nova-3"
STT_LANGUAGE = "multi"

LLM_MODEL = "openai/gpt-oss-120b"

# TTS_MODEL = "aura-asteria-en"
TTS_MODEL = "bulbul:v3"
TTS_LANGUAGE = "hi-IN"
TTS_SPEAKER = "shubh"

AGENT_NAME = "jarvis"