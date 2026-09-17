import asyncio
import logging
import platform
from typing import Optional

from livekit.agents import function_tool, RunContext, ToolError
from .desktop_state import get_last_opened
from .apps import _find_visible_hwnd_by_process, _force_foreground_window

logger = logging.getLogger("desktop_automation")
OS_TYPE = platform.system().lower()


def _ensure_active_focus(last) -> bool:
    """Ensure target window is 100% focused before any keystroke."""
    if OS_TYPE != "windows" or not last.hwnd:
        return True

    import win32gui
    fg_hwnd = win32gui.GetForegroundWindow()

    if fg_hwnd != last.hwnd:
        valid_hwnd = _find_visible_hwnd_by_process(last.process_name)
        if valid_hwnd:
            _force_foreground_window(valid_hwnd)
            last.hwnd = valid_hwnd
            return True
        return False
    return True


@function_tool(description="Type text into the verified active application.")
async def type_text(context: RunContext, text: str) -> str:
    last = get_last_opened()
    if last is None:
        raise ToolError("Boss, pehle koi application open ya switch karo.")

    if not _ensure_active_focus(last):
        raise ToolError(f"Boss, {last.registry_key} foreground mein nahi aa saka.")

    import pyautogui
    await asyncio.sleep(0.15)
    pyautogui.write(text, interval=0.03)
    return f"Boss, {last.registry_key} mein type kar diya."


@function_tool(description="Type Unicode or non-ASCII text (Bengali, Hindi, symbols) via clipboard paste.")
async def type_text_unicode(context: RunContext, text: str) -> str:
    last = get_last_opened()
    if last is None:
        raise ToolError("Boss, pehle koi application open ya switch karo.")

    if not _ensure_active_focus(last):
        raise ToolError(f"Boss, {last.registry_key} foreground mein nahi aa saka.")

    import pyautogui
    import pyperclip

    pyperclip.copy(text)
    await asyncio.sleep(0.15)

    if OS_TYPE == "darwin":
        pyautogui.hotkey("command", "v")
    else:
        pyautogui.hotkey("ctrl", "v")

    return f"Boss, {last.registry_key} mein Unicode text paste kar diya."


@function_tool(description="Press a keyboard key (enter, tab, esc) in active application.")
async def press_key(context: RunContext, key: str, modifier: Optional[str] = None) -> str:
    last = get_last_opened()
    if last is None:
        raise ToolError("Boss, pehle koi app focus karo.")

    if not _ensure_active_focus(last):
        raise ToolError(f"Boss, {last.registry_key} focus nahi ho paya.")

    import pyautogui
    await asyncio.sleep(0.1)

    if modifier:
        if modifier.lower() == "cmd" and OS_TYPE == "darwin":
            modifier = "command"
        pyautogui.hotkey(modifier.lower(), key.lower())
    else:
        pyautogui.press(key.lower())

    combo = f"{modifier}+{key}" if modifier else key
    return f"Boss, {last.registry_key} mein {combo} press kar diya."