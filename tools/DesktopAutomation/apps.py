import asyncio
import logging
import platform
import subprocess

import psutil

from livekit.agents import function_tool, RunContext, ToolError

from .desktop_registry import APP_REGISTRY, resolve_app
from .desktop_state import set_last_opened, clear_last_opened, get_last_opened

logger = logging.getLogger("desktop_automation")
OS_TYPE = platform.system().lower()

STARTUP_TIMEOUT_S = 6.0
POLL_INTERVAL_S = 0.2
SHUTDOWN_TIMEOUT_S = 4.0


def _is_process_running(process_name: str) -> psutil.Process | None:
    """Return the first matching running process, or None."""
    target = process_name.lower()
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target:
                return proc
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


async def _wait_until_running(process_name: str, timeout_s: float) -> psutil.Process | None:
    elapsed = 0.0
    while elapsed < timeout_s:
        proc = _is_process_running(process_name)
        if proc:
            return proc
        await asyncio.sleep(POLL_INTERVAL_S)
        elapsed += POLL_INTERVAL_S
    return None


async def _wait_until_stopped(process_name: str, timeout_s: float) -> bool:
    elapsed = 0.0
    while elapsed < timeout_s:
        if _is_process_running(process_name) is None:
            return True
        await asyncio.sleep(POLL_INTERVAL_S)
        elapsed += POLL_INTERVAL_S
    return False


@function_tool()
async def open_application(
    context: RunContext,
    app_name: str,
) -> str:
    """Open a known desktop application by name.

    Only apps JARVIS actually recognizes can be opened (e.g. "chrome",
    "notepad", "calculator", "spotify", "vscode", "word", "excel",
    "discord", "vlc", "terminal", "settings"). If the name isn't
    recognized, this tool fails instead of guessing.

    Args:
        app_name: Name of the application to open

    Returns:
        Confirmation that the app was verified running
    """
    key = resolve_app(app_name)
    if key is None:
        raise ToolError(
            f"'{app_name}' JARVIS ke registry mein nahi hai, isliye open nahi kar sakta. "
            f"Please exact app name bolo ya registry mein add karwao."
        )

    entry = APP_REGISTRY[key]
    launch_cmd = entry["cmd"].get(OS_TYPE)
    process_name = entry["process"].get(OS_TYPE)

    if not launch_cmd or not process_name:
        raise ToolError(f"'{key}' is not supported on {OS_TYPE}.")

    # already running? don't relaunch, just report + track it
    existing = _is_process_running(process_name)
    if existing:
        set_last_opened(key, process_name, existing.pid)
        return f"Boss, {key} pehle se hi chal raha hai."

    logger.info(f"Launching '{key}' via: {launch_cmd}")

    try:
        if OS_TYPE == "windows":
            # no shell=True with raw LLM input - launch_cmd only ever comes
            # from our own registry, never directly from app_name
            subprocess.Popen(["cmd", "/c", "start", "", launch_cmd], shell=False)
        elif OS_TYPE == "darwin":
            subprocess.Popen(["open", "-a", launch_cmd])
        else:
            subprocess.Popen(launch_cmd.split())
    except Exception as e:
        logger.error(f"Launch failed for {key}: {e}")
        raise ToolError(f"Boss, {key} launch karne mein command hi fail ho gaya: {e}")

    proc = await _wait_until_running(process_name, STARTUP_TIMEOUT_S)

    if proc is None:
        raise ToolError(
            f"Boss, {key} launch command chala diya tha lekin {STARTUP_TIMEOUT_S}s mein "
            f"process start hote hue verify nahi hua. Shayad slow load ho raha hai, ya fail ho gaya."
        )

    set_last_opened(key, process_name, proc.pid)
    return f"Boss, {key} khul gaya aur verify ho gaya (pid {proc.pid})."


@function_tool()
async def close_application(
    context: RunContext,
    app_name: str,
) -> str:
    """Close a running application by name, with real verification.

    Args:
        app_name: Name of the application to close

    Returns:
        Confirmation that the app was verified closed
    """
    key = resolve_app(app_name)
    if key is None:
        raise ToolError(f"'{app_name}' JARVIS ke registry mein nahi hai, close nahi kar sakta.")

    entry = APP_REGISTRY[key]
    process_name = entry["process"].get(OS_TYPE)
    if not process_name:
        raise ToolError(f"'{key}' is not supported on {OS_TYPE}.")

    proc = _is_process_running(process_name)
    if proc is None:
        return f"Boss, {key} already band hai (running hi nahi mila)."

    try:
        proc.terminate()
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        raise ToolError(f"Boss, {key} ko terminate karne ki permission nahi mili: {e}")

    stopped = await _wait_until_stopped(process_name, SHUTDOWN_TIMEOUT_S)

    if not stopped:
        # escalate: graceful terminate didn't work, force kill
        proc_retry = _is_process_running(process_name)
        if proc_retry:
            try:
                proc_retry.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        stopped = await _wait_until_stopped(process_name, SHUTDOWN_TIMEOUT_S)

    if not stopped:
        raise ToolError(f"Boss, {key} band karne ki koshish ki lekin process abhi bhi chal raha hai.")

    last = get_last_opened()
    if last and last.registry_key == key:
        clear_last_opened()

    return f"Boss, {key} verify ho ke band ho gaya."


@function_tool()
async def switch_to_application(
    context: RunContext,
    app_name: str,
) -> str:
    """Bring an already-running application's window to the foreground.

    Args:
        app_name: Name of the application to switch to

    Returns:
        Confirmation that focus was verified switched
    """
    key = resolve_app(app_name)
    if key is None:
        raise ToolError(f"'{app_name}' JARVIS ke registry mein nahi hai.")

    entry = APP_REGISTRY[key]
    process_name = entry["process"].get(OS_TYPE)
    proc = _is_process_running(process_name) if process_name else None

    if proc is None:
        raise ToolError(f"Boss, {key} abhi chal hi nahi raha, switch kaise karu.")

    if OS_TYPE == "windows":
        import win32gui
        import win32con
        import win32process

        matched_hwnd = None

        def enum_handler(hwnd, _results):
            nonlocal matched_hwnd
            if not win32gui.IsWindowVisible(hwnd):
                return
            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
            if found_pid == proc.pid:
                matched_hwnd = hwnd

        win32gui.EnumWindows(enum_handler, None)

        if matched_hwnd is None:
            raise ToolError(f"Boss, {key} process chal raha hai lekin koi visible window nahi mila.")

        win32gui.ShowWindow(matched_hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(matched_hwnd)

        # verify
        await asyncio.sleep(0.2)
        if win32gui.GetForegroundWindow() != matched_hwnd:
            raise ToolError(f"Boss, {key} par switch try kiya lekin foreground verify nahi hua.")

        set_last_opened(key, process_name, proc.pid)
        return f"Boss, {key} par switch ho gaya, verified."

    elif OS_TYPE == "darwin":
        launch_cmd = entry["cmd"].get("darwin")
        result = subprocess.run(
            ["osascript", "-e", f'tell application "{launch_cmd}" to activate'],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise ToolError(f"Boss, {key} activate karne mein fail: {result.stderr.strip()}")
        set_last_opened(key, process_name, proc.pid)
        return f"Boss, {key} par switch ho gaya."

    else:
        launch_cmd = entry["cmd"].get("linux")
        result = subprocess.run(["wmctrl", "-xa", launch_cmd], capture_output=True, text=True)
        if result.returncode != 0:
            raise ToolError(f"Boss, {key} par switch fail hua (wmctrl): {result.stderr.strip()}")
        set_last_opened(key, process_name, proc.pid)
        return f"Boss, {key} par switch ho gaya."