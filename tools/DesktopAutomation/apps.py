import asyncio
import logging
import platform
import subprocess
import webbrowser
from typing import Optional
import psutil

from livekit.agents import function_tool, RunContext, ToolError
from .desktop_registry import APP_REGISTRY, resolve_app
from .desktop_state import set_last_opened, clear_last_opened

logger = logging.getLogger("desktop_automation")
OS_TYPE = platform.system().lower()

STARTUP_TIMEOUT_S = 8.0
POLL_INTERVAL_S = 0.3


def _release_all_modifiers():
    """আটকে থাকা Alt, AltGr, Ctrl বা Shift কি থাকলে তাৎক্ষণিক রিলিজ করা।"""
    if OS_TYPE != "windows":
        return

    import win32api
    import win32con

    vks = [
        win32con.VK_MENU,       
        win32con.VK_LMENU,     
        win32con.VK_RMENU,     
        win32con.VK_CONTROL,   
        win32con.VK_LCONTROL,
        win32con.VK_RCONTROL,
        win32con.VK_SHIFT
    ]
    for vk in vks:
        win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)


def _get_all_matching_pids(process_name: str) -> list[int]:
    target = process_name.lower()
    pids = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target:
                pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


def _find_visible_hwnd_by_process(process_name: str) -> int | None:
    if OS_TYPE != "windows":
        return None

    import win32gui
    import win32process

    target_pids = set(_get_all_matching_pids(process_name))
    if not target_pids:
        return None

    matched_hwnd = None

    def enum_handler(hwnd, _):
        nonlocal matched_hwnd
        if not win32gui.IsWindowVisible(hwnd):
            return

        rect = win32gui.GetWindowRect(hwnd)
        if (rect[2] - rect[0] <= 0) or (rect[3] - rect[1] <= 0):
            return

        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return

        if process_name.lower() == "explorer.exe" and title in ["Program Manager", ""]:
            return

        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
        if found_pid in target_pids:
            matched_hwnd = hwnd

    win32gui.EnumWindows(enum_handler, None)
    return matched_hwnd


def _force_foreground_window(hwnd: int) -> bool:
    """Alt কি প্রেস ছাড়াই নিরাপদ Win32 থ্রেড অ্যাটাচমেন্টের মাধ্যমে ফোকাস আনা।"""
    if OS_TYPE != "windows" or not hwnd:
        return False

    import win32gui
    import win32con
    import win32process
    import win32api

    try:
        _release_all_modifiers()

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        cur_thread = win32api.GetCurrentThreadId()
        fg_hwnd = win32gui.GetForegroundWindow()
        
        if fg_hwnd and fg_hwnd != hwnd:
            fg_thread, _ = win32process.GetWindowThreadProcessId(fg_hwnd)
            if fg_thread != cur_thread:
                win32process.AttachThreadInput(cur_thread, fg_thread, True)
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
                win32process.AttachThreadInput(cur_thread, fg_thread, False)
            else:
                win32gui.SetForegroundWindow(hwnd)
                win32gui.BringWindowToTop(hwnd)
        else:
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)

        _release_all_modifiers()
        return True
    except Exception as e:
        logger.warning(f"Focus adjustment failed: {e}")
        return False


@function_tool(
    name="open_website",
    description="Open a specific website or search query directly in the default browser (e.g. YouTube, Facebook, WhatsApp, Google)."
)
async def open_website(context: RunContext, query_or_url: str) -> str:
    target = query_or_url.strip()
    if not target.startswith("http"):
        if "." in target and " " not in target:
            target = f"https://{target}"
        else:
            target = f"https://www.google.com/search?q={target.replace(' ', '+')}"

    webbrowser.open(target)
    await asyncio.sleep(1.0)
    
    for b in ["chrome.exe", "msedge.exe", "firefox.exe"]:
        h = _find_visible_hwnd_by_process(b)
        if h:
            set_last_opened("browser", b, h)
            break

    return f"Opened {target} in browser, sir."


@function_tool(
    name="close_tab",
    description=(
        "Close a specific browser tab (such as Facebook, YouTube, WhatsApp) or the currently active tab. "
        "Use this whenever the user says 'close Facebook', 'close YouTube', 'close tab', or 'tab band karo'. "
        "Do NOT call close_application for websites."
    )
)
async def close_tab(context: RunContext, tab_name: Optional[str] = None) -> str:
    """ব্রাউজারে ফোকাস এনে নির্দিষ্ট ব্যাকগ্রাউন্ড ট্যাব খুঁজে Ctrl+W দিয়ে বন্ধ করা।"""
    import pyautogui

    target_hwnd = None
    for b in ["chrome.exe", "msedge.exe", "firefox.exe"]:
        target_hwnd = _find_visible_hwnd_by_process(b)
        if target_hwnd:
            break

    if not target_hwnd:
        raise ToolError("Boss, koi running browser window nahi mila.")

    _force_foreground_window(target_hwnd)
    await asyncio.sleep(0.2)
    _release_all_modifiers()

    clean_name = tab_name.strip() if tab_name else ""
    if clean_name and clean_name.lower() not in ["tab", "current", "this", "page"]:
        pyautogui.hotkey("ctrl", "shift", "a")
        await asyncio.sleep(0.25)
        pyautogui.write(clean_name, interval=0.03)
        await asyncio.sleep(0.2)
        pyautogui.press("enter")
        await asyncio.sleep(0.25)

    _release_all_modifiers()
    pyautogui.hotkey("ctrl", "w")
    await asyncio.sleep(0.1)
    _release_all_modifiers()

    name = clean_name if clean_name else "active"
    return f"Boss, {name} tab close kar diya gaya hai."


@function_tool(
    name="open_application",
    description="Launch a desktop app and verify its graphical window is visible."
)
async def open_application(context: RunContext, app_name: str) -> str:
    key = resolve_app(app_name)
    if key is None:
        raise ToolError(f"'{app_name}' registry mein nahi hai.")

    entry = APP_REGISTRY[key]
    launch_cmd = entry["cmd"].get(OS_TYPE)
    process_name = entry["process"].get(OS_TYPE)

    if not launch_cmd or not process_name:
        raise ToolError(f"'{key}' {OS_TYPE} par supported nahi hai.")

    is_explorer = (key == "explorer")
    hwnd = _find_visible_hwnd_by_process(process_name)

    if hwnd and not is_explorer:
        _force_foreground_window(hwnd)
        set_last_opened(key, process_name, hwnd)
        return f"Boss, {key} pehle se open tha, samne le aaya hoon."

    try:
        if OS_TYPE == "windows":
            subprocess.Popen(f"start {launch_cmd}", shell=True)
        else:
            subprocess.Popen(launch_cmd.split())
    except Exception as e:
        raise ToolError(f"Launch command failed: {e}")

    elapsed = 0.0
    while elapsed < STARTUP_TIMEOUT_S:
        hwnd = _find_visible_hwnd_by_process(process_name)
        if hwnd:
            _force_foreground_window(hwnd)
            set_last_opened(key, process_name, hwnd)
            return f"Boss, {key} successfully open ho gaya."
        await asyncio.sleep(POLL_INTERVAL_S)
        elapsed += POLL_INTERVAL_S

    raise ToolError(f"Boss, {key} launch hua lekin window verify nahi hui.")


@function_tool(
    name="switch_to_application",
    description="Switch focus to an already running app's window."
)
async def switch_to_application(context: RunContext, app_name: str) -> str:
    key = resolve_app(app_name)
    if key is None:
        raise ToolError(f"'{app_name}' registry mein nahi hai.")

    process_name = APP_REGISTRY[key]["process"].get(OS_TYPE)
    hwnd = _find_visible_hwnd_by_process(process_name)

    if not hwnd:
        raise ToolError(f"Boss, {key} ka koi active window nahi mila.")

    _force_foreground_window(hwnd)
    set_last_opened(key, process_name, hwnd)
    return f"Boss, {key} par successfully switch ho gaya."


@function_tool(
    name="close_application",
    description=(
        "Close an entire running desktop application (e.g. Notepad, Calculator, VS Code, or quitting the entire Chrome browser). "
        "Do NOT use this to close a website or browser tab like YouTube, Facebook, or WhatsApp; use close_tab instead."
    )
)
async def close_application(context: RunContext, app_name: str) -> str:
    key = resolve_app(app_name)
    if key is None:
        raise ToolError(f"'{app_name}' registry mein nahi hai.")

    if key == "explorer":
        hwnd = _find_visible_hwnd_by_process("explorer.exe")
        if hwnd:
            import win32gui
            import win32con
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            clear_last_opened()
            return "Boss, File Explorer window safely close kar diya gaya hai."
        return "Boss, File Explorer ka koi khula window nahi mila."

    process_name = APP_REGISTRY[key]["process"].get(OS_TYPE)

    if OS_TYPE == "windows":
        subprocess.run(["taskkill", "/F", "/IM", process_name, "/T"], capture_output=True)
    else:
        for pid in _get_all_matching_pids(process_name):
            try:
                psutil.Process(pid).kill()
            except:
                pass

    clear_last_opened()
    return f"Boss, {key} application poori tarah band kar diya gaya hai."