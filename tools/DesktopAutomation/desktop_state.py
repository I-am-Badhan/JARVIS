from dataclasses import dataclass
from typing import Optional

@dataclass
class LastOpenedApp:
    registry_key: str
    process_name: str
    hwnd: Optional[int] = None

_state: Optional[LastOpenedApp] = None

def set_last_opened(registry_key: str, process_name: str, hwnd: Optional[int] = None) -> None:
    global _state
    _state = LastOpenedApp(registry_key=registry_key, process_name=process_name, hwnd=hwnd)

def get_last_opened() -> Optional[LastOpenedApp]:
    return _state

def clear_last_opened() -> None:
    global _state
    _state = None