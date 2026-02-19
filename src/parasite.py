# src/parasite.py
"""
Polling Parasite Pool data from Parasite API.
"""
import time
import logging
import requests
from collections import deque
from src.data import state
from src.constants import PARASITE_POLL_INTERVAL, PARASITE_API_BASE, BTC_ADDRESS
from src.helpers import get_cached_total_work, fetch_user_rank, fetch_historical_hashrate, fetch_recent_shares, format_pool_best_diff, parse_difficulty, session

logger = logging.getLogger(__name__)

HISTORICAL_REFRESH_INTERVAL = 300

def run_parasite_polling(state):
    while True:
        now = time.time()
        success = False
        with state.parasite_lock:
            prev = state.parasite.copy()

        ph = prev["pool_hashrate_ph"]
        pool_str = prev["pool_hashrate_str"]
        pool_best_str = prev["pool_best_diff_str"]
        user_hr_th = prev["user_hashrate_th"]
        user_hr_str = prev["user_hashrate_str"]
        user_workers = prev["user_workers"]
        user_best_float = prev["user_best_diff_float"]
        user_uptime = prev["user_uptime"]
        user_rank = prev["user_rank"]

        # Pool stats
        try:
            r = session.get(f"{PARASITE_API_BASE}/pool-stats", timeout=7)
            r.raise_for_status()
            d = r.json()
            ph = d.get("hashrate", 0) / 1e15
            pool_str = f"{ph:.2f} PH/s"
            raw_diff = str(d.get("highestDifficulty", "??"))
            pool_best_str = format_pool_best_diff(raw_diff)
            success = True
        except Exception as e:
            logger.error(f"Failed to fetch pool stats: {e}")

        # User stats
        try:
            r = session.get(f"{PARASITE_API_BASE}/user/{BTC_ADDRESS}", timeout=8)
            r.raise_for_status()
            d = r.json()
            workers = d.get("workerData", [])
            hr_sum = sum(float(w.get("hashrate", 0)) for w in workers) if workers else d.get("hashrate", 0)
            user_hr_th = hr_sum / 1e12
            user_hr_str = f"{user_hr_th:.2f} TH/s" if user_hr_th > 0.05 else "?.?? TH/s"
            user_workers = d.get("workers", 0)
            user_best_float = parse_difficulty(str(d.get("bestDifficulty", "0")))
            user_uptime = d.get("uptime", "?d ?h")
            success = True
        except Exception as e:
            logger.error(f"Failed to fetch user stats: {e}")

        # Total work (cached)
        user_work = get_cached_total_work()

        # Rank
        new_rank = fetch_user_rank()
        if new_rank != "?":
            user_rank = new_rank
            success = True

        # Historical hashrate curve
        if now - state.historical_last_fetch > HISTORICAL_REFRESH_INTERVAL:
            hist = fetch_historical_hashrate()
            if hist:
                with state.parasite_lock:
                    state.historical_hashrate = hist
                state.historical_last_fetch = now

        # Update state
        with state.parasite_lock:
            state.parasite.update({
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
            })
            if success:
                state.parasite["last_success_time"] = now
                state.parasite["last_update"] = now
                if user_hr_th > 0.1:
                    state.hash_history.append(user_hr_th)

        time.sleep(PARASITE_POLL_INTERVAL)


def run_recent_shares_worker(state):
    last_fetch = 0
    while True:
        now = time.time()
        if now - last_fetch < 10:  # Not more than once every 10 seconds
            time.sleep(1)
            continue
        last_fetch = now
        shares = fetch_recent_shares()
        if shares:
            with state.parasite_lock:
                # Add only new records
                existing_ts = {ts for ts, _ in state.recent_shares}
                for ts, diff in shares:
                    if ts not in existing_ts:
                        state.recent_shares.append((ts, diff))
                # Sort by timestamp and keep the 9 most recent
                state.recent_shares = deque(
                    sorted(state.recent_shares, key=lambda x: x[0], reverse=True)[:9]
                )
            logger.info(f"Updated recent shares: {len(state.recent_shares)} entries")
        time.sleep(1)
