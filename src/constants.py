# src/constants.py
"""
Global constants + configuration loading
All runtime configurables are loaded from config.json.
"""
import json
import os
import logging
from typing import Dict, Any

# Initialize logger for this module
logger = logging.getLogger(__name__)

# Determine the project root directory
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'config.json')

# Define default configuration values
DEFAULT_CONFIG = {
    "btc_address": "",
    "logo_path": "logos/parasite-white.png",
    "fps": 12,
    "dim_alpha": 50,
    "data_timeout_sec": 300,
    "stale_warn_sec": 60,
    "mempool_poll_interval": 25,
    "parasite_poll_interval": 4,
    "wifi_check_interval": 12,
    "total_work_cache_min": 140,
    "total_work_cache_max": 300,
    "parasite_api_base": "https://parasite.space/api"
}

# Load configuration from the JSON file, falling back to defaults if there are issues
try:
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        CONFIG: Dict[str, Any] = json.load(f)
    logger.info("Config loaded successfully")
except FileNotFoundError as e:
    logger.warning(f"Config file not found: {e}. Using default configuration.")
    CONFIG = DEFAULT_CONFIG
except json.JSONDecodeError as e:
    logger.warning(f"Invalid JSON in config file: {e}. Using default configuration.")
    CONFIG = DEFAULT_CONFIG

# Extract constants from the loaded configuration
BTC_ADDRESS = CONFIG['btc_address']
LOGO_PATH = os.path.join(PROJECT_ROOT, CONFIG['logo_path'])

# Screen dimensions and FPS
SCREEN_W = 480
SCREEN_H = 320
FPS = CONFIG.get('fps', 12)
DIM_ALPHA = CONFIG.get('dim_alpha', 50)

# Colors
COLOR_BLACK = (0, 0, 0)
COLOR_GRID = (40, 40, 55)
COLOR_WHITE = (255, 255, 255)
COLOR_GREEN = (0, 230, 140)
COLOR_RED = (255, 90, 90)
COLOR_GRAY = (130, 130, 160)
COLOR_ORANGE = (255, 180, 0)
COLOR_DARK_GREEN = (0, 2, 8)

# Chart positions
CHART_X = 6
CHART_Y = 162
CHART_W = 460
CHART_H = 125

# Marquee settings
MARQUEE_H = 24
MARQUEE_Y = SCREEN_H - MARQUEE_H

# Timeouts and intervals
DATA_TIMEOUT_SEC = CONFIG.get('data_timeout_sec', 300)
STALE_WARN_SEC = CONFIG.get('stale_warn_sec', 60)
MEMPOOL_POLL_INTERVAL = CONFIG.get('mempool_poll_interval', 25)
PARASITE_POLL_INTERVAL = CONFIG.get('parasite_poll_interval', 4)
WIFI_CHECK_INTERVAL = CONFIG.get('wifi_check_interval', 12)

# configurable historical API interval (5m / 15m / 30m / 1h)
HISTORICAL_INTERVAL = CONFIG.get('historical_interval', '5m')

# Cache settings
TOTAL_WORK_CACHE_MIN = CONFIG.get('total_work_cache_min', 140)
TOTAL_WORK_CACHE_MAX = CONFIG.get('total_work_cache_max', 300)

# API base
PARASITE_API_BASE = CONFIG.get('parasite_api_base', "https://parasite.space/api")
