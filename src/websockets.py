# src/websockets.py
"""
WebSocket clients (Binance, Kraken) for real-time prices.
"""
import json
import time
import logging
import websocket
from src.data import state

logger = logging.getLogger(__name__)

def run_kraken_websocket(state):
    def on_message(ws, message):
        try:
            msg = json.loads(message)
            if not isinstance(msg, list) or len(msg) < 4 or msg[2] != "ticker":
                return
            _, ticker_data, _, pair = msg
            if pair != "XBT/USD":
                return
            price = float(ticker_data["c"][0])
            open_24h = float(ticker_data["o"][1])
            change_pct = ((price - open_24h) / open_24h * 100) if open_24h > 0 else 0.0
            with state.data_lock:
                state.kraken.update(price, change_pct)
        except Exception:
            pass

    def on_open(ws):
        state.kraken_ws_status = "Live"
        ws.send(json.dumps({
            "event": "subscribe",
            "pair": ["XBT/USD"],
            "subscription": {"name": "ticker"}
        }))

    def on_error(ws, error):
        state.kraken_ws_status = "Error"

    def on_close(ws, code=None, reason=None):
        state.kraken_ws_status = "Reconnecting…"

    backoff = 1.0
    while True:
        ws = websocket.WebSocketApp(
            "wss://ws.kraken.com/",
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        ws.run_forever(ping_interval=25, ping_timeout=10)
        time.sleep(backoff)
        backoff = min(backoff * 1.8, 120)

def run_binance_websocket(state):
    def on_message(ws, message):
        try:
            d = json.loads(message)
            if d.get("s", "").lower() != "btcusdt":
                return
            price = float(d["c"])
            change_pct = float(d["P"])
            with state.data_lock:
                state.binance.update(price, change_pct)
        except Exception:
            pass

    def on_open(ws):
        state.binance_ws_status = "Live"

    def on_error(ws, error):
        state.binance_ws_status = "Error"

    def on_close(ws, code=None, reason=None):
        state.binance_ws_status = "Reconnecting…"

    backoff = 1.0
    while True:
        ws = websocket.WebSocketApp(
            "wss://stream.binance.com:9443/ws/btcusdt@ticker",
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        ws.run_forever(ping_interval=30, ping_timeout=10)
        time.sleep(backoff)
        backoff = min(backoff * 1.8, 120)
