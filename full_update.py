#!/usr/bin/env python3
import os
import sys
from pathlib import Path
import subprocess

# ========== Configuration ==========

# Define all files and their content
FILES = {
    "config/config.yaml": """\
mode: paper
exchange_id: coinbasepro
symbol: BTC/USDT
timeframe: 1h
trade_qty: 0.001

risk:
  fast: 12
  slow: 26
  risk_per_trade: 0.005
  stop_loss: 0.02
  take_profit: 0.04

limits:
  max_daily_dd: 0.02
  max_session_dd: 0.05
  max_open_trades: 1

auto:
  enabled: false
  interval_min: 60
  run_minutes: 10
  last_auto_start: null

notifications:
  email:
    enabled: false
    smtp_server: ""
    smtp_port: 587
    sender: ""
    password: ""
    recipients: []
  telegram:
    enabled: false
    bot_token: ""
    chat_id: ""
""",

    "requirements.txt": """\
streamlit
pandas
pyyaml
plotly
requests
ccxt
""",

    "bot/__init__.py": """\
# This file makes bot/ a Python package
""",

    "bot/config_loader.py": """\
import os
import yaml
from pathlib import Path

DEFAULT_CONFIG = {
    "mode": "paper",
    "exchange_id": "coinbasepro",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "trade_qty": 0.001,
    "risk": {
        "fast": 12,
        "slow": 26,
        "risk_per_trade": 0.005,
        "stop_loss": 0.02,
        "take_profit": 0.04
    },
    "limits": {
        "max_daily_dd": 0.02,
        "max_session_dd": 0.05,
        "max_open_trades": 1
    },
    "auto": {
        "enabled": False,
        "interval_min": 60,
        "run_minutes": 10,
        "last_auto_start": None
    },
    "notifications": {
        "email": {
            "enabled": False,
            "smtp_server": "",
            "smtp_port": 587,
            "sender": "",
            "password": "",
            "recipients": []
        },
        "telegram": {
            "enabled": False,
            "bot_token": "",
            "chat_id": ""
        }
    }
}

def safe_cast(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default

def load_config(config_path: str = None):
    if config_path is None:
        config_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    cfg = {}
    if Path(config_path).exists():
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}

    env = {
        "mode": os.getenv("TRADING_MODE"),
        "exchange_id": os.getenv("EXCHANGE_ID"),
        "symbol": os.getenv("SYMBOL"),
        "timeframe": os.getenv("TIMEFRAME"),
        "trade_qty": safe_cast(os.getenv("TRADE_QTY"), float)
    }
    env = {k: v for k, v in env.items() if v is not None}

    def merge(d, c):
        out = {}
        for k in d:
            if k in c and isinstance(d[k], dict) and isinstance(c[k], dict):
                out[k] = merge(d[k], c[k])
            else:
                out[k] = c.get(k, d[k])
        for k in c:
            if k not in d:
                out[k] = c[k]
        return out

    return merge(DEFAULT_CONFIG, {**cfg, **env})
""",

    "bot/broker.py": """\
import os
import random
from datetime import datetime, timezone
import pandas as pd

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
            prices = [30000 + random.gauss(0, 200) for _ in range(limit)]
            ts = pd.date_range(end=pd.Timestamp.utcnow(), periods=limit, freq="h")
            df = pd.DataFrame({
                "timestamp": ts,
                "open": prices,
                "high": [p * (1 + random.uniform(0, 0.01)) for p in prices],
                "low": [p * (1 - random.uniform(0, 0.01)) for p in prices],
                "close": [p * (1 + random.uniform(-0.005, 0.005)) for p in prices],
                "volume": [random.uniform(1, 10) for _ in prices]
            })
            return df
        else:
            try:
                data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
                df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
                return df
            except Exception as e:
                print(f"Error fetching OHLCV: {e}")
                return pd.DataFrame()

    def place_order(self, symbol, side, qty, price=None):
        ts = datetime.now(timezone.utc).isoformat()
        if self.mode == "paper":
            executed = float(price if price else 30000 + random.uniform(-200, 200))
            fee = 0.0
            return {
                "timestamp": ts,
                "symbol": symbol,
                "side": side,
                "price": executed,
                "qty": float(qty),
                "fee": fee,
                "pnl": 0.0
            }
        else:
            try:
                order = self.exchange.create_market_order(symbol, side, qty)
                filled_price = float(price if price else order.get("average") or order.get("price"))
                return {
                    "timestamp": ts,
                    "symbol": symbol,
                    "side": side,
                    "price": filled_price,
                    "qty": float(qty),
                    "fee": 0.0,
                    "pnl": 0.0
                }
            except Exception as e:
                print(f"Error placing order: {e}")
                return None
""",

    "bot/notifications.py": """\
from bot.config_loader import load_config
import smtplib
from email.mime.text import MIMEText
import requests

def notify_email(subject: str, body: str):
    cfg = load_config()
    em = cfg.get("notifications", {}).get("email", {})
    if not em.get("enabled", False):
        return
    server = em.get("smtp_server")
    port = em.get("smtp_port")
    sender = em.get("sender")
    pwd = em.get("password")
    recips = em.get("recipients", [])
    if not (server and sender and pwd and recips):
        print("⚠️ Email config incomplete")
        return
    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recips)
    try:
        smtp = smtplib.SMTP(server, port, timeout=10)
        smtp.starttls()
        smtp.login(sender, pwd)
        smtp.sendmail(sender, recips, msg.as_string())
        smtp.quit()
    except Exception as e:
        print("Email notify failed:", e)

def notify_telegram(text: str):
    cfg = load_config()
    tg = cfg.get("notifications", {}).get("telegram", {})
    if not tg.get("enabled", False):
        return
    token = tg.get("bot_token")
    chat = tg.get("chat_id")
    if not (token and chat):
        print("⚠️ Telegram config incomplete")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat, "text": text}
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print("Telegram notify failed:", e)
""",

    "bot/bot.py": """\
import os
import time
import sqlite3
import logging
from pathlib import Path
import pandas as pd
from bot.broker import Broker
from bot.config_loader import load_config
from bot.notifications import notify_email, notify_telegram

STORAGE = Path(__file__).resolve().parents[1] / "storage"
DB_PATH = STORAGE / "journal.db"
KILL_FLAG = STORAGE / "kill.flag"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
STORAGE.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def init_db():
    with sqlite3.connect(DB_PATH) as con:
        con.execute(\"\"\"CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,
                price REAL,
                qty REAL,
                fee REAL,
                pnl REAL
            )\"\"\")

def ema_crossover(df, fast=12, slow=26):
    df["ema_fast"] = df["close"].ewm(span=fast).mean()
    df["ema_slow"] = df["close"].ewm(span=slow).mean()
    df["signal"] = (df["ema_fast"] > df["ema_slow"]).astype(int)
    return df

def run_bot():
    last_mtime = None
    cfg = load_config(CONFIG_PATH)
    broker = Broker(exchange_id=cfg.get("exchange_id"), mode=cfg.get("mode"))
    position = None

    init_db()
    logging.info(f\"Bot started in {cfg.get('mode')} on {cfg.get('symbol')}\")
    notify_email("Bot Started", str(cfg))
    notify_telegram(f\"Bot started: {cfg.get('symbol')}, mode {cfg.get('mode')}\")
    while True:
        try:
            mtime = os.path.getmtime(CONFIG_PATH)
            if last_mtime is None or mtime > last_mtime:
                cfg = load_config(CONFIG_PATH)
                broker = Broker(exchange_id=cfg.get("exchange_id"), mode=cfg.get("mode"))
                logging.info("Config reloaded")
                last_mtime = mtime
        except Exception as e:
            logging.error(f"Config reload error: {e}")

        if KILL_FLAG.exists():
            logging.info("Kill flag detected. Exiting.")
            notify_email("Bot Stopped", "Kill flag triggered")
            notify_telegram("Bot stopped")
            break

        try:
            df = broker.fetch_ohlcv(cfg.get("symbol"), cfg.get("timeframe"), limit=200)
            df = ema_crossover(df)
            last, prev = df.iloc[-1], df.iloc[-2]

            with sqlite3.connect(DB_PATH) as con:
                if prev["signal"] == 0 and last["signal"] == 1 and position is None:
                    trade = broker.place_order(cfg.get("symbol"), "buy", cfg.get("trade_qty"), float(last["close"]))
                    trade["pnl"] = 0
                    pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                    logging.info(f\"BUY at {trade['price']}\")
                    notify_email("Trade BUY", str(trade))
                    notify_telegram(f\"BUY {cfg.get('symbol')} @ {trade['price']}\")
                    position = trade
                elif prev["signal"] == 1 and last["signal"] == 0 and position is not None:
                    trade = broker.place_order(cfg.get("symbol"), "sell", cfg.get("trade_qty"), float(last["close"]))
                    trade["pnl"] = 0
                    pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                    logging.info(f\"SELL at {trade['price']}\")
                    notify_email("Trade SELL", str(trade))
                    notify_telegram(f\"SELL {cfg.get('symbol')} @ {trade['price']}\")
                    position = None
        except Exception as e:
            logging.error(f\"Trading error: {e}\")
            notify_email("Bot Error", str(e))
            notify_telegram(f\"Error: {e}\")

        time.sleep(10)

if __name__ == \"__main__\":
    run_bot()
""",

    "app/dashboard.py": """\
import os
import sqlite3
import pandas as pd
import streamlit as st
import yaml
import json
import requests
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).resolve().parents[1]))

from bot.config_loader import load_config
from bot.broker import Broker

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
DB_PATH = Path(__file__).resolve().parents[1] / "storage" / "journal.db"
KILL_FLAG = Path(__file__).resolve().parents[1] / "storage" / "kill.flag"

def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute(\"\"\"CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,
                price REAL,
                qty REAL,
                fee REAL,
                pnl REAL
            )\"\"\")

def read_trades(symbol=None):
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as con:
        if symbol:
            df = pd.read_sql(\"SELECT * FROM trades WHERE symbol = ? ORDER BY timestamp DESC\", con, params=(symbol,))
        else:
            df = pd.read_sql(\"SELECT * FROM trades ORDER BY timestamp DESC\", con)
    if not df.empty:
        df[\"timestamp\"] = pd.to_datetime(df[\"timestamp\"])
    return df

def write_config(cfg: dict):
    with open(CONFIG_PATH, \"w\") as f:
        yaml.safe_dump(cfg, f)

def fetch_products():
    try:
        resp = requests.get(\"https://api.coinbase.com/api/v3/brokerage/products\", timeout=5)
        resp.raise_for_status()
        arr = resp.json().get(\"products\", [])
        return sorted([p.get(\"product_id\") for p in arr if p.get(\"product_id\")])
    except Exception as e:
        st.warning(f\"Could not fetch products: {e}\")
        return []

def plot_candles_ema(df, trades, ema_fast, ema_slow):
    import plotly.graph_objects as go
    df[\"ema_fast\"] = df[\"close\"].ewm(span=ema_fast).mean()
    df[\"ema_slow\"] = df[\"close\"].ewm(span=ema_slow).mean()

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df[\"open\"], high=df[\"high\"], low=df[\"low\"], close=df[\"close\"], name=\"Price\"
    ))
    fig.add_trace(go.Scatter(x=df.index, y=df[\"ema_fast\"], mode=\"lines\", name=f\"EMA{ema_fast}\"))
    fig.add_trace(go.Scatter(x=df.index, y=df[\"ema_slow\"], mode=\"lines\", name=f\"EMA{ema_slow}\"))

    if trades is not None and not trades.empty:
        buys = trades[trades[\"side\"].str.lower() == \"buy\"]
        sells = trades[trades[\"side\"].str.lower() == \"sell\"]
        fig.add_trace(go.Scatter(
            x=buys[\"timestamp\"], y=buys[\"price\"], mode=\"markers\", marker=dict(symbol=\"triangle-up\", color=\"green\", size=10), name=\"Buys\"
        ))
        fig.add_trace(go.Scatter(
            x=sells[\"timestamp\"], y=sells[\"price\"], mode=\"markers\", marker=dict(symbol=\"triangle-down\", color=\"red\", size=10), name=\"Sells\"
        ))
    fig.update_layout(xaxis_rangeslider_visible=False, template=\"plotly_dark\", height=600)
    return fig

def main():
    st.set_page_config(page_title=\"Crypto Trading Bot Dashboard\", layout=\"wide\")
    st.title(\"📈 Crypto Trading Bot Dashboard\")
    init_db()
    cfg = load_config()

    st.sidebar.header(\"Settings & Options\")
    products = fetch_products()
    default = cfg.get(\"symbol\", \"\")
    symbol = st.sidebar.selectbox(\"Trading Pair\", options=products or [default], index=products.index(default) if default in products else 0)
    timeframe = st.sidebar.selectbox(\"Timeframe\", [\"1m\",\"5m\",\"15m\",\"1h\",\"4h\",\"1d\"], index=[\"1m\",\"5m\",\"15m\",\"1h\",\"4h\",\"1d\"].index(cfg.get(\"timeframe\",\"1h\")))
    ema_fast = st.sidebar.number_input(\"EMA Fast\", min_value=1, value=cfg.get(\"risk\", {}).get(\"fast\", 12))
    ema_slow = st.sidebar.number_input(\"EMA Slow\", min_value=1, value=cfg.get(\"risk\", {}).get(\"slow\", 26))

    if st.sidebar.button(\"💾 Save & Apply\"):
        new = cfg.copy()
        new[\"symbol\"] = symbol
        new[\"timeframe\"] = timeframe
        new.setdefault(\"risk\", {})[\"fast\"] = ema_fast
        new.setdefault(\"risk\", {})[\"slow\"] = ema_slow
        write_config(new)
        st.sidebar.success(\"Configuration saved\")

    tab1, tab2, tab3 = st.tabs([\"Chart\", \"Trades\", \"Controls\"])
    with tab1:
        trades = read_trades(symbol=symbol)
        try:
            broker = Broker(exchange_id=cfg.get(\"exchange_id\"), mode=cfg.get(\"mode\"))
            df = broker.fetch_ohlcv(symbol, timeframe, limit=200)
            df[\"timestamp\"] = pd.to_datetime(df[\"timestamp\"])
            df = df.set_index(\"timestamp\")
        except Exception as e:
            st.error(f\"Price fetch failed: {e}\")
            df = pd.DataFrame()

        if not df.empty:
            fig = plot_candles_ema(df, trades, ema_fast, ema_slow)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(\"No price data\")

    with tab2:
        trades = read_trades(symbol=symbol)
        if trades.empty:
            st.info(\"No trades recorded\")
        else:
            st.dataframe(trades)

    with tab3:
        st.subheader(\"Bot Controls & Config\")
        st.json(cfg)
        c1, c2 = st.columns(2)
        if c1.button(\"▶️ Start Bot\"):
            if KILL_FLAG.exists():
                KILL_FLAG.unlink(missing_ok=True)
            st.success(\"Bot start flagged\")
        if c2.button(\"⏹ Stop Bot\"):
            KILL_FLAG.write_text(\"stop\")
            st.warning(\"Bot stop flagged\")

        st.subheader(\"Available Products\")
        st.write(products or [])

if __name__ == \"__main__\":
    main()
"""
}

def write_all_files():
    for relpath, content in FILES.items():
        path = Path(relpath)
        # ensure directory
        dirp = path.parent
        if not dirp.exists():
            dirp.mkdir(parents=True, exist_ok=True)
        # always overwrite
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Written: {relpath}")

def install_deps():
    print("Installing dependencies from requirements.txt …")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    except subprocess.CalledProcessError as e:
        print("Failed to install dependencies:", e)

def main():
    print("==== Full Update / Setup Starting ====")
    write_all_files()
    install_deps()
    print("\n✅ Full update done.")
    print("Run your bot with: python bot/bot.py")
    print("Launch dashboard: streamlit run app/dashboard.py")

if __name__ == "__main__":
    main()

