"""
Single source of truth for "which apps JARVIS is allowed to open/close".

This is an ALLOW-LIST by design: the LLM can never cause JARVIS to launch
or run an arbitrary string. If an app isn't here (or close enough via
fuzzy match), JARVIS refuses instead of guessing.

Each entry has:
    - "cmd": {os: launch_command_or_path}
    - "process": {os: process image name used to verify it actually started}
"""

import difflib

APP_REGISTRY = {
    "chrome": {
        "cmd": {"windows": "chrome", "darwin": "Google Chrome", "linux": "google-chrome"},
        "process": {"windows": "chrome.exe", "darwin": "Google Chrome", "linux": "chrome"},
    },
    "firefox": {
        "cmd": {"windows": "firefox", "darwin": "Firefox", "linux": "firefox"},
        "process": {"windows": "firefox.exe", "darwin": "firefox", "linux": "firefox"},
    },
    "edge": {
        "cmd": {"windows": "msedge", "darwin": "Microsoft Edge", "linux": "microsoft-edge"},
        "process": {"windows": "msedge.exe", "darwin": "Microsoft Edge", "linux": "msedge"},
    },
    "notepad": {
        "cmd": {"windows": "notepad", "darwin": "TextEdit", "linux": "gedit"},
        "process": {"windows": "notepad.exe", "darwin": "TextEdit", "linux": "gedit"},
    },
    "calculator": {
        "cmd": {"windows": "calc", "darwin": "Calculator", "linux": "gnome-calculator"},
        "process": {"windows": "CalculatorApp.exe", "darwin": "Calculator", "linux": "gnome-calculator"},
    },
    "paint": {
        "cmd": {"windows": "mspaint", "darwin": None, "linux": None},
        "process": {"windows": "mspaint.exe", "darwin": None, "linux": None},
    },
    "explorer": {
        "cmd": {"windows": "explorer", "darwin": "Finder", "linux": "nautilus"},
        "process": {"windows": "explorer.exe", "darwin": "Finder", "linux": "nautilus"},
    },
    "word": {
        "cmd": {"windows": "winword", "darwin": "Microsoft Word", "linux": "libreoffice --writer"},
        "process": {"windows": "WINWORD.EXE", "darwin": "Microsoft Word", "linux": "soffice.bin"},
    },
    "excel": {
        "cmd": {"windows": "excel", "darwin": "Microsoft Excel", "linux": "libreoffice --calc"},
        "process": {"windows": "EXCEL.EXE", "darwin": "Microsoft Excel", "linux": "soffice.bin"},
    },
    "powerpoint": {
        "cmd": {"windows": "powerpnt", "darwin": "Microsoft PowerPoint", "linux": "libreoffice --impress"},
        "process": {"windows": "POWERPNT.EXE", "darwin": "Microsoft PowerPoint", "linux": "soffice.bin"},
    },
    "vscode": {
        "cmd": {"windows": "code", "darwin": "Visual Studio Code", "linux": "code"},
        "process": {"windows": "Code.exe", "darwin": "Electron", "linux": "code"},
    },
    "spotify": {
        "cmd": {"windows": "spotify", "darwin": "Spotify", "linux": "spotify"},
        "process": {"windows": "Spotify.exe", "darwin": "Spotify", "linux": "spotify"},
    },
    "discord": {
        "cmd": {"windows": "discord", "darwin": "Discord", "linux": "discord"},
        "process": {"windows": "Discord.exe", "darwin": "Discord", "linux": "discord"},
    },
    "vlc": {
        "cmd": {"windows": "vlc", "darwin": "VLC", "linux": "vlc"},
        "process": {"windows": "vlc.exe", "darwin": "VLC", "linux": "vlc"},
    },
    "terminal": {
        "cmd": {"windows": "cmd", "darwin": "Terminal", "linux": "gnome-terminal"},
        "process": {"windows": "cmd.exe", "darwin": "Terminal", "linux": "gnome-terminal-server"},
    },
    "settings": {
        "cmd": {"windows": "ms-settings:", "darwin": "System Preferences", "linux": "gnome-control-center"},
        "process": {"windows": "SystemSettings.exe", "darwin": "System Preferences", "linux": "gnome-control-center"},
    },
}


def resolve_app(app_name: str, min_score: float = 0.6):
    """
    Resolve a free-text app name against the registry ONLY.
    Returns the registry key on a confident match, else None.

    This is the safety gate: no matter what string the LLM produces,
    it can only ever resolve to one of the keys defined above.
    """
    name = app_name.strip().lower()

    if name in APP_REGISTRY:
        return name

    # fuzzy match against known keys only (never against arbitrary input)
    matches = difflib.get_close_matches(name, APP_REGISTRY.keys(), n=1, cutoff=min_score)
    if matches:
        return matches[0]

    return None