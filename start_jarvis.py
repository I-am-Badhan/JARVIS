import socket
import subprocess
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import openwakeword
from openwakeword.model import Model

# ============================================================
# CONFIGURATION
# ============================================================
ROOT = Path(r"D:\JARVIS")
LIVEKIT_EXE = Path(r"D:\livekit\livekit-server.exe")
APP_EXE = ROOT / "src-tauri" / "target" / "release" / "app.exe"
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
LIVEKIT_HOST, LIVEKIT_PORT = "127.0.0.1", 7880
API_HOST, API_PORT = "127.0.0.1", 8080
ROOM_NAME = "jarvis-room"
SAMPLE_RATE = 16000
FRAME_SIZE = 1280  # 80 ms
WAKE_THRESHOLD = 0.50
WAKE_CONFIRM_FRAMES = 2
POST_SESSION_DISCARD_SECONDS = 1.0
REARM_THRESHOLD = 0.10
REARM_QUIET_SECONDS = 1.0
WAKE_COOLDOWN = 3.0
AGENT_READY_TIMEOUT = 45.0
MODEL_PATH = Path(openwakeword.__file__).parent / "resources" / "models" / "hey_jarvis_v0.1.onnx"
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
    mode = "w" if truncate else "a"
    handle = open(LOG_DIR / log_name, mode, encoding="utf-8", buffering=1)
    LOG_HANDLES.append(handle)
    log(f"Starting background process: {log_name}")
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


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
            raise RuntimeError(f"Process exited ({process.returncode}) before {host}:{port} became ready.")
        time.sleep(0.15)
    raise TimeoutError(f"Timed out waiting for {host}:{port}")


def stop_process_tree(process, name):
    if process is None or process.poll() is not None:
        return
    log(f"Stopping {name}...")
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True, text=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            log(f"Could not taskkill {name}: {(result.stderr or result.stdout).strip()}")
    except (OSError, subprocess.TimeoutExpired) as exc:
        log(f"Could not stop {name}: {exc}")
        try:
            process.terminate()
        except OSError:
            pass
    try:
        process.wait(timeout=2)
    except (subprocess.TimeoutExpired, OSError):
        try:
            process.kill()
        except OSError:
            pass


def start_background_services():
    """Start LiveKit/API and keep them running while the wake listener waits."""
    global livekit_process, api_process, owns_livekit, owns_api
    if port_ready(LIVEKIT_HOST, LIVEKIT_PORT):
        log("LiveKit already ready; leaving existing server alone.")
    else:
        if not LIVEKIT_EXE.exists():
            raise FileNotFoundError(f"LiveKit executable not found: {LIVEKIT_EXE}")
        livekit_process = start_hidden([str(LIVEKIT_EXE), "--dev"], LIVEKIT_EXE.parent, "livekit.log")
        owns_livekit = True
        wait_for_port(LIVEKIT_HOST, LIVEKIT_PORT, livekit_process, timeout=30)
        log("LiveKit ready.")

    if port_ready(API_HOST, API_PORT):
        log("FastAPI already ready; leaving existing server alone.")
    else:
        if not VENV_PYTHON.exists():
            raise FileNotFoundError(f"Virtual environment Python not found: {VENV_PYTHON}")
        api_process = start_hidden(
            [str(VENV_PYTHON), "-m", "uvicorn", "web_server:app", "--host", API_HOST, "--port", str(API_PORT)],
            ROOT, "fastapi.log",
        )
        owns_api = True
        wait_for_port(API_HOST, API_PORT, api_process, timeout=30)
        log("FastAPI ready.")


def start_warm_agent():
    """Start the LiveKit/Gemini agent before listening for the wake word."""
    global agent_process, owns_agent
    if not VENV_PYTHON.exists():
        raise FileNotFoundError(f"Virtual environment Python not found: {VENV_PYTHON}")
    agent_log = LOG_DIR / "agent.log"
    agent_process = start_hidden(
        [str(VENV_PYTHON), "main.py", "connect", "--room", ROOM_NAME],
        ROOT, "agent.log", truncate=True,
    )
    owns_agent = True
    log("Waiting for the agent's Realtime session to become ready...")
    deadline = time.monotonic() + AGENT_READY_TIMEOUT
    while time.monotonic() < deadline:
        if agent_process.poll() is not None:
            raise RuntimeError(f"JARVIS agent exited early ({agent_process.returncode}); inspect {agent_log}")
        try:
            content = agent_log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            content = ""
        if "session.start completed; waiting for wake-triggered UI connection" in content:
            log("JARVIS agent and Realtime session are warm. Starting wake listener.")
            return
        # Also report the existing marker while using an older server.py, which may
        # still use the original startup text. That version won't defer its greeting.
        if "[STARTUP] session.start completed" in content and "waiting for wake-triggered UI connection" not in content:
            log("Agent session started, but server.py is not the prewarmed version. Replace server.py too.")
            raise RuntimeError("The current server.py sends greeting immediately; install server_prewarmed.py as server.py first.")
        time.sleep(0.15)
    raise TimeoutError(f"Agent session did not become ready in {AGENT_READY_TIMEOUT:.0f}s; inspect {agent_log}")


def restart_warm_agent():
    """Create a fresh LiveKit/Gemini session after the UI closes."""
    global agent_process, owns_agent

    log("Refreshing JARVIS agent after UI closed...")

    # Stop the previous worker and its child processes.
    if agent_process is not None:
        stop_process_tree(agent_process, "old JARVIS agent")

    agent_process = None
    time.sleep(1.5)

    # Start a fresh worker and wait for Gemini Realtime readiness.
    start_warm_agent()


def open_ui_until_closed():
    if not APP_EXE.exists():
        raise FileNotFoundError(f"JARVIS UI not found: {APP_EXE}")
    log("Wake detected. Opening JARVIS UI; agent and Gemini session are already warm.")
    app = subprocess.Popen([str(APP_EXE)], cwd=str(APP_EXE.parent))
    while app.poll() is None:
        if agent_process is not None and agent_process.poll() is not None:
            log(f"WARNING: warm agent exited with code {agent_process.returncode}; see logs\\agent.log")
            break
        time.sleep(0.2)
    log("JARVIS UI closed; agent will be refreshed before the next wake.")


def reset_wake_model():
    log("Loading/resetting wake-word model...")
    return Model(wakeword_model_paths=[str(MODEL_PATH)])


def get_wake_score(model, frame):
    predictions = model.predict(frame)
    if not predictions:
        return 0.0, "unknown"
    key, value = max(predictions.items(), key=lambda item: float(item[1]))
    return float(value), key


def wait_until_rearmed(stream, model):
    discard_frames = int(POST_SESSION_DISCARD_SECONDS * SAMPLE_RATE / FRAME_SIZE)
    log(f"Discarding old audio for {POST_SESSION_DISCARD_SECONDS:.1f}s...")
    for _ in range(discard_frames):
        stream.read(FRAME_SIZE)
    log("Waiting for detector to become quiet...")
    needed = max(1, int(REARM_QUIET_SECONDS * SAMPLE_RATE / FRAME_SIZE))
    quiet = 0
    while quiet < needed:
        audio, overflowed = stream.read(FRAME_SIZE)
        if overflowed:
            quiet = 0
            continue
        score, _ = get_wake_score(model, np.asarray(audio).reshape(-1))
        quiet = quiet + 1 if score < REARM_THRESHOLD else 0
    log("Wake detector rearmed; listening for a new 'Hey JARVIS'.")


def listen_for_wake_word():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Wake-word model not found: {MODEL_PATH}")
    model = reset_wake_model()
    log(f"Wake model ready. Threshold={WAKE_THRESHOLD:.2f}; confirmation={WAKE_CONFIRM_FRAMES} frames.")
    log("Listening. Say 'Hey JARVIS'.")
    last_detection = 0.0
    while True:
        detected = False
        high_frames = 0
        high_key = "unknown"
        high_score = 0.0
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME_SIZE) as stream:
            if last_detection:
                wait_until_rearmed(stream, model)
            while True:
                audio, overflowed = stream.read(FRAME_SIZE)
                if overflowed:
                    high_frames = 0
                    continue
                score, key = get_wake_score(model, np.asarray(audio).reshape(-1))
                if score >= WAKE_THRESHOLD:
                    high_frames += 1
                    high_key, high_score = key, score
                else:
                    high_frames = 0
                now = time.monotonic()
                if high_frames >= WAKE_CONFIRM_FRAMES and now - last_detection >= WAKE_COOLDOWN:
                    last_detection = now
                    log(f"Wake detected: {high_key}, score={high_score:.3f}")
                    detected = True
                    break

        if detected:
            open_ui_until_closed()
            restart_warm_agent()
            model = reset_wake_model()
            log("Ready for the next wake word.")


def main():
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for required in (ROOT, LIVEKIT_EXE, APP_EXE, VENV_PYTHON):
        if not required.exists():
            raise FileNotFoundError(f"Required path not found: {required}")
    start_background_services()
    start_warm_agent()
    listen_for_wake_word()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Wake listener stopped by user.")
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
