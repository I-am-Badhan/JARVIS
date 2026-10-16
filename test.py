
import time
from pathlib import Path

import numpy as np
import sounddevice as sd
from openwakeword.model import Model

SAMPLE_RATE = 16000
FRAME_SIZE = 1280
THRESHOLD = 0.50
CONFIRM_FRAMES = 2

MODEL_PATH = (
    Path(r"D:\JARVIS\.venv\Lib\site-packages")
    / "openwakeword"
    / "resources"
    / "models"
    / "hey_jarvis_v0.1.onnx"
)


def main():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Wake-word model not found: {MODEL_PATH}"
        )

    print("Loading Hey JARVIS model...")
    model = Model(
        wakeword_model_paths=[str(MODEL_PATH)],
        enable_speex_noise_suppression=False,
    )
    print("Model loaded.\n")

    trials = 5
    trial_seconds = 3.0
    rest_seconds = 2.0

    results = []

    print("=" * 55)
    print("       HEY JARVIS PER-TRIAL ACCURACY TEST")
    print("=" * 55)
    print("Keep your mouth silent during the initial 5 seconds.")
    print("For each trial, say 'Hey JARVIS' ONCE after SAY NOW.")
    print("Speak naturally at your usual microphone distance.")
    print("Wait for the next trial before speaking again.")
    print("Ctrl+C stops the test.")
    print("=" * 55)

    try:
        with sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
            blocksize=FRAME_SIZE,
        ) as stream:

            print("\nMicrophone ready. Stay silent for 5 seconds.")
            silence_end = time.monotonic() + 5.0

            while time.monotonic() < silence_end:
                audio, overflowed = stream.read(FRAME_SIZE)
                if overflowed:
                    continue
                model.predict(np.asarray(audio).reshape(-1))

            for trial in range(1, trials + 1):
                print(f"\nTRIAL {trial}/{trials}: Get ready...")
                time.sleep(1.0)

                # Reset temporal state so previous trials
                # do not contribute to the next trial.
                model.reset()

                print("SAY NOW: Hey JARVIS")
                start = time.monotonic()
                deadline = start + trial_seconds

                peak = 0.0
                above_count = 0
                consecutive = 0
                longest_consecutive = 0

                while time.monotonic() < deadline:
                    audio, overflowed = stream.read(FRAME_SIZE)
                    if overflowed:
                        continue

                    scores = model.predict(
                        np.asarray(audio).reshape(-1)
                    )
                    score = float(
                        scores.get("hey_jarvis_v0.1", 0.0)
                    )

                    peak = max(peak, score)

                    if score >= THRESHOLD:
                        above_count += 1
                        consecutive += 1
                        longest_consecutive = max(
                            longest_consecutive, consecutive
                        )
                    else:
                        consecutive = 0

                detected = longest_consecutive >= CONFIRM_FRAMES

                result = {
                    "trial": trial,
                    "peak": peak,
                    "above": above_count,
                    "longest": longest_consecutive,
                    "detected": detected,
                }
                results.append(result)

                status = "PASS" if detected else "MISS"
                print(
                    f"Result: {status} | "
                    f"Peak={peak:.3f} | "
                    f"Frames >= {THRESHOLD:.2f}: {above_count} | "
                    f"Longest consecutive: {longest_consecutive}"
                )

                if trial < trials:
                    print(f"Rest for {rest_seconds:.0f} seconds...")
                    rest_end = time.monotonic() + rest_seconds
                    while time.monotonic() < rest_end:
                        audio, overflowed = stream.read(FRAME_SIZE)
                        if not overflowed:
                            model.predict(
                                np.asarray(audio).reshape(-1)
                            )

    except KeyboardInterrupt:
        print("\nTest interrupted.")

    finally:
        if results:
            passed = sum(r["detected"] for r in results)
            print("\n" + "=" * 55)
            print(f"RESULT: {passed}/{len(results)} trials passed")
            for r in results:
                print(
                    f"Trial {r['trial']}: "
                    f"peak={r['peak']:.3f}, "
                    f"consecutive={r['longest']}, "
                    f"{'PASS' if r['detected'] else 'MISS'}"
                )
            print("=" * 55)

        print("Microphone test finished.")


if __name__ == "__main__":
    main()
