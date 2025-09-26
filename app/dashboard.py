import os
import sys
import json
import yaml
import sqlite3
import requests
import pandas as pd
import streamlit as st
from pathlib import Path

# Internal imports
sys.path.append(str(Path(__file__).resolve().parents[1]))
from bot.config_loader import load_config
from bot.broker import Broker

# Paths
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
DB_PATH = Path(__file__).resolve().parents[1] / "storage" / "journal.db"
KILL_FLAG = Path(__file__).resolve().parents[1] / "storage" / "kill.flag"


# -------------------- Main --------------------
def main():
    st.set_page_config(page_title="Crypto Bot Dashboard", layout="wide")
    st.title("📈 Crypto Trading Bot Dashboard")

    init_db()
    cfg = load_config()
    st.sidebar.header("Settings & Options")

    # Fetch trading pairs
    products = fetch_products()
    default = cfg.get("symbol", "")
    if default and default not in products:
        products.append(default)
    products = sorted(products)

    symbol_index = products.index(default) if default in products else 0
    symbol = st.sidebar.selectbox("Trading Pair", options=products or ["BTC-USD"], index=symbol_index)

    timeframe_options = ["1m", "5m", "15m", "1h", "4h", "1d"]
    default_tf = cfg.get("timeframe", "1h")
    tf_index = timeframe_options.index(default_tf) if default_tf in timeframe_options else 3
    timeframe = st.sidebar.selectbox("Timeframe", timeframe_options, index=tf_index)

    ema_fast = st.sidebar.number_input("EMA Fast", min_value=1, value=cfg.get("risk", {}).get("fast", 12))
    ema_slow = st.sidebar.number_input("EMA Slow", min_value=1, value=cfg.get("risk", {}).get("slow", 26))

    if st.sidebar.button("💾 Save & Apply"):
        new_cfg = cfg.copy()
        new_cfg["symbol"] = symbol
        new_cfg["timeframe"] = timeframe
        new_cfg.setdefault("risk", {})["fast"] = ema_fast
        new_cfg.setdefault("risk", {})["slow"] = ema_slow
        write_config(new_cfg)
        st.sidebar.success("✅ Configuration saved!")

    tab1, tab2, tab3 = st.tabs(["Chart", "Trades", "Controls"])

    # --- Tab 1: Chart ---
    with tab1:
        trades = read_trades(symbol=symbol)
        try:
            broker = Broker(exchange_id=cfg.get("exchange_id"), mode=cfg.get("mode"))
            df = broker.fetch_ohlcv(symbol, timeframe, limit=200)
            df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
            df = df.dropna(subset=["timestamp"]).set_index("timestamp")
        except Exception as e:
            st.error(f"Price fetch failed: {e}")
            df = pd.DataFrame()

        if not df.empty:
            fig = plot_candles_ema(df, trades, ema_fast, ema_slow)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No price data available.")

    # --- Tab 2: Trades ---
    with tab2:
        trades = read_trades(symbol=symbol)
        if trades.empty:
            st.info("No trades recorded.")
        else:
            st.dataframe(trades)

    # --- Tab 3: Controls ---
    with tab3:
        st.subheader("⚙️ Bot Controls & Configuration")

        with st.form("config_form"):
            # General
            st.markdown("### General Settings")
            mode = st.selectbox("Mode", ["paper", "live"], index=["paper", "live"].index(cfg.get("mode", "paper")))
            trade_qty = st.number_input("Trade Quantity", min_value=0.0001, value=float(cfg.get("trade_qty", 0.001)), format="%.6f")

            # Risk
            st.markdown("### Risk Management")
            risk = cfg.get("risk", {})
            risk_per_trade = st.slider("Risk per Trade (%)", 0.001, 0.05, float(risk.get("risk_per_trade", 0.005)))
            stop_loss = st.slider("Stop Loss (%)", 0.005, 0.1, float(risk.get("stop_loss", 0.02)))
            take_profit = st.slider("Take Profit (%)", 0.01, 0.2, float(risk.get("take_profit", 0.04)))

            # Limits
            st.markdown("### Limits")
            limits = cfg.get("limits", {})
            max_daily_dd = st.slider("Max Daily Drawdown (%)", 0.01, 0.2, float(limits.get("max_daily_dd", 0.02)))
            max_session_dd = st.slider("Max Session Drawdown (%)", 0.01, 0.2, float(limits.get("max_session_dd", 0.05)))
            max_open_trades = st.number_input("Max Open Trades", min_value=1, max_value=10, value=int(limits.get("max_open_trades", 1)))

            # Auto Trading
            st.markdown("### Auto Trading")
            auto = cfg.get("auto", {})
            auto_enabled = st.checkbox("Enable Auto Mode", value=auto.get("enabled", False))
            interval_min = st.number_input("Interval (minutes)", min_value=1, value=int(auto.get("interval_min", 60)))
            run_minutes = st.number_input("Run Duration (minutes)", min_value=1, value=int(auto.get("run_minutes", 10)))

            # Notifications (Email & Telegram)
            st.markdown("### Notifications")

            email_cfg = cfg.get("notifications", {}).get("email", {})
            email_enabled = st.checkbox("Enable Email Alerts", value=email_cfg.get("enabled", False))
            smtp_server = st.text_input("SMTP Server", value=email_cfg.get("smtp_server", ""))
            smtp_port = st.number_input("SMTP Port", value=email_cfg.get("smtp_port", 587))
            sender = st.text_input("Sender Email", value=email_cfg.get("sender", ""))
            password = st.text_input("Email Password", value=email_cfg.get("password", ""), type="password")
            recipients = st.text_area("Recipient Emails (comma-separated)", value=",".join(email_cfg.get("recipients", [])))

            tg_cfg = cfg.get("notifications", {}).get("telegram", {})
            tg_enabled = st.checkbox("Enable Telegram Alerts", value=tg_cfg.get("enabled", False))
            bot_token = st.text_input("Bot Token", value=tg_cfg.get("bot_token", ""))
            chat_id = st.text_input("Chat ID", value=tg_cfg.get("chat_id", ""))

            submitted = st.form_submit_button("💾 Save Configuration")
            if submitted:
                new_cfg = cfg.copy()
                new_cfg.update({
                    "mode": mode,
                    "trade_qty": trade_qty,
                    "risk": {
                        "risk_per_trade": risk_per_trade,
                        "stop_loss": stop_loss,
                        "take_profit": take_profit,
                        "fast": ema_fast,
                        "slow": ema_slow,
                    },
                    "limits": {
                        "max_daily_dd": max_daily_dd,
                        "max_session_dd": max_session_dd,
                        "max_open_trades": max_open_trades
                    },
                    "auto": {
                        "enabled": auto_enabled,
                        "interval_min": interval_min,
                        "run_minutes": run_minutes,
                        "last_auto_start": auto.get("last_auto_start", None)
                    },
                    "notifications": {
                        "email": {
                            "enabled": email_enabled,
                            "smtp_server": smtp_server,
                            "smtp_port": smtp_port,
                            "sender": sender,
                            "password": password,
                            "recipients": [r.strip() for r in recipients.split(",") if r.strip()]
                        },
                        "telegram": {
                            "enabled": tg_enabled,
                            "bot_token": bot_token,
                            "chat_id": chat_id
                        }
                    }
                })
                write_config(new_cfg)
                st.success("✅ Configuration saved!")

        c1, c2 = st.columns(2)
        if c1.button("▶️ Start Bot"):
            KILL_FLAG.unlink(missing_ok=True)
            st.success("Bot start flagged")
        if c2.button("⏹ Stop Bot"):
            KILL_FLAG.write_text("stop")
            st.warning("Bot stop flagged")

        st.subheader("Available Coinbase Products")
        st.write(products or ["No products available"])


# -------------------- Utility Functions --------------------
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
