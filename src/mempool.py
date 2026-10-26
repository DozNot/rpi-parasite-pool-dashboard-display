"""
Polling thread for Bitcoin network statistics from mempool.space.

Fetches recommended fees, tip height, latest mining pool,
network hashrate and network difficulty.
"""

from __future__ import annotations

import logging
import time

from src.constants import MEMPOOL_POLL_INTERVAL
from src.data import AppState
from src.helpers import session

logger = logging.getLogger(__name__)

MEMPOOL_API_BASE = "https://mempool.space/api"
USER_AGENT = {"User-Agent": "rpi-parasite-pool-dashboard-display/1.0"}


def run_mempool_polling(state: AppState) -> None:
    """
    Continuously poll mempool.space and update state.mempool.

    On any failure the fields are reset to None so the UI can show
    a loading / unavailable state.
    """
    while True:
        try:
            fees = session.get(
                f"{MEMPOOL_API_BASE}/v1/fees/precise",
                timeout=15,
                headers=USER_AGENT,
            ).json()
            fees_val = float(fees.get("halfHourFee"))

            height = int(
                session.get(
                    f"{MEMPOOL_API_BASE}/blocks/tip/height",
                    timeout=10,
                    headers=USER_AGENT,
                ).text
            )

            pool_name = None
            net_diff = None
            if height:
                blk_hash = session.get(
                    f"{MEMPOOL_API_BASE}/block-height/{height}",
                    timeout=10,
                    headers=USER_AGENT,
                ).text
                blk = session.get(
                    f"{MEMPOOL_API_BASE}/v1/block/{blk_hash}",
                    timeout=12,
                    headers=USER_AGENT,
                ).json()
                pool_name = blk.get("extras", {}).get("pool", {}).get("name")
                net_diff = blk.get("difficulty")

            hr = session.get(
                f"{MEMPOOL_API_BASE}/v1/mining/hashrate/3m",
                timeout=12,
                headers=USER_AGENT,
            ).json()
            net_hr_eh = hr.get("currentHashrate", 0) / 1e18

            with state.mempool_lock:
                state.mempool.update(
                    {
                        "fees_sats_vb": fees_val,
                        "block_height": height,
                        "mining_pool": pool_name,
                        "network_hashrate_eh": net_hr_eh,
                        "network_difficulty": net_diff,
                    }
                )
        except Exception as exc:
            logger.warning("Mempool poll failed: %s", exp)
            with state.mempool_lock:
                state.mempool.update(
                    {
                        "fees_sats_vb": None,
                        "block_height": None,
                        "mining_pool": None,
                        "network_hashrate_eh": None,
                        "network_difficulty": None,
                    }
                )

        time.sleep(MEMPOOL_POLL_INTERVAL)
