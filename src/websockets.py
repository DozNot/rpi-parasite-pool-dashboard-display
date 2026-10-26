"""
WebSocket clients for real-time BTC price feeds (Binance primary, Kraken fallback).

Both clients reconnect automatically with exponential backoff.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import websocket

from src.data import AppState

logger = logging.getLogger(__name__)


def run_kraken_websocket(state: AppState) -> None:
    """
    Long-running Kraken ticker WebSocket client.

    Updates state.kraken and state.kraken_ws_status.
    Reconnects with exponential backoff on failure.
    """

    def on_message(ws: websocket.WebSocketApp, message: str) -> None:
        try:
            msg = json.loads(message)
            if not isinstance(msg, list) or len(msg) < 4 or msg[2] != "ticker":
                return
            _, ticker_data, _, pair = msg
            if pair != "XBT/USD":
                return
            price = float(ticker_data["c"][0])
            open_24h = float(ticker_data["o"][1])
            change_pct = (
                ((price - open_24h) / open_24h * 100) if open_24h > 0 else 0.0
            )
            with state.data_lock:
                state.kraken.update(price, change_pct)
        except Exception as exc:
            logger.debug("Kraken message parse error: %s", exc)

    def on_open(ws: websocket.WebSocketApp) -> None:
        state.kraken_ws_status = "Live"
        ws.send(
            json.dumps(
                {
                    "event": "subscribe",
                    "pair": ["XBT/USD"],
                    "subscription": {"name": "ticker"},
                }
            )
        )
        logger.info("Kraken WebSocket connected")

    def on_error(ws: websocket.WebSocketApp, error: Any) -> None:
        state.kraken_ws_status = "Error"
        logger.warning("Kraken WebSocket error: %s", error)

    def on_close(
        ws: websocket.WebSocketApp,
        code: Any = None,
        reason: Any = None,
    ) -> None:
        state.kraken_ws_status = "Reconnecting…"
        logger.info("Kraken WebSocket closed (code=%s, reason=%s)", code, reason)

    backoff = 1.0
    while True:
        ws = websocket.WebSocketApp(
            "wss://ws.kraken.com/",
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
        )
        ws.run_forever(ping_interval=25, ping_timeout=10)
        time.sleep(backoff)
        backoff = min(backoff * 1.8, 120)


def run_binance_websocket(state: AppState) -> None:
    """
    Long-running Binance BTCUSDT ticker WebSocket client.

    Updates state.binance and state.binance_ws_status.
    Reconnects with exponential backoff on failure.
    """

    def on_message(ws: websocket.WebSocketApp, message: str) -> None:
        try:
            data = json.loads(message)
            if data.get("s", "").lower() != "btcusdt":
                return
            price = float(data["c"])
            change_pct = float(data["P"])
            with state.data_lock:
                state.binance.update(price, change_pct)
        except Exception as exc:
            logger.debug("Binance message parse error: %s", exc)

    def on_open(ws: websocket.WebSocketApp) -> None:
        state.binance_ws_status = "Live"
        logger.info("Binance WebSocket connected")

    def on_error(ws: websocket.WebSocketApp, error: Any) -> None:
        state.binance_ws_status = "Error"
        logger.warning("Binance WebSocket error: %s", error)

    def on_close(
        ws: websocket.WebSocketApp,
        code: Any = None,
        reason: Any = None,
    ) -> None:
        state.binance_ws_status = "Reconnecting…"
        logger.info("Binance WebSocket closed (code=%s, reason=%s)", code, reason)

    backoff = 1.0
    while True:
        ws = websocket.WebSocketApp(
            "wss://stream.binance.com:9443/ws/btcusdt@ticker",
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open,
        )
        ws.run_forever(ping_interval=30, ping_timeout=10)
        time.sleep(backoff)
        backoff = min(backoff * 1.8, 120)
