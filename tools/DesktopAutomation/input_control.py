import asyncio
import logging
import platform
from typing import Optional

from livekit.agents import function_tool, RunContext, ToolError
from .desktop_state import get_last_opened
from .apps import _get_all_visible_hwnds, _force_foreground_window

logger = logging.getLogger("desktop_automation")
OS_TYPE = platform.system().lower()


def _ensure_active_focus(last) -> bool:
    if OS_TYPE != "windows" or not last or not last.hwnd:
        return True

    import win32gui
    fg_hwnd = win32gui.GetForegroundWindow()

    # উইন্ডো এখনো ফোকাসে থাকলে সরাসরি অনুমতি দেওয়া
    if fg_hwnd == last.hwnd:
        return True

    # যদি ডায়ালগ ওপেন হয়ে থাকে বা HWND বদলে যায়, পুনরায় সক্রিয় উইন্ডো বের করা
    hwnds = _get_all_visible_hwnds(last.process_name, getattr(last, "registry_key", ""))
    if hwnds:
        valid_hwnd = hwnds[0]
        _force_foreground_window(valid_hwnd)
        last.hwnd = valid_hwnd
        return True

    return False


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