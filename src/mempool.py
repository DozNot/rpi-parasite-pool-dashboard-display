# src/mempool.py
"""
Polling thread for Bitcoin network statistics from mempool.space API.
Fetches fees, block height, latest pool, network hashrate and difficulty.
"""
import time
import logging
import requests
from src.data import state
from src.constants import MEMPOOL_POLL_INTERVAL
from src.helpers import session

logger = logging.getLogger(__name__)

def run_mempool_polling(state):
    headers = {"User-Agent": "rpi-parasite-pool-dashboard-display/1.0"}
    url_base = "https://mempool.space/api"

    while True:
        try:
            fees = session.get(f"{url_base}/v1/fees/precise", timeout=15, headers=headers).json()
            fees_val = float(fees.get("halfHourFee"))

            height = int(session.get(f"{url_base}/blocks/tip/height", timeout=10, headers=headers).text)
            pool_name = net_diff = None

            if height:
                blk_hash = session.get(f"{url_base}/block-height/{height}", timeout=10, headers=headers).text
                blk = session.get(f"{url_base}/v1/block/{blk_hash}", timeout=12, headers=headers).json()
                pool_name = blk.get("extras", {}).get("pool", {}).get("name")
                net_diff = blk.get("difficulty")

            hr = session.get(f"{url_base}/v1/mining/hashrate/3m", timeout=12, headers=headers).json()
            net_hr_eh = hr.get("currentHashrate", 0) / 1e18

            with state.mempool_lock:
                state.mempool.update({
                    "fees_sats_vb": fees_val,
                    "block_height": height,
                    "mining_pool": pool_name,
                    "network_hashrate_eh": net_hr_eh,
                    "network_difficulty": net_diff,
                })
        except Exception:
            with state.mempool_lock:
                state.mempool.update({
                    "fees_sats_vb": None,
                    "block_height": None,
                    "mining_pool": None,
                    "network_hashrate_eh": None,
                    "network_difficulty": None,
                })

        time.sleep(MEMPOOL_POLL_INTERVAL)
