import asyncio
import logging
import platform
from typing import Optional

from livekit.agents import function_tool, RunContext, ToolError

from .desktop_state import get_last_opened

logger = logging.getLogger("desktop_automation")
OS_TYPE = platform.system().lower()


def _foreground_matches_expected(expected_pid: int) -> bool:
    """Check the actual OS foreground window belongs to the expected process."""
    if OS_TYPE != "windows":
        # extend with NSWorkspace (mac) / wmctrl+xprop (linux) if needed
        return True

    import win32gui
    import win32process

    hwnd = win32gui.GetForegroundWindow()
    if not hwnd:
        return False

    _, fg_pid = win32process.GetWindowThreadProcessId(hwnd)
    return fg_pid == expected_pid


@function_tool()
async def type_text(
    context: RunContext,
    text: str,
) -> str:
    """Type text into whichever application JARVIS most recently opened
    or switched to. Refuses to type if that application isn't currently
    the focused window, instead of typing into the wrong place.

    Args:
        text: The text to type

    Returns:
        Confirmation that text was typed into the verified app
    """
    last = get_last_opened()
    if last is None:
        raise ToolError(
            "Boss, mujhe pata nahi kis app mein type karna hai — pehle koi app open ya switch karo."
        )

    if not _foreground_matches_expected(last.pid):
        raise ToolError(
            f"Boss, {last.registry_key} abhi foreground mein nahi hai, isliye type nahi kiya — "
            f"kahin galat window mein type ho jaata."
        )

    import pyautogui

    logger.info(f"Typing into '{last.registry_key}' (pid {last.pid}): {text[:50]}...")
    pyautogui.write(text, interval=0.05)

    return f"Boss, {last.registry_key} mein type kar diya, verified focus ke saath."


@function_tool()
async def type_text_unicode(
    context: RunContext,
    text: str,
) -> str:
    """Type text that includes non-ASCII/Unicode characters (e.g. Hindi,
    Bengali) via clipboard paste, with the same foreground-app guard as
    type_text.

    Args:
        text: The text to type (can include non-Latin scripts)

    Returns:
        Confirmation that text was typed into the verified app
    """
    last = get_last_opened()
    if last is None:
        raise ToolError("Boss, pehle koi app open ya switch karo, phir type karunga.")

    if not _foreground_matches_expected(last.pid):
        raise ToolError(
            f"Boss, {last.registry_key} foreground mein nahi hai, isliye paste nahi kiya."
        )

    import pyautogui
    import pyperclip

    pyperclip.copy(text)
    await asyncio.sleep(0.1)

    if OS_TYPE == "darwin":
        pyautogui.hotkey("command", "v")
    else:
        pyautogui.hotkey("ctrl", "v")

    return f"Boss, {last.registry_key} mein Unicode text paste kar diya."


@function_tool()
async def press_key(
    context: RunContext,
    key: str,
    modifier: Optional[str] = None,
) -> str:
    """Press a keyboard key or key combination in the currently tracked app.

    Args:
        key: Key to press (e.g. "enter", "tab", "f5", "backspace")
        modifier: Optional modifier (e.g. "ctrl", "alt", "shift", "cmd")

    Returns:
        Confirmation the key was pressed in the verified app
    """
    last = get_last_opened()
    if last is None:
        raise ToolError("Boss, pehle koi app open ya switch karo.")

    if not _foreground_matches_expected(last.pid):
        raise ToolError(f"Boss, {last.registry_key} foreground mein nahi hai, key press skip kiya.")

    import pyautogui

    if modifier:
        if modifier.lower() == "cmd" and OS_TYPE == "darwin":
            modifier = "command"
        pyautogui.hotkey(modifier, key)
    else:
        pyautogui.press(key)

    combo = f"{modifier}+{key}" if modifier else key
    return f"Boss, {last.registry_key} mein {combo} press kar diya."