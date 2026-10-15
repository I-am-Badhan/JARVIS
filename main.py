import logging
import time

from livekit import agents
from server import server

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("jarvis.main")


if __name__ == "__main__":
    started = time.perf_counter()
    logger.info("Starting JARVIS LiveKit agent...")

    try:
        agents.cli.run_app(server)
    except KeyboardInterrupt:
        logger.info("JARVIS stopped by user.")
    except Exception:
        logger.exception("JARVIS startup failed.")
        raise
    finally:
        logger.info(
            "JARVIS process exiting after %.2f seconds",
            time.perf_counter() - started,
        )
