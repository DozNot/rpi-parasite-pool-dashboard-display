"""
Utility helpers: formatting, connectivity checks and Parasite API helpers.

Pure formatting functions are side-effect free.
Network helpers use a shared requests.Session with retries.
"""

from __future__ import annotations

import logging
import random
import re
import socket
import time
from datetime import datetime
from typing import List, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.constants import (
    BTC_ADDRESS,
    COLOR_GREEN,
    COLOR_ORANGE,
    COLOR_RED,
    HISTORICAL_INTERVAL,
    PARASITE_API_BASE,
    TOTAL_WORK_CACHE_MAX,
    TOTAL_WORK_CACHE_MIN,
    WIFI_CHECK_INTERVAL,
)
from src.data import state

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared HTTP session with retries
# ---------------------------------------------------------------------------

session = requests.Session()
_retry = Retry(
    total=6,
    backoff_factor=0.6,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
)
_adapter = HTTPAdapter(max_retries=_retry)
session.mount("http://", _adapter)
session.mount("https://", _adapter)
session.headers.update(
    {"User-Agent": "rpi-parasite-pool-dashboard-display/1.0"}
)


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------

def is_wifi_connected() -> bool:
    """Quick non-blocking internet reachability check via DNS."""
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2.5)
        return True
    except OSError:
        return False


def get_ws_status_color() -> Tuple[int, int, int]:
    """
    Return the RGB color for the global connection indicator.

    - RED    : no Wi-Fi / internet
    - GREEN  : at least one price WebSocket is live
    - ORANGE : internet OK but no live WebSocket
    """
    now = time.time()
    if now - state.last_wifi_check > WIFI_CHECK_INTERVAL:
        state.wifi_ok = is_wifi_connected()
        state.last_wifi_check = now

    if not state.wifi_ok:
        return COLOR_RED
    if state.binance_ws_status == "Live" or state.kraken_ws_status == "Live":
        return COLOR_GREEN
    return COLOR_ORANGE


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_hashrate(th: float) -> str:
    """Format hashrate in TH/s with two decimal places."""
    return f"{th:.2f} TH/s"


def format_difficulty(diff: float) -> str:
    """Human-readable difficulty with K/M/G/T suffix."""
    if diff <= 0:
        return "0"
    for unit, divisor in (("T", 1e12), ("G", 1e9), ("M", 1e6), ("K", 1e3)):
        if diff >= divisor:
            return f"{diff / divisor:.2f} {unit}"
    return f"{int(diff)}"


def format_pool_best_diff(diff_str: str) -> str:
    """Normalize pool best-difficulty string (e.g. '1.23T' -> '1.23 T')."""
    if not diff_str or diff_str in {"?", "??"}:
        return diff_str
    match = re.match(
        r"^([\d.]+)\s*([KMGTPEZY])$", diff_str.strip(), re.IGNORECASE
    )
    if match:
        num, unit = match.groups()
        return f"{num} {unit.upper()}"
    return diff_str


def format_network_hashrate(hr_eh: float) -> str:
    """Format network hashrate starting from EH/s with dynamic scaling."""
    for unit, divisor, prec in (
        ("YH/s", 1e6, 2),
        ("ZH/s", 1e3, 2),
        ("EH/s", 1, 2),
        ("PH/s", 1e-3, 2),
    ):
        if hr_eh >= divisor:
            return f"{hr_eh / divisor:.{prec}f} {unit}"
    return f"{hr_eh * 1e6:.2f} TH/s"


def parse_difficulty(diff_str: str) -> float:
    """Parse a difficulty string (e.g. '12.3M', '1.5T') into a float."""
    if not diff_str or diff_str in {"?", "??"}:
        return 0.0
    try:
        match = re.match(r"([\d.]+)\s*([KkMmGgTt]?)", diff_str.strip())
        if not match:
            return 0.0
        num = float(match.group(1))
        unit = match.group(2).upper()
        multipliers = {"": 1, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}
        return num * multipliers.get(unit, 1)
    except (ValueError, TypeError):
        return 0.0


def format_large_work(value: float | int) -> str:
    """Format large work / total difficulty values with SI-like suffixes."""
    if value <= 0:
        return "0 B"
    units = [
        (1e24, "Y"),
        (1e21, "Z"),
        (1e18, "E"),
        (1e15, "P"),
        (1e12, "T"),
        (1e9, "B"),
        (1e6, "M"),
    ]
    for threshold, unit in units:
        if value >= threshold:
            return f"{value / threshold:.2f}{unit}"
    return f"{value / 1e9:.2f}B"


# ---------------------------------------------------------------------------
# Parasite API helpers
# ---------------------------------------------------------------------------

def get_cached_total_work() -> str:
    """
    Return cached total work, refreshing from the API when the TTL expires.

    Uses a randomized refresh window to avoid synchronized requests.
    """
    now = time.time()
    if now - state.total_work_last_fetch <= state.total_work_next_fetch_in:
        with state.parasite_lock:
            return state.total_work_cache

    try:
        url = f"{PARASITE_API_BASE}/account/{BTC_ADDRESS}"
        response = session.get(url, timeout=8)
        response.raise_for_status()
        data = response.json()
        total_diff = int(data.get("account", {}).get("total_diff", 0))
        formatted = format_large_work(total_diff)

        with state.parasite_lock:
            state.total_work_cache = formatted
            state.total_work_last_fetch = now
            state.total_work_next_fetch_in = random.uniform(
                TOTAL_WORK_CACHE_MIN, TOTAL_WORK_CACHE_MAX
            )

        logger.info("Total Work updated: %s (raw: %s)", formatted, f"{total_diff:,}")
        return formatted

    except Exception as exc:
        logger.warning("Failed to fetch total_diff: %s", exp)
        with state.parasite_lock:
            return state.total_work_cache


def fetch_user_rank() -> str:
    """Fetch the user's combined leaderboard rank (or '?' on failure)."""
    try:
        response = session.get(
            f"{PARASITE_API_BASE}/leaderboard",
            params={"type": "combined", "limit": 9},
            timeout=8,
        )
        response.raise_for_status()
        data = response.json()
        addr_short = BTC_ADDRESS[:4] + "..." + BTC_ADDRESS[-4:]
        for index, entry in enumerate(data):
            if entry.get("address", "").lower() == addr_short.lower():
                return str(index + 1)
        return "?"
    except Exception as exc:
        logger.error("fetch_user_rank failed: %s", exp)
        return "?"


def fetch_recent_shares() -> List[Tuple[float, float]]:
    """
    Fetch recent high-difficulty shares for the configured address.

    Returns:
        List of (unix_timestamp, difficulty) sorted newest first.
    """
    try:
        params = {
            "address": BTC_ADDRESS,
            "type": "user-diffs",
            "limit": 9,
        }
        response = session.get(
            f"{PARASITE_API_BASE}/highest-diff", params=params, timeout=5
        )
        response.raise_for_status()
        data = response.json()

        shares: List[Tuple[float, float]] = []
        for item in data:
            diff = parse_difficulty(str(item.get("difficulty", "0")))
            ts = float(item.get("block_timestamp", 0))
            if ts > 0 and diff > 0:
                shares.append((ts, diff))

        shares.sort(key=lambda x: x[0], reverse=True)
        return shares
    except Exception as exp:
        logger.error("fetch_recent_shares failed: %s", exp)
        return []


def fetch_historical_hashrate() -> List[Tuple[float, float]]:
    """
    Fetch historical hashrate points for the configured address.

    Returns:
        List of (unix_timestamp, hashrate_th) sorted oldest first.
    """
    try:
        url = (
            f"{PARASITE_API_BASE}/user/{BTC_ADDRESS}/historical"
            f"?period=1d&interval={HISTORICAL_INTERVAL}"
        )
        response = session.get(url, timeout=12)
        response.raise_for_status()
        data = response.json()

        points: List[Tuple[float, float]] = []
        for entry in data:
            ts_str = entry.get("timestamp")
            hr_raw = entry.get("hashrate", 0)
            if ts_str and isinstance(hr_raw, (int, float)):
                dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                ts_unix = dt.timestamp()
                hr_th = hr_raw / 1e12
                points.append((ts_unix, hr_th))

        points.sort(key=lambda x: x[0])
        return points
    except Exception as exp:
        logger.error("fetch_historical_hashrate failed: %s", exp)
        return []
