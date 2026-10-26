#!/usr/bin/env python3
"""
RPi Parasite Pool Dashboard Display

Live TFT/HDMI dashboard for Raspberry Pi showing Parasite Pool stats:
  - Personal Parasite Pool stats (via BTC address)
  - Total pool hashrate and best difficulty
  - Network hashrate, difficulty, fees, block height and mining pool
  - BTC price ticker (Binance primary + Kraken fallback)

Optimized for Raspberry Pi:
  - Low CPU usage
  - Smooth rendering with configurable FPS
  - Robust error handling
  - Automatic WebSocket reconnection with exponential backoff
  - Logging defaults to ERROR (set to INFO for more verbosity)

Developed and tested with:
  - Raspberry Pi 3B+, 4, 5
  - Waveshare 3.5\" TFT touchscreen (480x320, XPT2046 controller)
  - HDMI monitors (auto-scaled with preserved aspect ratio)
"""

from __future__ import annotations

import logging
import os
import signal
import socket
import sys
import threading
import time
from logging.handlers import RotatingFileHandler

# Pygame environment must be set before importing pygame
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
os.environ["SDL_FBDEV"] = "/dev/fb0"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame

from src.constants import BTC_ADDRESS, CONFIG, LOGO_PATH, PROJECT_ROOT
from src.data import state
from src.mempool import run_mempool_polling
from src.parasite import run_parasite_polling, run_recent_shares_worker
from src.rendering import init_pygame, run_render_loop
from src.websockets import run_binance_websocket, run_kraken_websocket

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "app.log")

_log_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=2 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)

logging.basicConfig(
    level=logging.ERROR,
    format="%(asctime)s | %(levelname)-5s | %(threadName)s | %(message)s",
    handlers=[_log_handler, logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------

def _signal_handler(sig: int, frame) -> None:
    """Graceful shutdown on SIGTERM / SIGINT."""
    logger.info("Shutdown signal received (%s)", sig)
    if pygame.get_init():
        pygame.quit()
    sys.exit(0)


signal.signal(signal.SIGTERM, _signal_handler)
signal.signal(signal.SIGINT, _signal_handler)


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------

def wait_for_internet(timeout: int = 90) -> bool:
    """
    Block until internet connectivity is available or timeout is reached.

    Args:
        timeout: Maximum seconds to wait.

    Returns:
        True if connection was established, False on timeout.
    """
    logger.info("Waiting for internet connection at startup...")
    start = time.time()
    while time.time() - start < timeout:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            logger.info("Internet connection established")
            return True
        except OSError:
            time.sleep(2)
    logger.error("No internet connection after %d seconds", timeout)
    return False


def start_background_threads() -> None:
    """Launch all daemon worker threads."""
    threads = [
        threading.Thread(
            target=run_binance_websocket,
            args=(state,),
            daemon=True,
            name="BinanceWS",
        ),
        threading.Thread(
            target=run_kraken_websocket,
            args=(state,),
            daemon=True,
            name="KrakenWS",
        ),
        threading.Thread(
            target=run_mempool_polling,
            args=(state,),
            daemon=True,
            name="MempoolPoller",
        ),
        threading.Thread(
            target=run_parasite_polling,
            args=(state,),
            daemon=True,
            name="ParasitePoller",
        ),
        threading.Thread(
            target=run_recent_shares_worker,
            args=(state,),
            daemon=True,
            name="SharesFetcher",
        ),
    ]
    for t in threads:
        t.start()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    """Application entry point."""
    wait_for_internet()
    start_background_threads()

    logger.info("Starting RPi Parasite Pool Dashboard Display...")
    if not BTC_ADDRESS:
        logger.warning("No btc_address configured – personal stats will be unavailable")

    init_pygame(LOGO_PATH)
    run_render_loop(state)


if __name__ == "__main__":
    main()
