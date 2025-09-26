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
        con.execute("""CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,
                price REAL,
                qty REAL,
                fee REAL,
                pnl REAL
            )""")

def read_trades(symbol=None):
    if not DB_PATH.exists():
        return pd.DataFrame()
    with sqlite3.connect(DB_PATH) as con:
        if symbol:
            df = pd.read_sql("SELECT * FROM trades WHERE symbol = ? ORDER BY timestamp DESC", con, params=(symbol,))
        else:
            df = pd.read_sql("SELECT * FROM trades ORDER BY timestamp DESC", con)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df

def write_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(cfg, f)

def fetch_products():
    try:
        resp = requests.get("https://api.coinbase.com/api/v3/brokerage/products", timeout=5)
        resp.raise_for_status()
        arr = resp.json().get("products", [])
        return sorted([p.get("product_id") for p in arr if p.get("product_id")])
    except Exception as e:
        st.warning(f"Could not fetch products: {e}")
        return []

def plot_candles_ema(df, trades, ema_fast, ema_slow):
    import plotly.graph_objects as go
    df["ema_fast"] = df["close"].ewm(span=ema_fast).mean()
    df["ema_slow"] = df["close"].ewm(span=ema_slow).mean()

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="Price"
    ))
    fig.add_trace(go.Scatter(x=df.index, y=df["ema_fast"], mode="lines", name=f"EMA{ema_fast}"))
    fig.add_trace(go.Scatter(x=df.index, y=df["ema_slow"], mode="lines", name=f"EMA{ema_slow}"))

    if trades is not None and not trades.empty:
        buys = trades[trades["side"].str.lower() == "buy"]
        sells = trades[trades["side"].str.lower() == "sell"]
        fig.add_trace(go.Scatter(
            x=buys["timestamp"], y=buys["price"], mode="markers", marker=dict(symbol="triangle-up", color="green", size=10), name="Buys"
        ))
        fig.add_trace(go.Scatter(
            x=sells["timestamp"], y=sells["price"], mode="markers", marker=dict(symbol="triangle-down", color="red", size=10), name="Sells"
        ))
    fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=600)
    return fig

def main():
    st.set_page_config(page_title="Crypto Trading Bot Dashboard", layout="wide")
    st.title("📈 Crypto Trading Bot Dashboard")
    init_db()
    cfg = load_config()

    st.sidebar.header("Settings & Options")
    products = fetch_products()
    default = cfg.get("symbol", "")
    symbol = st.sidebar.selectbox("Trading Pair", options=products or [default], index=products.index(default) if default in products else 0)
    timeframe = st.sidebar.selectbox("Timeframe", ["1m","5m","15m","1h","4h","1d"], index=["1m","5m","15m","1h","4h","1d"].index(cfg.get("timeframe","1h")))
    ema_fast = st.sidebar.number_input("EMA Fast", min_value=1, value=cfg.get("risk", {}).get("fast", 12))
    ema_slow = st.sidebar.number_input("EMA Slow", min_value=1, value=cfg.get("risk", {}).get("slow", 26))

    if st.sidebar.button("💾 Save & Apply"):
        new = cfg.copy()
        new["symbol"] = symbol
        new["timeframe"] = timeframe
        new.setdefault("risk", {})["fast"] = ema_fast
        new.setdefault("risk", {})["slow"] = ema_slow
        write_config(new)
        st.sidebar.success("Configuration saved")

    tab1, tab2, tab3 = st.tabs(["Chart", "Trades", "Controls"])
    with tab1:
        trades = read_trades(symbol=symbol)
        try:
            broker = Broker(exchange_id=cfg.get("exchange_id"), mode=cfg.get("mode"))
            df = broker.fetch_ohlcv(symbol, timeframe, limit=200)
            df["timestamp"] = pd.to_datetime(df["timestamp"])
            df = df.set_index("timestamp")
        except Exception as e:
            st.error(f"Price fetch failed: {e}")
            df = pd.DataFrame()

        if not df.empty:
            fig = plot_candles_ema(df, trades, ema_fast, ema_slow)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No price data")

    with tab2:
        trades = read_trades(symbol=symbol)
        if trades.empty:
            st.info("No trades recorded")
        else:
            st.dataframe(trades)

    with tab3:
        st.subheader("Bot Controls & Config")
        st.json(cfg)
        c1, c2 = st.columns(2)
        if c1.button("▶️ Start Bot"):
            if KILL_FLAG.exists():
                KILL_FLAG.unlink(missing_ok=True)
            st.success("Bot start flagged")
        if c2.button("⏹ Stop Bot"):
            KILL_FLAG.write_text("stop")
            st.warning("Bot stop flagged")

        st.subheader("Available Products")
        st.write(products or [])

if __name__ == "__main__":
    main()
