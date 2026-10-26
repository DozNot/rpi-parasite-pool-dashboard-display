"""
Global constants and configuration loading.

All runtime configurables are loaded from config.json (with safe defaults).
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

# ---------------------------------------------------------------------------
# Default configuration
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "btc_address": "",
    "logo_path": "logos/parasite-white.png",
    "fps": 12,
    "dim_alpha": 50,
    "data_timeout_sec": 300,
    "stale_warn_sec": 60,
    "mempool_poll_interval": 25,
    "parasite_poll_interval": 4,
    "wifi_check_interval": 12,
    "historical_interval": "5m",
    "total_work_cache_min": 140,
    "total_work_cache_max": 300,
    "parasite_api_base": "https://parasite.space/api",
}

# ---------------------------------------------------------------------------
# Load configuration
# ---------------------------------------------------------------------------

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        CONFIG: Dict[str, Any] = json.load(f)
    logger.info("Config loaded successfully from %s", CONFIG_PATH)
except FileNotFoundError:
    logger.warning("Config file not found. Using default configuration.")
    CONFIG = DEFAULT_CONFIG.copy()
except json.JSONDecodeError as exc:
    logger.warning("Invalid JSON in config file: %s. Using default configuration.", exc)
    CONFIG = DEFAULT_CONFIG.copy()

# ---------------------------------------------------------------------------
# Extracted constants (with safe .get fallbacks)
# ---------------------------------------------------------------------------

BTC_ADDRESS: str = CONFIG.get("btc_address", DEFAULT_CONFIG["btc_address"])
LOGO_PATH: str = os.path.join(
    PROJECT_ROOT, CONFIG.get("logo_path", DEFAULT_CONFIG["logo_path"])
)

# Display
SCREEN_W: int = 480
SCREEN_H: int = 320
FPS: int = int(CONFIG.get("fps", DEFAULT_CONFIG["fps"]))
DIM_ALPHA: int = int(CONFIG.get("dim_alpha", DEFAULT_CONFIG["dim_alpha"]))

# Colors (RGB)
COLOR_BLACK = (0, 0, 0)
COLOR_GRID = (40, 40, 55)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (0, 230, 140)
COLOR_RED = (255, 90, 90)
COLOR_GRAY = (130, 130, 160)
COLOR_ORANGE = (255, 180, 0)
COLOR_DARK_GREEN = (0, 2, 8)

# Chart layout
CHART_X: int = 6
CHART_Y: int = 162
CHART_W: int = 460
CHART_H: int = 125

# Marquee
MARQUEE_H: int = 24
MARQUEE_Y: int = SCREEN_H - MARQUEE_H

# Timeouts / intervals (seconds)
DATA_TIMEOUT_SEC: float = float(
    CONFIG.get("data_timeout_sec", DEFAULT_CONFIG["data_timeout_sec"])
)
STALE_WARN_SEC: float = float(
    CONFIG.get("stale_warn_sec", DEFAULT_CONFIG["stale_warn_sec"])
)
MEMPOOL_POLL_INTERVAL: float = float(
    CONFIG.get("mempool_poll_interval", DEFAULT_CONFIG["mempool_poll_interval"])
)
PARASITE_POLL_INTERVAL: float = float(
    CONFIG.get("parasite_poll_interval", DEFAULT_CONFIG["parasite_poll_interval"])
)
WIFI_CHECK_INTERVAL: float = float(
    CONFIG.get("wifi_check_interval", DEFAULT_CONFIG["wifi_check_interval"])
)

# Historical hashrate interval (Parasite API: 5m / 15m / 30m / 1h)
HISTORICAL_INTERVAL: str = str(
    CONFIG.get("historical_interval", DEFAULT_CONFIG["historical_interval"])
)

# Total-work cache randomization window (seconds)
TOTAL_WORK_CACHE_MIN: float = float(
    CONFIG.get("total_work_cache_min", DEFAULT_CONFIG["total_work_cache_min"])
)
TOTAL_WORK_CACHE_MAX: float = float(
    CONFIG.get("total_work_cache_max", DEFAULT_CONFIG["total_work_cache_max"])
)

# API
PARASITE_API_BASE: str = str(
    CONFIG.get("parasite_api_base", DEFAULT_CONFIG["parasite_api_base"])
)
