# src/helpers.py
"""
Helper functions for formatting data and utilities.
"""
import re
import socket
import time
import random
import logging
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Tuple, List
from datetime import datetime
from src.constants import BTC_ADDRESS, PARASITE_API_BASE, TOTAL_WORK_CACHE_MIN, TOTAL_WORK_CACHE_MAX, WIFI_CHECK_INTERVAL, COLOR_GREEN, COLOR_RED, COLOR_ORANGE, HISTORICAL_INTERVAL
from src.data import state

# HTTP Session with retries
session = requests.Session()
retry_strategy = Retry(
    total=6,
    backoff_factor=0.6,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"]
)
adapter = HTTPAdapter(max_retries=retry_strategy)
session.mount("http://", adapter)
session.mount("https://", adapter)
session.headers.update({"User-Agent": "rpi-parasite-pool-dashboard-display/1.0"})

logger = logging.getLogger(__name__)

def is_wifi_connected() -> bool:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=2.5)
        return True
    except OSError:
        return False

def get_ws_status_color() -> Tuple[int, int, int]:
    now = time.time()
    if now - state.last_wifi_check > WIFI_CHECK_INTERVAL:
        state.wifi_ok = is_wifi_connected()
        state.last_wifi_check = now

    if not state.wifi_ok:
        return COLOR_RED
    if state.binance_ws_status == "Live" or state.kraken_ws_status == "Live":
        return COLOR_GREEN
    return COLOR_ORANGE

def format_hashrate(th: float) -> str:
    return f"{th:.2f} TH/s"

def format_difficulty(diff: float) -> str:
    if diff <= 0:
        return "0"
    for unit, div in [("T", 1e12), ("G", 1e9), ("M", 1e6), ("K", 1e3)]:
        if diff >= div:
            return f"{diff / div:.2f} {unit}"
    return f"{int(diff)}"

def format_pool_best_diff(diff_str: str) -> str:
    if not diff_str or diff_str in {"?", "??"}:
        return diff_str
    match = re.match(r"^([\d.]+)\s*([KMGTPEZY])$", diff_str.strip(), re.IGNORECASE)
    if match:
        num, unit = match.groups()
        return f"{num} {unit.upper()}"
    return diff_str

def format_network_hashrate(hr: float) -> str:
    for unit, div, prec in [
        ("YH/s", 1e6, 2), ("ZH/s", 1e3, 2),
        ("EH/s", 1,   2), ("PH/s", 1e-3, 2),
    ]:
        if hr >= div:
            return f"{hr / div:.{prec}f} {unit}"
    return f"{hr * 1e6:.2f} TH/s"

def parse_difficulty(diff_str: str) -> float:
    if not diff_str or diff_str in {"?", "??"}:
        return 0.0
    try:
        match = re.match(r"([\d.]+)\s*([KkMmGgTt]?)", diff_str.strip())
        if not match:
            return 0.0
        num = float(match.group(1))
        unit = match.group(2).upper()
        mult = {"": 1, "K": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}
        return num * mult.get(unit, 1)
    except Exception:
        return 0.0

def format_large_work(value: float | int) -> str:
    if value <= 0:
        return "0 B"

    units = [
        (1e24, "Y"), (1e21, "Z"), (1e18, "E"), (1e15, "P"),
        (1e12, "T"), (1e9,  "B"), (1e6,  "M"),
    ]
    for threshold, unit in units:
        if value >= threshold:
            return f"{value / threshold:.2f}{unit}"
    return f"{value / 1e9:.2f}B"

def get_cached_total_work() -> str:
    now = time.time()
    if now - state.total_work_last_fetch <= state.total_work_next_fetch_in:
        with state.parasite_lock:
            return state.total_work_cache

    try:
        url = f"{PARASITE_API_BASE}/account/{BTC_ADDRESS}"
        r = session.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
        total_diff = int(data.get("account", {}).get("total_diff", 0))
        formatted = format_large_work(total_diff)

        with state.parasite_lock:
            state.total_work_cache = formatted
            state.total_work_last_fetch = now
            state.total_work_next_fetch_in = random.uniform(TOTAL_WORK_CACHE_MIN, TOTAL_WORK_CACHE_MAX)

        logger.info(f"Total Work updated: {formatted} (raw: {total_diff:,})")
        return formatted

    except Exception as e:
        logger.warning(f"Failed to fetch total_diff: {e}")
        with state.parasite_lock:
            return state.total_work_cache

def fetch_user_rank() -> str:
    try:
        r = session.get(
            f"{PARASITE_API_BASE}/leaderboard",
            params={"type": "combined", "limit": 9},
            timeout=8
        )
        r.raise_for_status()
        data = r.json()
        addr_short = BTC_ADDRESS[:4] + "..." + BTC_ADDRESS[-4:]
        for i, entry in enumerate(data):
            if entry.get("address", "").lower() == addr_short.lower():
                return str(i + 1)
        return "?"
    except Exception as e:
        logger.error(f"fetch_user_rank failed: {e}")
        return "?"

def fetch_recent_shares() -> List[Tuple[float, float]]:
    try:
        params = {
            "address": BTC_ADDRESS,
            "type": "user-diffs",
            "limit": 9
        }
        r = session.get(f"{PARASITE_API_BASE}/highest-diff", params=params, timeout=5)
        r.raise_for_status()
        data = r.json()

        shares = []
        for item in data:
            diff = parse_difficulty(str(item.get("difficulty", "0")))
            ts = float(item.get("block_timestamp", 0))
            if ts > 0 and diff > 0:
                shares.append((ts, diff))

        shares.sort(key=lambda x: x[0], reverse=True)
        return shares
    except Exception as e:
        logger.error(f"fetch_recent_shares failed: {e}")
        return []

def fetch_historical_hashrate() -> List[Tuple[float, float]]:
    try:
        url = f"{PARASITE_API_BASE}/user/{BTC_ADDRESS}/historical?period=1d&interval={HISTORICAL_INTERVAL}"
        r = session.get(url, timeout=12)
        r.raise_for_status()
        data = r.json()

        points = []
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
    except Exception as e:
        logger.error(f"fetch_historical_hashrate failed: {e}")
        return []
