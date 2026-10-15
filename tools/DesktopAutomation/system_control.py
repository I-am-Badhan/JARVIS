import os
import asyncio
import logging
import platform
import ctypes
from ctypes import cast, POINTER
from typing import Optional, Dict, Any
import psutil

from livekit.agents import function_tool, RunContext, ToolError

logger = logging.getLogger("desktop_automation.system")
OS_TYPE = platform.system().lower()

# Win32 Virtual-Key Codes for Hardware Media Keys
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_STOP = 0xB2
VK_MEDIA_PLAY_PAUSE = 0xB3

# ---------------------------------------------------------------------------
# Audio Control (pycaw Version-Agnostic + COM Safe)
# ---------------------------------------------------------------------------

def _get_audio_endpoint():
    """pycaw-এর যেকোনো ভার্সনের (নতুন ও পুরাতন) সাথে সামঞ্জস্যপূর্ণ অডিও ইন্টারফেস তৈরি করে।"""
    import comtypes
    comtypes.CoInitialize()
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    if not devices:
        raise ToolError("System speaker device detect nahi hua.")

    # ১. আধুনিক pycaw ভার্সনের ক্ষেত্রে EndpointVolume প্রপার্টি থাকে
    if hasattr(devices, "EndpointVolume") and devices.EndpointVolume is not None:
        return devices.EndpointVolume

    # ২. AudioDevice র‍্যাপারের ভেতরের IMMDevice পয়েন্টার বের করা
    raw_dev = getattr(devices, "_dev", getattr(devices, "device", devices))

    # ৩. IMMDevice থেকে IAudioEndpointVolume সক্রিয় করা
    interface = raw_dev.Activate(IAudioEndpointVolume._iid_, comtypes.CLSCTX_ALL, None)
    try:
        return cast(interface, POINTER(IAudioEndpointVolume))
    except Exception:
        return interface.QueryInterface(IAudioEndpointVolume)


def _sync_set_volume(volume_percent: int) -> int:
    volume_percent = max(0, min(100, volume_percent))
    endpoint = _get_audio_endpoint()
    endpoint.SetMasterVolumeLevelScalar(volume_percent / 100.0, None)
    return volume_percent


def _sync_get_volume() -> Dict[str, Any]:
    endpoint = _get_audio_endpoint()
    current_scalar = endpoint.GetMasterVolumeLevelScalar()
    is_muted = bool(endpoint.GetMute())
    return {
        "volume": int(round(current_scalar * 100)),
        "is_muted": is_muted
    }


def _sync_set_mute(mute: Optional[bool] = None) -> bool:
    endpoint = _get_audio_endpoint()
    current_mute = bool(endpoint.GetMute())
    target_mute = (not current_mute) if mute is None else mute
    endpoint.SetMute(int(target_mute), None)
    return target_mute


@function_tool(
    name="set_system_volume",
    description="Set the computer master audio volume to a specific percentage (0 to 100)."
)
async def set_system_volume(context: RunContext, volume_percent: int) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Audio control is currently only supported on Windows.")

    try:
        val = await asyncio.to_thread(_sync_set_volume, volume_percent)
        return f"Boss, system volume {val}% par set kar diya gaya hai."
    except Exception as e:
        raise ToolError(f"Volume change failed: {e}")


@function_tool(
    name="change_system_volume",
    description="Increase or decrease computer volume by a relative amount (e.g. +10, -15)."
)
async def change_system_volume(context: RunContext, delta_percent: int) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Audio control is only supported on Windows.")

    try:
        status = await asyncio.to_thread(_sync_get_volume)
        new_vol = status["volume"] + delta_percent
        val = await asyncio.to_thread(_sync_set_volume, new_vol)
        direction = "badha kar" if delta_percent > 0 else "kam karke"
        return f"Boss, volume {direction} {val}% kar diya gaya hai."
    except Exception as e:
        raise ToolError(f"Volume adjustment failed: {e}")


@function_tool(
    name="mute_system_volume",
    description="Mute, unmute, or toggle system master volume."
)
async def mute_system_volume(context: RunContext, mute: Optional[bool] = None) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Audio control is only supported on Windows.")

    try:
        is_muted = await asyncio.to_thread(_sync_set_mute, mute)
        state_str = "mute" if is_muted else "unmute"
        return f"Boss, system volume {state_str} kar diya gaya hai."
    except Exception as e:
        raise ToolError(f"Mute toggle failed: {e}")


@function_tool(
    name="get_system_volume",
    description="Get the current computer volume level and mute status."
)
async def get_system_volume(context: RunContext) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Audio status is only supported on Windows.")

    try:
        status = await asyncio.to_thread(_sync_get_volume)
        mute_text = " (Muted)" if status["is_muted"] else ""
        return f"Boss, current system volume {status['volume']}% hai{mute_text}."
    except Exception as e:
        raise ToolError(f"Volume fetch failed: {e}")


# ---------------------------------------------------------------------------
# Display & Brightness Control (screen_brightness_control)
# ---------------------------------------------------------------------------

def _sync_set_brightness(level: int) -> int:
    import screen_brightness_control as sbc
    level = max(0, min(100, level))
    sbc.set_brightness(level)
    return level


def _sync_get_brightness() -> int:
    import screen_brightness_control as sbc
    current = sbc.get_brightness()
    if isinstance(current, list):
        return current[0]
    return current


@function_tool(
    name="set_screen_brightness",
    description="Set the display/screen brightness to a specific percentage (0 to 100)."
)
async def set_screen_brightness(context: RunContext, brightness_percent: int) -> str:
    try:
        val = await asyncio.to_thread(_sync_set_brightness, brightness_percent)
        return f"Boss, screen brightness {val}% par set kar diya hai."
    except Exception as e:
        raise ToolError(f"Brightness change failed: {e}. Monitor DDC/CI support check karein.")


@function_tool(
    name="change_screen_brightness",
    description="Increase or decrease screen brightness by a relative offset (e.g. +10, -20)."
)
async def change_screen_brightness(context: RunContext, delta_percent: int) -> str:
    try:
        current = await asyncio.to_thread(_sync_get_brightness)
        new_val = current + delta_percent
        val = await asyncio.to_thread(_sync_set_brightness, new_val)
        direction = "badha kar" if delta_percent > 0 else "kam karke"
        return f"Boss, brightness {direction} {val}% kar diya gaya hai."
    except Exception as e:
        raise ToolError(f"Brightness adjustment failed: {e}")


@function_tool(
    name="turn_off_display",
    description="Turn off the monitor/display screen to save power (screen wakes up on mouse move)."
)
async def turn_off_display(context: RunContext) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Display sleep is only supported on Windows.")

    try:
        HWND_BROADCAST = 0xFFFF
        WM_SYSCOMMAND = 0x0112
        SC_MONITORPOWER = 0xF170
        ctypes.windll.user32.SendMessageW(HWND_BROADCAST, WM_SYSCOMMAND, SC_MONITORPOWER, 2)
        return "Boss, monitor display turn off kar diya gaya hai."
    except Exception as e:
        raise ToolError(f"Display sleep failed: {e}")


# ---------------------------------------------------------------------------
# Power, Security & System Control
# ---------------------------------------------------------------------------

@function_tool(
    name="lock_workstation",
    description="Immediately lock the computer screen (Windows Lock screen)."
)
async def lock_workstation(context: RunContext) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Lock screen is only supported on Windows.")

    try:
        ctypes.windll.user32.LockWorkStation()
        return "Boss, PC lock kar diya gaya hai."
    except Exception as e:
        raise ToolError(f"PC lock failed: {e}")


@function_tool(
    name="sleep_computer",
    description="Put the computer into Sleep/Standby mode."
)
async def sleep_computer(context: RunContext) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Sleep mode is only supported on Windows.")

    try:
        ctypes.windll.powrprof.SetSuspendState(0, 1, 0)
        return "Boss, PC sleep mode mein switch ho raha hai."
    except Exception as e:
        raise ToolError(f"PC sleep failed: {e}")


@function_tool(
    name="shutdown_or_restart_pc",
    description="Schedule a shutdown or restart for the computer. Includes safety countdown timer."
)
async def shutdown_or_restart_pc(
    context: RunContext,
    restart: bool = False,
    timer_seconds: int = 45
) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Shutdown control is only supported on Windows.")

    flag = "/r" if restart else "/s"
    action_text = "restart" if restart else "shutdown"
    
    cmd = f"shutdown {flag} /t {max(5, timer_seconds)} /c \"JARVIS scheduled {action_text}\""
    os.system(cmd)
    return f"Boss, PC {timer_seconds} seconds mein {action_text} hoga. Cancel karne ke liye 'cancel shutdown' bolein."


@function_tool(
    name="cancel_pc_shutdown",
    description="Cancel any pending scheduled shutdown or restart."
)
async def cancel_pc_shutdown(context: RunContext) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Shutdown control is only supported on Windows.")

    res = os.system("shutdown /a")
    if res == 0:
        return "Boss, scheduled shutdown/restart successfully cancel kar diya gaya hai."
    return "Boss, koi pending shutdown schedule nahi mila."


# ---------------------------------------------------------------------------
# Global System Media Controls (Spotify, YouTube, VLC, Media Players)
# ---------------------------------------------------------------------------

def _send_media_key(vk_code: int):
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)  # KEYEVENTF_KEYUP


@function_tool(
    name="system_media_control",
    description="Globally control system media playback (Spotify, browser, music players): 'play_pause', 'next', 'previous', 'stop'."
)
async def system_media_control(context: RunContext, action: str) -> str:
    if OS_TYPE != "windows":
        raise ToolError("Media control is only supported on Windows.")

    act = action.strip().lower()
    if any(k in act for k in ["play", "pause", "resume", "toggle"]):
        _send_media_key(VK_MEDIA_PLAY_PAUSE)
        return "Boss, media playback play/pause toggle kar diya gaya hai."
    elif any(k in act for k in ["next", "forward", "agla"]):
        _send_media_key(VK_MEDIA_NEXT_TRACK)
        return "Boss, next track par switch kar diya hai."
    elif any(k in act for k in ["prev", "previous", "pichhla", "back"]):
        _send_media_key(VK_MEDIA_PREV_TRACK)
        return "Boss, previous track par switch kar diya hai."
    elif any(k in act for k in ["stop", "band"]):
        _send_media_key(VK_MEDIA_STOP)
        return "Boss, media playback stop kar diya gaya hai."
    else:
        raise ToolError(f"Action '{action}' samjh nahi aaya. Use 'play_pause', 'next', ya 'previous'.")


# ---------------------------------------------------------------------------
# Battery, CPU & Hardware Metrics
# ---------------------------------------------------------------------------

@function_tool(
    name="get_hardware_metrics",
    description="Check CPU usage, RAM usage, and battery/power percentage."
)
async def get_hardware_metrics(context: RunContext) -> str:
    cpu_usage = psutil.cpu_percent(interval=0.2)
    ram = psutil.virtual_memory()
    battery = psutil.sensors_battery()

    battery_info = "Battery status unavailable (Desktop PC)"
    if battery:
        plugged = "Charging" if battery.power_plugged else "Discharging"
        battery_info = f"Battery: {battery.percent}% ({plugged})"

    return (
        f"System Status:\n"
        f"* CPU Usage: {cpu_usage}%\n"
        f"* RAM Usage: {ram.percent}% ({round(ram.used / (1024**3), 1)}GB / {round(ram.total / (1024**3), 1)}GB)\n"
        f"* {battery_info}"
    )