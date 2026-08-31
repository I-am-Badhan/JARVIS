from livekit.agents import Agent
from prompts.system_prompt import JARVIS_INSTRUCTIONS

class Jarvis(Agent):

    def __init__(self) -> None:
        super().__init__(
            instructions=JARVIS_INSTRUCTIONS
        )


