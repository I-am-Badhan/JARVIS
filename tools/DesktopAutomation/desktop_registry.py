import os
import glob
import winreg
import shutil
import difflib
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("desktop_automation.registry")

BUILTIN_APPS = {
    "chrome": {"cmd": "chrome", "process": "chrome.exe"},
    "edge": {"cmd": "msedge", "process": "msedge.exe"},
    "firefox": {"cmd": "firefox", "process": "firefox.exe"},
    "notepad": {"cmd": "notepad", "process": "notepad.exe"},
    "calculator": {"cmd": "calc", "process": "CalculatorApp.exe"},
    "calc": {"cmd": "calc", "process": "CalculatorApp.exe"},
    "paint": {"cmd": "mspaint", "process": "mspaint.exe"},
    "mspaint": {"cmd": "mspaint", "process": "mspaint.exe"},
    "explorer": {"cmd": "explorer", "process": "explorer.exe"},
    "cmd": {"cmd": "cmd", "process": "cmd.exe"},
    "terminal": {"cmd": "wt", "process": "WindowsTerminal.exe"},
    "taskmanager": {"cmd": "taskmgr", "process": "Taskmgr.exe"},
    "settings": {"cmd": "ms-settings:", "process": "SystemSettings.exe"},
    "vscode": {"cmd": "code", "process": "Code.exe"},
    "code": {"cmd": "code", "process": "Code.exe"},
}

_dynamic_cache: Dict[str, Dict[str, Any]] = {}
_cache_initialized = False


def _scan_start_menu_shortcuts() -> Dict[str, str]:
    shortcuts = {}
    paths = [
        os.path.expandvars(r"%ProgramData%\Microsoft\Windows\Start Menu\Programs"),
        os.path.expandvars(r"%AppData%\Microsoft\Windows\Start Menu\Programs"),
    ]

    for base_path in paths:
        if not os.path.exists(base_path):
            continue
        for lnk_path in glob.glob(os.path.join(base_path, "**", "*.lnk"), recursive=True):
            filename = os.path.splitext(os.path.basename(lnk_path))[0].lower()
            if any(skip in filename for skip in ["uninstall", "setup", "help", "readme", "documentation"]):
                continue
            shortcuts[filename] = lnk_path
    return shortcuts


def _scan_registry_app_paths() -> Dict[str, str]:
    reg_apps = {}
    reg_locations = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths")
    ]

    for hkey, subkey in reg_locations:
        try:
            with winreg.OpenKey(hkey, subkey) as root_key:
                num_subkeys = winreg.QueryInfoKey(root_key)[0]
                for i in range(num_subkeys):
                    try:
                        app_key_name = winreg.EnumKey(root_key, i)
                        with winreg.OpenKey(root_key, app_key_name) as app_key:
                            exe_path, _ = winreg.QueryValueEx(app_key, "")
                            if os.path.exists(exe_path):
                                clean_name = os.path.splitext(app_key_name)[0].lower()
                                reg_apps[clean_name] = exe_path
                    except (OSError, WindowsError):
                        continue
        except (OSError, WindowsError):
            continue
    return reg_apps


def refresh_installed_apps():
    global _dynamic_cache, _cache_initialized
    _dynamic_cache.clear()

    for key, data in BUILTIN_APPS.items():
        _dynamic_cache[key] = {
            "name": key,
            "cmd": data["cmd"],
            "process": data["process"],
            "type": "builtin"
        }

    for name, path in _scan_start_menu_shortcuts().items():
        if name not in _dynamic_cache:
            _dynamic_cache[name] = {
                "name": name,
                "cmd": f'"{path}"',
                "process": os.path.splitext(os.path.basename(path))[0] + ".exe",
                "type": "shortcut"
            }

    for name, path in _scan_registry_app_paths().items():
        if name not in _dynamic_cache:
            _dynamic_cache[name] = {
                "name": name,
                "cmd": f'"{path}"',
                "process": os.path.basename(path),
                "type": "registry"
            }

    _cache_initialized = True
    logger.info(f"Discovered and cached {len(_dynamic_cache)} desktop applications.")


def resolve_app_dynamically(app_name: str, min_score: float = 0.5) -> Optional[Dict[str, Any]]:
    global _cache_initialized
    if not _cache_initialized:
        refresh_installed_apps()

    name = app_name.strip().lower()

    if name in _dynamic_cache:
        return _dynamic_cache[name]

    matches = difflib.get_close_matches(name, _dynamic_cache.keys(), n=1, cutoff=min_score)
    if matches:
        return _dynamic_cache[matches[0]]

    for key, data in _dynamic_cache.items():
        if name in key or key in name:
            return data

    which_path = shutil.which(name)
    if which_path:
        return {
            "name": name,
            "cmd": name,
            "process": os.path.basename(which_path),
            "type": "path"
        }

    refresh_installed_apps()
    if name in _dynamic_cache:
        return _dynamic_cache[name]

    return None