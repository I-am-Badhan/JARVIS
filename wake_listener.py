import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import openwakeword
from openwakeword.model import Model

SAMPLE_RATE = 16000
FRAME_SIZE = 1280  # 80 ms
THRESHOLD = 0.3
CONFIRM_FRAMES = 2
COOLDOWN = 3.0
DEBUG_INTERVAL = 5.0
DISCARD_SECONDS = 0.7
QUIET_THRESHOLD = 0.10
QUIET_SECONDS = 0.5
REARM_TIMEOUT = 3.0
MODEL_PATH = Path(openwakeword.__file__).parent / "resources" / "models" / "hey_jarvis_v0.1.onnx"


class WakeWordListener:
    def __init__(self, log=print):
        if not MODEL_PATH.exists():
            raise FileNotFoundError(f"Wake-word model not found: {MODEL_PATH}")
        self.log = log
        self.model = None
        self.last_detection = 0.0
        self.needs_rearm = False
        self._load_model()

    def _load_model(self):
        self.log("Loading wake-word model...")
        self.model = Model(wakeword_model_paths=[str(MODEL_PATH)])
        self.log(f"Wake model ready. Threshold={THRESHOLD:.2f}; confirmation={CONFIRM_FRAMES} frames.")

    def _score(self, audio):
        predictions = self.model.predict(np.asarray(audio).reshape(-1))
        if not predictions:
            return 0.0, "unknown"
        key, value = max(predictions.items(), key=lambda pair: float(pair[1]))
        return float(value), key

    def _rearm(self, stream):
        self.log(f"Discarding residual audio for {DISCARD_SECONDS:.1f}s...")
        for _ in range(max(1, int(DISCARD_SECONDS * SAMPLE_RATE / FRAME_SIZE))):
            stream.read(FRAME_SIZE)
        self.log("Waiting briefly for detector to become quiet...")
        required = max(1, int(QUIET_SECONDS * SAMPLE_RATE / FRAME_SIZE))
        quiet = 0
        deadline = time.monotonic() + REARM_TIMEOUT
        while quiet < required and time.monotonic() < deadline:
            audio, overflowed = stream.read(FRAME_SIZE)
            if overflowed:
                quiet = 0
                continue
            score, _ = self._score(audio)
            quiet = quiet + 1 if score < QUIET_THRESHOLD else 0
        if quiet < required:
            self.log("Wake detector re-arm timed out; resetting model state.")
            self.model.reset()
        self.needs_rearm = False
        self.log("Listening for 'Hey JARVIS'.")

    def wait_for_wake_word(self):
        """Wait for one wake word, then close microphone stream before returning."""
        if self.model is None:
            self._load_model()
        self.log("Wake listener active. Say 'Hey JARVIS'.")
        high_frames = 0
        peak = 0.0
        peak_key = "unknown"
        next_debug = time.monotonic() + DEBUG_INTERVAL
        with sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=FRAME_SIZE
        ) as stream:
            if self.needs_rearm:
                self._rearm(stream)
            while True:
                audio, overflowed = stream.read(FRAME_SIZE)
                if overflowed:
                    high_frames = 0
                    continue
                score, key = self._score(audio)
                if score > peak:
                    peak, peak_key = score, key
                if score >= THRESHOLD:
                    high_frames += 1
                else:
                    high_frames = 0
                now = time.monotonic()
                if now >= next_debug:
                    self.log(f"Wake score peak={peak:.3f} ({peak_key}); threshold={THRESHOLD:.2f}.")
                    peak, peak_key = score, key
                    next_debug = now + DEBUG_INTERVAL
                if high_frames >= CONFIRM_FRAMES and now - self.last_detection >= COOLDOWN:
                    self.last_detection = now
                    self.needs_rearm = True
                    self.log(f"Wake detected: {key}, score={score:.3f}. Releasing microphone for UI...")
                    return

    def reset_after_ui_close(self):
        """Reset detector state; microphone reopens only for the next wake wait."""
        self.needs_rearm = True
        try:
            self.model.reset()
        except Exception:
            self._load_model()
        self.log("UI closed. Wake-word listening will resume; detector microphone is the only active input.")
