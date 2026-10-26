"""
Polling threads for Parasite Pool data.

- run_parasite_polling: pool + user stats, rank, historical hashrate
- run_recent_shares_worker: recent high-difficulty shares
"""

from __future__ import annotations

import logging
import time
from collections import deque

from src.constants import (
    BTC_ADDRESS,
    PARASITE_API_BASE,
    PARASITE_POLL_INTERVAL,
)
from src.data import AppState
from src.helpers import (
    fetch_historical_hashrate,
    fetch_recent_shares,
    fetch_user_rank,
    format_pool_best_diff,
    get_cached_total_work,
    parse_difficulty,
    session,
)

logger = logging.getLogger(__name__)

# How often to refresh the historical hashrate curve (seconds)
HISTORICAL_REFRESH_INTERVAL = 300


def run_parasite_polling(state: AppState) -> None:
    """
    Continuously poll Parasite Pool endpoints and update state.parasite.

    Also periodically refreshes the historical hashrate series used
    by the chart.
    """
    while True:
        now = time.time()
        success = False

        with state.parasite_lock:
            prev = state.parasite.copy()

        # Defaults from previous successful values
        ph = prev["pool_hashrate_ph"]
        pool_str = prev["pool_hashrate_str"]
        pool_best_str = prev["pool_best_diff_str"]
        user_hr_th = prev["user_hashrate_th"]
        user_hr_str = prev["user_hashrate_str"]
        user_workers = prev["user_workers"]
        user_best_float = prev["user_best_diff_float"]
        user_uptime = prev["user_uptime"]
        user_rank = prev["user_rank"]

        # --- Pool-wide stats ---
        try:
            response = session.get(
                f"{PARASITE_API_BASE}/pool-stats", timeout=7
            )
            response.raise_for_status()
            data = response.json()
            ph = data.get("hashrate", 0) / 1e15
            pool_str = f"{ph:.2f} PH/s"
            raw_diff = str(data.get("highestDifficulty", "??"))
            pool_best_str = format_pool_best_diff(raw_diff)
            success = True
        except Exception as exc:
            logger.error("Failed to fetch pool stats: %s", exp)

        # --- User stats ---
        try:
            response = session.get(
                f"{PARASITE_API_BASE}/user/{BTC_ADDRESS}", timeout=8
            )
            response.raise_for_status()
            data = response.json()
            workers = data.get("workerData", [])
            hr_sum = (
                sum(float(w.get("hashrate", 0)) for w in workers)
                if workers
                else data.get("hashrate", 0)
            )
            user_hr_th = hr_sum / 1e12
            user_hr_str = (
                f"{user_hr_th:.2f} TH/s" if user_hr_th > 0.05 else "?.?? TH/s"
            )
            user_workers = data.get("workers", 0)
            user_best_float = parse_difficulty(
                str(data.get("bestDifficulty", "0"))
            )
            user_uptime = data.get("uptime", "?d ?h")
            success = True
        except Exception as exp:
            logger.error("Failed to fetch user stats: %s", exp)

        # --- Cached total work ---
        user_work = get_cached_total_work()

        # --- Rank ---
        new_rank = fetch_user_rank()
        if new_rank != "?":
            user_rank = new_rank
            success = True

        # --- Historical hashrate curve (less frequent) ---
        if now - state.historical_last_fetch > HISTORICAL_REFRESH_INTERVAL:
            hist = fetch_historical_hashrate()
            if hist:
                with state.parasite_lock:
                    state.historical_hashrate = hist
                state.historical_last_fetch = now

        # --- Commit updates ---
        with state.parasite_lock:
            state.parasite.update(
                {
                    "pool_hashrate_ph": ph,
                    "pool_hashrate_str": pool_str,
                    "pool_best_diff_str": pool_best_str,
                    "user_hashrate_th": user_hr_th,
                    "user_hashrate_str": user_hr_str,
                    "user_workers": user_workers,
                    "user_best_diff_float": user_best_float,
                    "user_uptime": user_uptime,
                    "user_work": user_work,
                    "user_rank": user_rank,
                }
            )
            if success:
                state.parasite["last_success_time"] = now
                state.parasite["last_update"] = now
                if user_hr_th > 0.1:
                    state.hash_history.append(user_hr_th)

        time.sleep(PARASITE_POLL_INTERVAL)


def run_recent_shares_worker(state: AppState) -> None:
    """
    Periodically fetch recent high-difficulty shares and keep the
    9 most recent entries in state.recent_shares.
    """
    last_fetch = 0.0
    while True:
        now = time.time()
        if now - last_fetch < 10:
            time.sleep(1)
            continue

        last_fetch = now
        shares = fetch_recent_shares()
        if shares:
            with state.parasite_lock:
                existing_ts = {ts for ts, _ in state.recent_shares}
                for ts, diff in shares:
                    if ts not in existing_ts:
                        state.recent_shares.append((ts, diff))
                # Keep only the 9 newest, sorted by timestamp descending
                state.recent_shares = deque(
                    sorted(
                        state.recent_shares, key=lambda x: x[0], reverse=True
                    )[:9]
                )
            logger.info(
                "Updated recent shares: %d entries", len(state.recent_shares)
            )

        time.sleep(1)
