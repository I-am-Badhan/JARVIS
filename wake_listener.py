
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
import openwakeword
from openwakeword.model import Model

SAMPLE_RATE = 16000
FRAME_SIZE = 1280
THRESHOLD = 0.50
COOLDOWN = 3.0

model_path = (
    Path(openwakeword.__file__).parent
    / "resources"
    / "models"
    / "hey_jarvis_v0.1.onnx"
)

if not model_path.exists():
    raise FileNotFoundError(f"Wake-word model missing: {model_path}")

print("[WAKE] Loading model...")
model = Model(wakeword_model_paths=[str(model_path)])

print("[WAKE] Model loaded.")
print("[WAKE] Model keys:", list(model.models.keys()))
print("[WAKE] Listening. Say 'Hey Jarvis'.")

last_detection = 0.0
last_debug = 0.0

try:
    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="int16",
        blocksize=FRAME_SIZE,
    ) as stream:

        while True:
            audio, overflowed = stream.read(FRAME_SIZE)

            if overflowed:
                continue

            frame = np.asarray(audio).reshape(-1)
            predictions = model.predict(frame)

            # Display the highest score from the actual model output.
            key, score = max(
                predictions.items(),
                key=lambda item: float(item[1]),
            )
            score = float(score)

            now = time.monotonic()

            # Print a diagnostic score approximately once per second.
            if now - last_debug >= 1.0:
                print(f"[DEBUG] {key}: {score:.3f}")
                last_debug = now

            if score >= THRESHOLD and now - last_detection >= COOLDOWN:
                last_detection = now
                print(f"[WAKE] Detected! {key}: {score:.3f}")

except KeyboardInterrupt:
    print("\n[WAKE] Listener stopped.")
