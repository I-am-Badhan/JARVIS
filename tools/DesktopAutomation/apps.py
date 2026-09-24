import asyncio
import ctypes
from ctypes import wintypes
import logging
import platform
import subprocess
from typing import Optional, List
import psutil

from livekit.agents import function_tool, RunContext, ToolError
from .desktop_registry import resolve_app_dynamically, refresh_installed_apps
from .desktop_state import set_last_opened, clear_last_opened, get_last_opened

logger = logging.getLogger("desktop_automation")
OS_TYPE = platform.system().lower()

STARTUP_TIMEOUT_S = 8.0
POLL_INTERVAL_S = 0.3
DWMWA_CLOAKED = 14


def _is_window_cloaked(hwnd: int) -> bool:
    """উইন্ডোটি ব্যাকগ্রাউন্ডে সাসপেন্ডেড বা ভার্চুয়াল ডেস্কটপে লুকানো কি না যাচাই করে।"""
    if OS_TYPE != "windows":
        return False
    try:
        cloaked = ctypes.c_int(0)
        res = ctypes.windll.dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd),
            ctypes.c_uint(DWMWA_CLOAKED),
            ctypes.byref(cloaked),
            ctypes.sizeof(cloaked)
        )
        if res == 0:
            return cloaked.value != 0
    except Exception:
        pass
    return False


def _release_all_modifiers():
    """আটকে থাকা কীবোর্ড মডিফায়ার কি তাৎক্ষণিক রিলিজ করে।"""
    if OS_TYPE != "windows":
        return
    import win32api
    import win32con

    vks = [
        win32con.VK_MENU, win32con.VK_LMENU, win32con.VK_RMENU,
        win32con.VK_CONTROL, win32con.VK_LCONTROL, win32con.VK_RCONTROL,
        win32con.VK_SHIFT
    ]
    for vk in vks:
        try:
            win32api.keybd_event(vk, 0, win32con.KEYEVENTF_KEYUP, 0)
        except Exception:
            pass


def _get_all_matching_pids(process_name: str) -> List[int]:
    target = process_name.lower()
    pids = []
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target:
                pids.append(proc.info["pid"])
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return pids


def _get_all_visible_hwnds(process_name: str, app_name: str = "") -> List[int]:
    """ঘোস্ট/সাসপেন্ডেড উইন্ডো বাদ দিয়ে কেবলমাত্র দৃশ্যমান উইন্ডো হ্যান্ডেল ফিল্টার করে।"""
    if OS_TYPE != "windows":
        return []

    import win32gui
    import win32process

    target_pids = set(_get_all_matching_pids(process_name))
    frame_host_pids = set(_get_all_matching_pids("ApplicationFrameHost.exe"))
    hwnds = []

    def enum_handler(hwnd, _):
        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return

        if _is_window_cloaked(hwnd):
            return

        rect = win32gui.GetWindowRect(hwnd)
        if (rect[2] - rect[0] <= 0) or (rect[3] - rect[1] <= 0):
            return

        title = win32gui.GetWindowText(hwnd).strip()
        if not title:
            return

        # Explorer শেল বাদ দেওয়া
        if process_name.lower() == "explorer.exe" and title in ["Program Manager", ""]:
            return

        _, found_pid = win32process.GetWindowThreadProcessId(hwnd)

        if found_pid in target_pids:
            hwnds.append(hwnd)
            return

        # UWP Apps (Calculator, Settings)
        if found_pid in frame_host_pids:
            clean_app = app_name.lower()
            clean_title = title.lower()
            if clean_app and (clean_app in clean_title or clean_title in clean_app):
                hwnds.append(hwnd)
            elif "calculator" in clean_title and "calc" in process_name.lower():
                hwnds.append(hwnd)

    win32gui.EnumWindows(enum_handler, None)
    return hwnds


def _find_visible_hwnd_by_process(process_name: str, app_name: str = "") -> Optional[int]:
    """ইনপুট কন্ট্রোল ও অন্যান্য মডিউলের জন্য সুরক্ষিত উন্মুক্ত হেল্পার।"""
    hwnds = _get_all_visible_hwnds(process_name, app_name)
    return hwnds[0] if hwnds else None


def _force_foreground_window(hwnd: int) -> bool:
    """উইন্ডোকে Alt কি প্রেস ছাড়াই পরিষ্কারভাবে সামনে আনে (KeyTips রিবন আসবে না)।"""
    if OS_TYPE != "windows" or not hwnd:
        return False

    import win32gui
    import win32con

    if not win32gui.IsWindow(hwnd):
        return False

    try:
        _release_all_modifiers()

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        else:
            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

        # Alt কি ছাড়া উইন্ডোজের নেটিভ ফোকাস সুইচ (KeyTips প্রিভেন্ট করে)
        ctypes.windll.user32.SwitchToThisWindow(wintypes.HWND(hwnd), True)
        win32gui.BringWindowToTop(hwnd)

        _release_all_modifiers()
        return True
    except Exception as e:
        logger.warning(f"Foreground adjustment fallback: {e}")
        return False


@function_tool(
    name="manage_window_state",
    description="Maximize, Minimize, Restore, or Fullscreen the active application window or a specific application."
)
async def manage_window_state(
    context: RunContext,
    action: str,
    app_name: Optional[str] = None
) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Window state management is only supported on Windows.")

    import win32gui
    import win32con

    target_hwnd = None
    if app_name:
        app_info = resolve_app_dynamically(app_name)
        if app_info:
            hwnds = _get_all_visible_hwnds(app_info["process"], app_info["name"])
            if hwnds:
                target_hwnd = hwnds[0]

    if not target_hwnd:
        last = get_last_opened()
        if last and last.hwnd and win32gui.IsWindow(last.hwnd):
            target_hwnd = last.hwnd
        else:
            target_hwnd = win32gui.GetForegroundWindow()

    if not target_hwnd or not win32gui.IsWindow(target_hwnd):
        raise ToolError("Koi active window nahi mila jise resize kiya ja sake.")

    act = action.strip().lower()
    _force_foreground_window(target_hwnd)

    if "max" in act or "bada" in act or "full" in act:
        win32gui.ShowWindow(target_hwnd, win32con.SW_MAXIMIZE)
        return "Boss, window maximize kar diya gaya hai."
    elif "min" in act or "hide" in act:
        win32gui.ShowWindow(target_hwnd, win32con.SW_MINIMIZE)
        return "Boss, window minimize kar diya gaya hai."
    elif "restore" in act or "normal" in act or "chhota" in act:
        win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
        return "Boss, window restore kar diya gaya hai."
    else:
        raise ToolError(f"Action '{action}' samjh nahi aaya. Use 'maximize', 'minimize', ya 'restore'.")


@function_tool(
    name="open_application",
    description="Open any desktop application installed on the computer. If already open, switches to it unless new_window=True."
)
async def open_application(
    context: RunContext,
    app_name: str,
    new_window: bool = False
) -> str:
    app_info = resolve_app_dynamically(app_name)
    if not app_info:
        raise ToolError(f"'{app_name}' computer mein installed nahi mila.")

    key = app_info["name"]
    launch_cmd = app_info["cmd"]
    process_name = app_info["process"]

    existing_hwnds = _get_all_visible_hwnds(process_name, key)

    if not new_window and existing_hwnds:
        top_hwnd = existing_hwnds[0]
        _force_foreground_window(top_hwnd)
        set_last_opened(key, process_name, top_hwnd)
        return f"Boss, {key} pehle se open tha, screen par focus kar diya hai."

    logger.info(f"Launching '{key}' (new_window={new_window}) via: {launch_cmd}")
    try:
        if OS_TYPE == "windows":
            if key == "explorer" and new_window:
                subprocess.Popen("explorer.exe /n", shell=True)
            else:
                subprocess.Popen(f"start \"\" {launch_cmd}", shell=True)
        else:
            subprocess.Popen(launch_cmd.split())
    except Exception as e:
        raise ToolError(f"Boss, {key} launch karne mein error: {e}")

    elapsed = 0.0
    while elapsed < STARTUP_TIMEOUT_S:
        current_hwnds = _get_all_visible_hwnds(process_name, key)
        new_created = [h for h in current_hwnds if h not in existing_hwnds]
        target_hwnd = new_created[0] if new_created else (current_hwnds[0] if current_hwnds else None)

        if target_hwnd:
            _force_foreground_window(target_hwnd)
            set_last_opened(key, process_name, target_hwnd)
            status_text = "naya window" if new_window else "window"
            return f"Boss, {key} ka {status_text} successfully open aur focus ho gaya hai."

        await asyncio.sleep(POLL_INTERVAL_S)
        elapsed += POLL_INTERVAL_S

    raise ToolError(f"Boss, {key} launch command execute hua lekin window verify nahi hui.")


@function_tool(
    name="switch_to_application",
    description="Switch focus to an open application or specific window title."
)
async def switch_to_application(
    context: RunContext,
    app_name: str,
    window_title_keyword: Optional[str] = None
) -> str:
    app_info = resolve_app_dynamically(app_name)
    if not app_info:
        raise ToolError(f"'{app_name}' application detect nahi hua.")

    key = app_info["name"]
    process_name = app_info["process"]
    hwnds = _get_all_visible_hwnds(process_name, key)

    if not hwnds:
        raise ToolError(f"Boss, {key} ka koi open window nahi mila.")

    target_hwnd = hwnds[0]

    if window_title_keyword and OS_TYPE == "windows":
        import win32gui
        for h in hwnds:
            if win32gui.IsWindow(h) and window_title_keyword.lower() in win32gui.GetWindowText(h).lower():
                target_hwnd = h
                break

    _force_foreground_window(target_hwnd)
    set_last_opened(key, process_name, target_hwnd)
    return f"Boss, {key} window par successfully switch ho gaya."


@function_tool(
    name="close_application",
    description="Close an application window safely without crashing or leaving zombie processes."
)
async def close_application(
    context: RunContext,
    app_name: str,
    close_all_instances: bool = False,
    force: bool = False
) -> str:
    app_info = resolve_app_dynamically(app_name)
    if not app_info:
        raise ToolError(f"'{app_name}' detect nahi hua.")

    key = app_info["name"]
    process_name = app_info["process"]

    if key == "explorer":
        hwnds = _get_all_visible_hwnds("explorer.exe", "explorer")
        if not hwnds:
            return "Boss, File Explorer ka koi khula window nahi mila."

        import win32gui
        import win32con
        to_close = hwnds if close_all_instances else [hwnds[0]]
        for h in to_close:
            try:
                if win32gui.IsWindow(h):
                    win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
            except Exception:
                pass
        clear_last_opened()
        return f"Boss, File Explorer ka {'saare' if close_all_instances else 'ek'} window close kar diya gaya hai."

    if OS_TYPE == "windows":
        import win32gui
        import win32con

        hwnds = _get_all_visible_hwnds(process_name, key)

        if hwnds and not force:
            to_close = hwnds if close_all_instances else [hwnds[0]]
            for h in to_close:
                try:
                    if win32gui.IsWindow(h):
                        win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
                except Exception as e:
                    logger.warning(f"Error closing hwnd {h}: {e}")

            await asyncio.sleep(0.4)

            still_hwnds = _get_all_visible_hwnds(process_name, key)
            if still_hwnds and key in ["notepad", "word", "excel"]:
                return f"Boss, {key} mein unsaved changes hain, isliye dialog aaya hai."
            elif still_hwnds and key in ["calculator", "calc"]:
                subprocess.run(["taskkill", "/F", "/IM", process_name, "/T"], capture_output=True)
                clear_last_opened()
                return f"Boss, {key} band kar diya gaya hai."
            else:
                clear_last_opened()
                return f"Boss, {key} window successfully close ho gaya hai."

        if force or close_all_instances or not hwnds:
            if _get_all_matching_pids(process_name):
                subprocess.run(["taskkill", "/F", "/IM", process_name, "/T"], capture_output=True)
                clear_last_opened()
                return f"Boss, {key} band kar diya gaya hai."

        return f"Boss, {key} already band hai."

    else:
        for pid in _get_all_matching_pids(process_name):
            try:
                psutil.Process(pid).terminate()
            except:
                pass
        clear_last_opened()
        return f"Boss, {key} band kar diya gaya hai."


@function_tool(
    name="rescan_installed_apps",
    description="Rescan the system for newly installed applications."
)
async def rescan_installed_apps(context: RunContext) -> str:
    refresh_installed_apps()
    return "Boss, system ke saare apps ka index refresh ho gaya hai."



# NOTE: `open_website` (webbrowser.open) and `close_tab` (pyautogui Ctrl+W)
# were removed from here. Both acted on whatever Chrome window the OS
# considered "default" / "foreground", which is a *different* browser
# session than the one browser_automation.py's tools control over CDP
# (`~/.jarvis_chrome_profile` on port 9222). Having both registered as
# tools let the LLM pick either one non-deterministically — e.g. "open X"
# would land in your normal Chrome window via open_website, but the very
# next "close it" would go through close_browser_tab (CDP-based) and spin
# up a *second*, unrelated automation window, since it had no idea the
# first window even existed.
#
# web_navigate / close_browser_tab / web_click_element etc. in
# browser_automation.py fully replace these two and always share one
# persistent CDP session, so open -> click -> close now consistently act
# on the same window. Route ALL website-opening/closing through those
# instead of re-adding tools here.