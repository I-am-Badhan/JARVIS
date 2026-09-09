from livekit.agents import Agent
from prompts.system_prompt import JARVIS_INSTRUCTIONS
from tools.date_time import get_date_time
from tools.realtime_information import get_realtime_information
from tools.DesktopAutomation.apps import open_application, close_application, switch_to_application
from tools.DesktopAutomation.input_control import type_text, type_text_unicode, press_key

class Jarvis(Agent):

    def __init__(self) -> None:
        super().__init__(
            instructions=JARVIS_INSTRUCTIONS,
            tools=[
                get_date_time,
                get_realtime_information,
                open_application,
                close_application,
                switch_to_application,
                type_text, 
                type_text_unicode, 
                press_key,
            ]
        )


