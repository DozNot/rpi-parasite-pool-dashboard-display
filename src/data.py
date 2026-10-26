"""
Shared data structures and global application state.

All mutable shared data is protected by the appropriate locks.
"""

from __future__ import annotations

import random
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple

from src.constants import DATA_TIMEOUT_SEC


@dataclass
class TickerData:
    """Real-time price ticker from a single exchange."""

    source: str
    price: Optional[float] = None
    change_24h: float = 0.0
    last_update: Optional[float] = None

    def is_fresh(self, now: float) -> bool:
        """Return True if the last update is within the configured timeout."""
        return (
            self.last_update is not None
            and (now - self.last_update) < DATA_TIMEOUT_SEC
        )

    def update(self, price: float, change: float) -> None:
        """Update price and 24h change, refreshing the timestamp."""
        self.price = price
        self.change_24h = change
        self.last_update = time.time()


class AppState:
    """
    Central thread-safe application state.

    Holds price tickers, Parasite Pool stats, mempool data,
    connection status and historical series used by the renderer.
    """

    def __init__(self) -> None:
        # Price tickers
        self.binance = TickerData("binance")
        self.kraken = TickerData("kraken")
        self.data_lock = threading.Lock()

        # Hashrate history (live rolling window)
        self.hash_history: Deque[float] = deque(maxlen=128)

        # Historical hashrate points from Parasite API: (unix_ts, hashrate_th)
        self.historical_hashrate: List[Tuple[float, float]] = []
        self.historical_last_fetch: float = 0.0

        # Recent high-difficulty shares: (unix_ts, difficulty)
        self.recent_shares: Deque[Tuple[float, float]] = deque(maxlen=9)

        # Parasite pool & user stats
        self.parasite: Dict[str, Any] = {
            "pool_hashrate_ph": 0.0,
            "pool_hashrate_str": "?.?? PH/s",
            "pool_best_diff_str": "??",
            "user_rank": "?",
            "user_work": "?.?B",
            "user_uptime": "?d ?h",
            "user_hashrate_th": 0.0,
            "user_hashrate_str": "?.?? TH/s",
            "user_best_diff_float": 0.0,
            "user_workers": 0,
            "last_update": 0.0,
            "last_success_time": 0.0,
        }
        self.parasite_lock = threading.Lock()

        # Cached total work (expensive endpoint, refreshed infrequently)
        self.total_work_cache: str = "?.?B"
        self.total_work_last_fetch: float = 0.0
        self.total_work_next_fetch_in: float = random.uniform(30, 90)

        # Mempool / network stats
        self.mempool: Dict[str, Any] = {
            "fees_sats_vb": None,
            "block_height": None,
            "mining_pool": None,
            "network_hashrate_eh": None,
            "network_difficulty": None,
        }
        self.mempool_lock = threading.Lock()

        # Connection / status indicators
        self.binance_ws_status: str = "Connecting…"
        self.kraken_ws_status: str = "Connecting…"
        self.wifi_ok: bool = False
        self.last_wifi_check: float = 0.0


# Singleton shared by all modules
state = AppState()
