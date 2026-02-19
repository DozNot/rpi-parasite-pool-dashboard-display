# src/data.py
"""
Shared data structures and global application state
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Tuple
from collections import deque
import threading
import time
import random
from src.constants import DATA_TIMEOUT_SEC

@dataclass
class TickerData:
    source: str
    price: Optional[float] = None
    change_24h: float = 0.0
    last_update: Optional[float] = None

    def is_fresh(self, now: float) -> bool:
        return self.last_update is not None and (now - self.last_update) < DATA_TIMEOUT_SEC

    def update(self, price: float, change: float) -> None:
        self.price = price
        self.change_24h = change
        self.last_update = time.time()

class AppState:
    def __init__(self):
        self.binance = TickerData("binance")
        self.kraken = TickerData("kraken")
        self.data_lock = threading.Lock()

        # History
        self.hash_history: deque[float] = deque(maxlen=128)
        self.historical_hashrate: List[Tuple[float, float]] = []
        self.historical_last_fetch = 0.0

        # Recent high-diff shares (up to 9)
        self.recent_shares: deque[Tuple[float, float]] = deque(maxlen=9)

        # Pool & user data
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

        # Total work (cached)
        self.total_work_cache: str = "?.?B"
        self.total_work_last_fetch: float = 0.0
        self.total_work_next_fetch_in: float = random.uniform(30, 90)

        # Mempool
        self.mempool: Dict[str, Any] = {
            "fees_sats_vb": None,
            "block_height": None,
            "mining_pool": None,
            "network_hashrate_eh": None,
            "network_difficulty": None,
        }
        self.mempool_lock = threading.Lock()

        # Network / status
        self.binance_ws_status = "Connecting…"
        self.kraken_ws_status = "Connecting…"
        self.wifi_ok = False
        self.last_wifi_check = 0.0

state = AppState()
