import os
import random
import pandas as pd
from datetime import datetime
try:
    import ccxt
except ImportError:
    ccxt = None

class Broker:
    def __init__(self, exchange_id="coinbasepro", mode="paper"):
        self.mode = mode.lower()
        self.exchange = None
        if self.mode == "live":
            if not ccxt:
                raise RuntimeError("ccxt is required for live mode.")
            api_key = os.getenv("EXCHANGE_API_KEY")
            api_secret = os.getenv("EXCHANGE_API_SECRET")
            if not api_key or not api_secret:
                raise RuntimeError("Missing API keys for live trading.")
            exchange_cls = getattr(ccxt, exchange_id)
            self.exchange = exchange_cls({
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
            })

    def fetch_ohlcv(self, symbol="BTC/USDT", timeframe="1h", limit=200):
        if self.mode == "paper":
            prices = [20000 + random.gauss(0, 200) for _ in range(limit)]
            df = pd.DataFrame({
                "timestamp": pd.date_range(end=datetime.utcnow(), periods=limit, freq="h"),
                "open": prices,
                "high": [p * (1 + random.uniform(0, 0.01)) for p in prices],
                "low": [p * (1 - random.uniform(0, 0.01)) for p in prices],
                "close": [p * (1 + random.uniform(-0.005, 0.005)) for p in prices],
                "volume": [random.uniform(1, 10) for _ in prices]
            })
            return df
        else:
            data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            return df

    def place_order(self, symbol, side, qty, price=None):
        if self.mode == "paper":
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": symbol,
                "side": side,
                "price": price if price else 20000 + random.uniform(-200, 200),
                "qty": qty,
                "fee": 0.0,
                "pnl": 0.0
            }
        else:
            order = self.exchange.create_market_order(symbol, side, qty)
            filled_price = float(price if price else order.get("average") or order["price"])
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": symbol,
                "side": side,
                "price": filled_price,
                "qty": qty,
                "fee": 0.0,
                "pnl": 0.0
            }
