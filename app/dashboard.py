import os
import sqlite3
import pandas as pd
import streamlit as st
import yaml
import requests
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
from bot.config_loader import load_config
from bot.broker import Broker

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
DB_PATH = Path(__file__).resolve().parents[1] / "storage" / "journal.db"
KILL_FLAG = Path(__file__).resolve().parents[1] / "storage" / "kill.flag"

# --------------------------- DATABASE ---------------------------
def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                symbol TEXT,
                side TEXT,
                price REAL,
                qty REAL,
                fee REAL,
                pnl REAL
            )
        """)

def read_trades(symbol=None):
    if not DB_PATH.exists():
        return pd.DataFrame()

    with sqlite3.connect(DB_PATH) as con:
        query = "SELECT * FROM trades"
        if symbol:
            query += " WHERE symbol = ? ORDER BY timestamp DESC"
            df = pd.read_sql(query, con, params=(symbol,))
        else:
            query += " ORDER BY timestamp DESC"
            df = pd.read_sql(query, con)

    if not df.empty and "timestamp" in df.columns:
        def clean_timestamp(ts):
            try:
                ts = str(ts).replace("EDT", "").replace("UTC", "").strip()
                return pd.to_datetime(ts, utc=True, errors='coerce')
            except Exception:
                return pd.NaT

        df["timestamp"] = df["timestamp"].apply(clean_timestamp)
        df = df.dropna(subset=["timestamp"])

    return df

# --------------------------- API ---------------------------
def fetch_products():
    try:
        resp = requests.get("https://api.coinbase.com/api/v3/brokerage/products", timeout=5)
        resp.raise_for_status()
        return sorted([p.get("product_id") for p in resp.json().get("products", []) if p.get("product_id")])
    except Exception as e:
        st.warning(f"Could not fetch products: {e}")
        return []

# --------------------------- CHART ---------------------------
def plot_candles_ema(df, trades, ema_fast, ema_slow):
    import plotly.graph_objects as go
    df["ema_fast"] = df["close"].ewm(span=ema_fast).mean()
    df["ema_slow"] = df["close"].ewm(span=ema_slow).mean()

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"], high=df["high"], low=df["low"], close=df["close"], name="Price"
    ))
    fig.add_trace(go.Scatter(x=df.index, y=df["ema_fast"], mode="lines", name=f"EMA {ema_fast}"))
    fig.add_trace(go.Scatter(x=df.index, y=df["ema_slow"], mode="lines", name=f"EMA {ema_slow}"))

    if trades is not None and not trades.empty:
        buys = trades[trades["side"].str.lower() == "buy"]
        sells = trades[trades["side"].str.lower() == "sell"]
        fig.add_trace(go.Scatter(x=buys["timestamp"], y=buys["price"], mode="markers", name="Buys",
                                 marker=dict(symbol="triangle-up", color="green", size=10)))
        fig.add_trace(go.Scatter(x=sells["timestamp"], y=sells["price"], mode="markers", name="Sells",
                                 marker=dict(symbol="triangle-down", color="red", size=10)))

    fig.update_layout(xaxis_rangeslider_visible=False, template="plotly_dark", height=600)
    return fig

# --------------------------- CONFIG ---------------------------
def write_config(cfg: dict):
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(cfg, f)

# --------------------------- MAIN ---------------------------
def main():
    st.set_page_config(page_title="📊 Crypto Bot Dashboard", layout="wide")
    st.title("📈 Crypto Trading Bot Dashboard")

    init_db()
    cfg = load_config()
    products = fetch_products()

    # Sidebar Settings
    st.sidebar.header("⚙️ Configuration")
    symbol = st.sidebar.selectbox("Trading Pair", options=products or [cfg.get("symbol")], index=0)
    timeframe = st.sidebar.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"],
                                      index=["1m", "5m", "15m", "1h", "4h", "1d"].index(cfg.get("timeframe", "1h")))
    ema_fast = st.sidebar.number_input("EMA Fast", min_value=1, value=cfg.get("risk", {}).get("fast", 12))
    ema_slow = st.sidebar.number_input("EMA Slow", min_value=1, value=cfg.get("risk", {}).get("slow", 26))

    if st.sidebar.button("💾 Save & Apply"):
        cfg["symbol"] = symbol
        cfg["timeframe"] = timeframe
        cfg.setdefault("risk", {})["fast"] = ema_fast
        cfg.setdefault("risk", {})["slow"] = ema_slow
        write_config(cfg)
        st.sidebar.success("Configuration saved!")

    # Tabs
    tab1, tab2, tab3 = st.tabs(["📊 Chart", "📒 Trades", "🛠 Controls"])

    with tab1:
        try:
            broker = Broker(exchange_id=cfg["exchange_id"], mode=cfg["mode"])
            df = broker.fetch_ohlcv(symbol, timeframe, limit=200)
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors='coerce')
            df = df.dropna(subset=["timestamp"]).set_index("timestamp")
            trades = read_trades(symbol=symbol)
            st.plotly_chart(plot_candles_ema(df, trades, ema_fast, ema_slow), use_container_width=True)
        except Exception as e:
            st.error(f"Chart loading failed: {e}")

    with tab2:
        trades = read_trades(symbol=symbol)
        if trades.empty:
            st.info("No trades found.")
        else:
            st.dataframe(trades)

    with tab3:
        st.subheader("🤖 Bot Controls & Configuration")

        # Editable config form
        with st.form("bot_config_form"):
            mode = st.selectbox("Mode", options=["paper", "live"], index=["paper", "live"].index(cfg.get("mode", "paper")))
            symbol_cfg = st.text_input("Symbol", value=cfg.get("symbol", "BTC/USDT"))
            trade_qty = st.number_input("Trade Quantity", min_value=0.0001, value=cfg.get("trade_qty", 0.001), format="%.6f")

            # Add more editable fields here if needed...

            submitted = st.form_submit_button("💾 Save Configuration")
            if submitted:
                cfg["mode"] = mode
                cfg["symbol"] = symbol_cfg
                cfg["trade_qty"] = trade_qty
                write_config(cfg)
                st.success("Configuration saved!")

        st.markdown("---")

        # Bot control buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("▶️ Start Bot"):
                if KILL_FLAG.exists():
                    KILL_FLAG.unlink()
                st.success("Bot start flagged")
        with col2:
            if st.button("⏹ Stop Bot"):
                KILL_FLAG.write_text("stop")
                st.warning("Bot stop flagged")

        st.markdown("---")

        # Collapsible full config JSON view
        with st.expander("View Full Configuration JSON"):
            st.json(cfg)

        st.markdown("---")

        st.subheader("📦 Available Coinbase Products")
        if products:
            st.write(products)
        else:
            st.info("No products available. Check your API token or network connection.")

if __name__ == "__main__":
    main()
