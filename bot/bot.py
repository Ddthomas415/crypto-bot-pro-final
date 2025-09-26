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
    logging.info(f"Bot started in {cfg.get('mode')} on {cfg.get('symbol')}")
    notify_email("Bot Started", str(cfg))
    notify_telegram(f"Bot started: {cfg.get('symbol')}, mode {cfg.get('mode')}")
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
                    logging.info(f"BUY at {trade['price']}")
                    notify_email("Trade BUY", str(trade))
                    notify_telegram(f"BUY {cfg.get('symbol')} @ {trade['price']}")
                    position = trade
                elif prev["signal"] == 1 and last["signal"] == 0 and position is not None:
                    trade = broker.place_order(cfg.get("symbol"), "sell", cfg.get("trade_qty"), float(last["close"]))
                    trade["pnl"] = 0
                    pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                    logging.info(f"SELL at {trade['price']}")
                    notify_email("Trade SELL", str(trade))
                    notify_telegram(f"SELL {cfg.get('symbol')} @ {trade['price']}")
                    position = None
        except Exception as e:
            logging.error(f"Trading error: {e}")
            notify_email("Bot Error", str(e))
            notify_telegram(f"Error: {e}")

        time.sleep(10)

if __name__ == "__main__":
    run_bot()
