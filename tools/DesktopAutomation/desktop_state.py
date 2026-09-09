"""
Tiny in-memory tracker for "which app did JARVIS most recently open/focus".

Why this exists: type_text and similar input tools must never blindly type
into whatever window happens to have focus. Before typing, they check that
the CURRENT foreground window actually belongs to the app JARVIS thinks
it's talking to. This module is what lets them know what to expect.

Single-process, single-session assumption (fine for a local voice
assistant). If you later run multiple concurrent sessions, key this dict
by session/room id instead of using module-level globals.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class LastOpenedApp:
    registry_key: str
    process_name: str
    pid: Optional[int] = None


_state: Optional[LastOpenedApp] = None


def set_last_opened(registry_key: str, process_name: str, pid: Optional[int] = None) -> None:
    global _state
    _state = LastOpenedApp(registry_key=registry_key, process_name=process_name, pid=pid)


def get_last_opened() -> Optional[LastOpenedApp]:
    return _state


def clear_last_opened() -> None:
    global _state
    _state = None