from livekit.agents import TurnHandlingOptions
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from config.interruption_config import *

def get_turn_handling() -> TurnHandlingOptions:
    return TurnHandlingOptions(
        turn_detection=MultilingualModel(),
        interruption={
            "min_duration" : INTERRUPTION_MIN_DURATION,
            "min_words" : INTERRUPTION_MIN_WORDS,
            "mode" : INTERRUPTION_MODE,
            "false_interruption_timeout" : FALSE_INTERRUPTION_TIMEOUT,
            "resume_false_interruption" : RESUME_FALSE_INTERRUPTION,
            # "discard_audio_if_uninterruptible" : DISCARD_AUDIO_IF_UNINTERRUPTIBLE,
        },
    )