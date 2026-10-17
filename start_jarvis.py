"""JARVIS launcher: keep the agent warm, listen for wake word only while UI is closed."""
import json
import os
import socket
import subprocess
import time
from pathlib import Path

from wake_listener import WakeWordListener

ROOT = Path(r"D:\JARVIS")
LIVEKIT_EXE = Path(r"D:\livekit\livekit-server.exe")
APP_EXE = ROOT / "src-tauri" / "target" / "release" / "app.exe"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
LIVEKIT_HOST, LIVEKIT_PORT = "127.0.0.1", 7880
API_HOST, API_PORT = "127.0.0.1", 8080
ROOM_NAME = "jarvis-room"
AGENT_READY_TIMEOUT = 45.0
# Keep the room alive for 24 hours after the UI participant disconnects.
# LiveKit's default departure_timeout is 20 seconds.
ROOM_DEPARTURE_TIMEOUT_SECONDS = 86400
LOG_DIR = ROOT / "logs"
LOG_HANDLES = []
livekit_process = None
api_process = None
agent_process = None
owns_livekit = False
owns_api = False
owns_agent = False


def log(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def start_hidden(command, cwd, log_name, truncate=False):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handle = open(LOG_DIR / log_name, "w" if truncate else "a", encoding="utf-8", buffering=1)
    LOG_HANDLES.append(handle)
    log(f"Starting background process: {log_name}")
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.Popen(
        command, cwd=str(cwd), stdin=subprocess.DEVNULL,
        stdout=handle, stderr=subprocess.STDOUT, env=child_env,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def close_log_handles(log_name):
    target = (LOG_DIR / log_name).resolve()
    for handle in list(LOG_HANDLES):
        try:
            if Path(handle.name).resolve() == target:
                handle.close()
                LOG_HANDLES.remove(handle)
        except (OSError, ValueError):
            pass


def port_ready(host, port):
    try:
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except OSError:
        return False


def wait_for_port(host, port, process=None, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_ready(host, port):
            return
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"Process exited ({process.returncode}) before {host}:{port} became ready")
        time.sleep(0.15)
    raise TimeoutError(f"Timed out waiting for {host}:{port}")


def stop_process_tree(process, name):
    if process is None or process.poll() is not None:
        return
    log(f"Stopping {name}...")
    try:
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=4, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt):
        try:
            process.kill()
        except (OSError, ProcessLookupError):
            pass
    try:
        process.wait(timeout=1.5)
    except (subprocess.TimeoutExpired, OSError, KeyboardInterrupt):
        pass


def start_background_services():
    global livekit_process, api_process, owns_livekit, owns_api
    if port_ready(LIVEKIT_HOST, LIVEKIT_PORT):
        raise RuntimeError(
            "A LiveKit server is already listening on 127.0.0.1:7880. "
            "The new departure_timeout cannot be applied to an already-running server. "
            "Stop the existing livekit-server.exe, then run start_jarvis.py again."
        )
    if not LIVEKIT_EXE.exists():
        raise FileNotFoundError(f"LiveKit executable not found: {LIVEKIT_EXE}")
    config_body = json.dumps({"room": {"departure_timeout": ROOM_DEPARTURE_TIMEOUT_SECONDS}})
    livekit_process = start_hidden(
        [str(LIVEKIT_EXE), "--dev", "--config-body", config_body],
        LIVEKIT_EXE.parent, "livekit.log",
    )
    owns_livekit = True
    wait_for_port(LIVEKIT_HOST, LIVEKIT_PORT, livekit_process, 30)
    log(
        "LiveKit ready. Room departure timeout="
        f"{ROOM_DEPARTURE_TIMEOUT_SECONDS}s (24 hours)."
    )

    if port_ready(API_HOST, API_PORT):
        log("FastAPI already ready; leaving existing server alone.")
    else:
        api_process = start_hidden(
            [str(VENV_PYTHON), "-m", "uvicorn", "web_server:app", "--host", API_HOST, "--port", str(API_PORT)],
            ROOT, "fastapi.log",
        )
        owns_api = True
        wait_for_port(API_HOST, API_PORT, api_process, 30)
        log("FastAPI ready.")


def read_agent_log():
    try:
        return (LOG_DIR / "agent.log").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def start_warm_agent():
    """Start agent once and wait until the Realtime session is connected."""
    global agent_process, owns_agent
    if not VENV_PYTHON.exists():
        raise FileNotFoundError(f"Virtual environment Python not found: {VENV_PYTHON}")
    close_log_handles("agent.log")
    agent_process = start_hidden(
        [str(VENV_PYTHON), "main.py", "connect", "--room", ROOM_NAME],
        ROOT, "agent.log", truncate=True,
    )
    owns_agent = True
    log("Warming up JARVIS agent before enabling wake-word listening...")
    deadline = time.monotonic() + AGENT_READY_TIMEOUT
    while time.monotonic() < deadline:
        if agent_process.poll() is not None:
            raise RuntimeError(f"Agent exited ({agent_process.returncode}); inspect {LOG_DIR / 'agent.log'}")
        content = read_agent_log()
        if "session.start completed; waiting for wake-triggered UI connection" in content:
            log("JARVIS agent is warm. Wake-word listener can start.")
            return
        if "failed to start agentsession" in content.lower() and "job exiting" in content.lower():
            raise RuntimeError(f"Agent startup failed; inspect {LOG_DIR / 'agent.log'}")
        time.sleep(0.15)
    raise TimeoutError(f"Agent did not become ready in {AGENT_READY_TIMEOUT:.0f}s; inspect {LOG_DIR / 'agent.log'}")


def ensure_agent_process():
    """Only restart when the actual agent process exited; never infer from old log text."""
    global agent_process
    if agent_process is None or agent_process.poll() is not None:
        log("Agent process has exited; restarting before opening UI.")
        if agent_process is not None:
            stop_process_tree(agent_process, "old JARVIS agent")
        time.sleep(0.4)
        start_warm_agent()


def open_ui_until_closed():
    if not APP_EXE.exists():
        raise FileNotFoundError(f"JARVIS UI not found: {APP_EXE}")
    ensure_agent_process()
    log("Wake detected. Opening JARVIS UI; wake listener is paused while UI is open.")
    app = subprocess.Popen([str(APP_EXE)], cwd=str(APP_EXE.parent))
    while app.poll() is None:
        # If agent process dies, recover it. This is uncommon; normal UI close keeps it warm.
        if agent_process is None or agent_process.poll() is not None:
            log("WARNING: agent process exited while UI was open. Restarting agent...")
            start_warm_agent()
        time.sleep(0.25)
    log("JARVIS UI closed. Agent stays warm; no UI microphone/speaker stream is connected.")


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for required in (ROOT, LIVEKIT_EXE, APP_EXE, VENV_PYTHON):
        if not required.exists():
            raise FileNotFoundError(f"Required path not found: {required}")
    start_background_services()
    start_warm_agent()
    # The listener opens the microphone only while waiting. It returns after a wake
    # detection, releasing the stream before the UI opens. UI close returns here.
    listener = WakeWordListener(log=log)
    while True:
        try:
            listener.wait_for_wake_word()
            open_ui_until_closed()
            listener.reset_after_ui_close()
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            log(f"Wake/UI cycle error: {exc}; retrying in 1 second.")
            time.sleep(1)
            listener.reset_after_ui_close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("JARVIS launcher stopped by user.")
    except Exception as exc:
        log(f"Fatal error: {exc}")
        raise
    finally:
        stop_process_tree(agent_process if owns_agent else None, "JARVIS agent")
        stop_process_tree(api_process if owns_api else None, "FastAPI")
        stop_process_tree(livekit_process if owns_livekit else None, "LiveKit server")
        for handle in LOG_HANDLES:
            try:
                handle.close()
            except Exception:
                pass
