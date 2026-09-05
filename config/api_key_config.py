import os
from dotenv import load_dotenv

load_dotenv(".env.local")

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
SARVAM_API_KEY = os.getenv("SARVAM_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")
EXA_API_KEY = os.getenv("EXA_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
SERPER_API_KEY = os.getenv("SERPER_API_KEY")
