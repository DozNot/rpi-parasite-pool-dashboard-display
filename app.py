#!/usr/bin/env python3
"""
RPi Parasite Pool Dashboard Display
Live TFT dashboard for Raspberry Pi displaying Parasite Pool Dashboard stats:
  • Personal Parasite Pool Stats (Using BTC ADDRESS)
  • Total Parasite Pool hashrate & best difficulty
  • Network hashrate, difficulty, fees, block height & pool
  • BTC price ticker (Binance primary + Kraken fallback)
Optimized for Raspberry Pi:
  - Low CPU usage
  - Smooth rendering with targeted FPS
  - Robust error handling
  - Automatic WebSocket reconnection with exponential backoff
  - Logging set to ERROR (change to INFO for more verbosity)
Developed and tested with:
  - Raspberry Pi 3B+, 4, 5
  - Waveshare 3.5" TFT touchscreen (480×320, XPT2046 controller)
  - HDMI monitors (auto-scaled with preserved aspect ratio)
"""
import os
os.environ['SDL_AUDIODRIVER'] = 'dummy'
os.environ["SDL_VIDEODRIVER"] = "kmsdrm"
os.environ["SDL_FBDEV"] = "/dev/fb0"
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import sys
import logging
from logging.handlers import RotatingFileHandler
import threading
import socket
import time
import signal
import pygame

def signal_handler(sig, frame):
    """Graceful shutdown."""
    logger.info("Shutdown signal received")
    pygame.quit()
    sys.exit(0)

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

from src.constants import CONFIG, PROJECT_ROOT, BTC_ADDRESS, LOGO_PATH
from src.data import state
from src.websockets import run_binance_websocket, run_kraken_websocket
from src.mempool import run_mempool_polling
from src.parasite import run_parasite_polling, run_recent_shares_worker
from src.rendering import init_pygame, run_render_loop

# LOGGING SETUP
log_dir = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "app.log")
log_handler = RotatingFileHandler(log_file, maxBytes=2*1024*1024, backupCount=5)
logging.basicConfig(
    level=logging.ERROR,
    format='%(asctime)s | %(levelname)-5s | %(threadName)s | %(message)s',
    handlers=[log_handler, logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def wait_for_internet(timeout: int = 90) -> bool:
    """Wait for internet connectivity at startup with a timeout."""
    logger.info("Waiting for internet connection at startup...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            logger.info("Internet connection established")
            return True
        except OSError:
            time.sleep(2)
    logger.error("No internet connection after %d seconds", timeout)
    return False

# WAITING FOR NETWORK AT STARTUP
wait_for_internet()

# START BACKGROUND THREADS
threading.Thread(target=run_binance_websocket, args=(state,), daemon=True, name="BinanceWS").start()
threading.Thread(target=run_kraken_websocket, args=(state,), daemon=True, name="KrakenWS").start()
threading.Thread(target=run_mempool_polling, args=(state,), daemon=True, name="MempoolPoller").start()
threading.Thread(target=run_parasite_polling, args=(state,), daemon=True, name="ParasitePoller").start()
threading.Thread(target=run_recent_shares_worker, args=(state,), daemon=True, name="SharesFetcher").start()

# MAIN
logger.info("Starting RPi Parasite Pool Dashboard Display...")
init_pygame(LOGO_PATH)
run_render_loop(state)
