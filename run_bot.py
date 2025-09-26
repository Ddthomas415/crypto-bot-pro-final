import os
import time
import sqlite3
import logging
from pathlib import Path
import pandas as pd
from bot.broker import Broker
from bot.config_loader import load_config

STORAGE = Path(__file__).resolve().parents[1] / "storage"
DB_PATH = STORAGE / "journal.db"
KILL_FLAG = STORAGE / "kill.flag"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "config.yaml"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def init_db():
    STORAGE.mkdir(parents=True, exist_ok=True)  # create storage folder if needed
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
    cfg = load_config()
    broker = Broker(exchange_id=cfg.get("exchange_id"), mode=cfg.get("mode"))
    position = None

    init_db()
    logging.info(f"Bot started in {cfg.get('mode')} on {cfg.get('symbol')}")
    while True:
        if KILL_FLAG.exists():
            logging.info("Kill flag detected. Exiting.")
            break
        try:
            cfg = load_config()
            df = broker.fetch_ohlcv(cfg.get("symbol"), cfg.get("timeframe"), limit=200)
            df = ema_crossover(df, fast=cfg["risk"]["fast"], slow=cfg["risk"]["slow"])
            last, prev = df.iloc[-1], df.iloc[-2]
            price = float(last["close"])

            stop_loss_pct = cfg["risk"]["stop_loss"]
            take_profit_pct = cfg["risk"]["take_profit"]

            with sqlite3.connect(DB_PATH) as con:
                if position is not None:
                    entry_price = float(position["price"])
                    stop_price = entry_price * (1 - stop_loss_pct)
                    target_price = entry_price * (1 + take_profit_pct)

                    if price <= stop_price:
                        trade = broker.place_order(cfg["symbol"], "sell", cfg["trade_qty"], price)
                        trade["pnl"] = price - entry_price
                        pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                        logging.warning(f"STOP LOSS triggered at {price}, entry was {entry_price}")
                        position = None
                        continue

                    if price >= target_price:
                        trade = broker.place_order(cfg["symbol"], "sell", cfg["trade_qty"], price)
                        trade["pnl"] = price - entry_price
                        pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                        logging.info(f"TAKE PROFIT triggered at {price}, entry was {entry_price}")
                        position = None
                        continue

                if prev["signal"] == 0 and last["signal"] == 1 and position is None:
                    trade = broker.place_order(cfg["symbol"], "buy", cfg["trade_qty"], price)
                    trade["pnl"] = 0
                    pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                    logging.info(f"BUY at {price}")
                    position = trade

                elif prev["signal"] == 1 and last["signal"] == 0 and position is not None:
                    trade = broker.place_order(cfg["symbol"], "sell", cfg["trade_qty"], price)
                    trade["pnl"] = price - float(position["price"])
                    pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                    logging.info(f"SELL at {price}")
                    position = None

        except Exception as e:
            logging.error(f"Trading error: {e}")
        time.sleep(10)
