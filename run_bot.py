
import os
import time
import sqlite3
import logging
from pathlib import Path
import pandas as pd
from bot.broker import Broker
from bot.config_loader import load_config
from bot.notifications import notify_email, notify_telegram

# Paths relative to this file
ROOT = Path(__file__).resolve().parent
STORAGE = ROOT / "storage"
DB_PATH = STORAGE / "journal.db"
KILL_FLAG = STORAGE / "kill.flag"
CONFIG_PATH = ROOT / "config" / "config.yaml"

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
        # Create position table if not exists
        con.execute("""CREATE TABLE IF NOT EXISTS position (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            symbol TEXT,
            side TEXT,
            price REAL,
            qty REAL,
            timestamp TEXT
        )""")

def ema_crossover(df, fast=12, slow=26):
    df["ema_fast"] = df["close"].ewm(span=fast).mean()
    df["ema_slow"] = df["close"].ewm(span=slow).mean()
    df["signal"] = (df["ema_fast"] > df["ema_slow"]).astype(int)
    return df

def calculate_rsi(df, period=14):
    delta = df["close"].diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    df["rsi"] = 100 - (100 / (1 + rs))
    return df

def run_bot():
    last_mtime = None
    cfg = load_config(CONFIG_PATH)
    broker = Broker(exchange_id=cfg.get("exchange_id"), mode=cfg.get("mode"))

    init_db()
    logging.info(f"Bot started in {cfg.get('mode')} on {cfg.get('symbol')}")
    notify_email("Bot Started", str(cfg))
    notify_telegram(f"Bot started: {cfg.get('symbol')} in mode {cfg.get('mode')}")

    # Restore existing open position from DB (if any)
    position = None
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        row = con.execute("SELECT * FROM position WHERE id = 1").fetchone()
        if row:
            position = dict(row)
            logging.info(f"Restored position: {position}")

    while True:
        # Reload config if changed
        try:
            mtime = os.path.getmtime(CONFIG_PATH)
            if last_mtime is None or mtime > last_mtime:
                cfg = load_config(CONFIG_PATH)
                broker = Broker(exchange_id=cfg.get("exchange_id"), mode=cfg.get("mode"))
                logging.info("Config reloaded")
                last_mtime = mtime
        except Exception as e:
            logging.error(f"Config reload error: {e}")

        # Check for kill flag
        if KILL_FLAG.exists():
            logging.info("Kill flag detected, exiting.")
            notify_email("Bot Stopped", "Kill flag triggered")
            notify_telegram("Bot stopped")
            break

        try:
            df = broker.fetch_ohlcv(cfg["symbol"], cfg["timeframe"], limit=200)
            df = ema_crossover(df, fast=cfg["risk"]["fast"], slow=cfg["risk"]["slow"])
            df = calculate_rsi(df, period=14)
            last, prev = df.iloc[-1], df.iloc[-2]
            price = float(last["close"])

            stop_loss_pct = cfg["risk"]["stop_loss"]
            take_profit_pct = cfg["risk"]["take_profit"]

            with sqlite3.connect(DB_PATH) as con:
                con.row_factory = sqlite3.Row

                # If there is an open position, manage it
                if position is not None:
                    entry_price = float(position["price"])
                    stop_price = entry_price * (1 - stop_loss_pct)
                    target_price = entry_price * (1 + take_profit_pct)

                    logging.info(f"Monitoring position: entry={entry_price:.2f}, price={price:.2f}, TP={target_price:.2f}, SL={stop_price:.2f}")

                    # Stop-loss condition
                    if price <= stop_price:
                        trade = broker.place_order(cfg["symbol"], "sell", cfg["trade_qty"], price)
                        trade["pnl"] = price - entry_price
                        pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                        con.execute("DELETE FROM position WHERE id = 1")
                        logging.warning(f"STOP LOSS triggered at {price:.2f}, entry was {entry_price:.2f}")
                        notify_email("STOP LOSS", str(trade))
                        notify_telegram(f"STOP LOSS at {price:.2f} (entry {entry_price:.2f})")
                        position = None
                        continue

                    # Take-profit condition
                    if price >= target_price:
                        trade = broker.place_order(cfg["symbol"], "sell", cfg["trade_qty"], price)
                        trade["pnl"] = price - entry_price
                        pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                        con.execute("DELETE FROM position WHERE id = 1")
                        logging.info(f"TAKE PROFIT triggered at {price:.2f}, entry was {entry_price:.2f}")
                        notify_email("TAKE PROFIT", str(trade))
                        notify_telegram(f"TAKE PROFIT at {price:.2f} (entry {entry_price:.2f})")
                        position = None
                        continue

                # Entry condition (buy)
                if prev["signal"] == 0 and last["signal"] == 1 and last["rsi"] < 30 and position is None:
                    trade = broker.place_order(cfg["symbol"], "buy", cfg["trade_qty"], price)
                    trade["pnl"] = 0
                    pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                    con.execute("""INSERT OR REPLACE INTO position
                        (id, symbol, side, price, qty, timestamp)
                        VALUES (1, ?, ?, ?, ?, ?)""",
                        (trade["symbol"], trade["side"], trade["price"], trade["qty"], trade["timestamp"])
                    )
                    position = trade
                    logging.info(f"BUY at {trade['price']} | RSI: {last['rsi']:.2f}")
                    notify_email("Trade BUY", str(trade))
                    notify_telegram(f"BUY {cfg['symbol']} @ {trade['price']:.2f} | RSI: {last['rsi']:.2f}")

                # Exit condition (sell on reverse signal)
                elif prev["signal"] == 1 and last["signal"] == 0 and last["rsi"] > 70 and position is not None:
                    trade = broker.place_order(cfg["symbol"], "sell", cfg["trade_qty"], price)
                    trade["pnl"] = price - float(position["price"])
                    pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                    con.execute("DELETE FROM position WHERE id = 1")
                    logging.info(f"SELL at {trade['price']} | RSI: {last['rsi']:.2f}")
                    notify_email("Trade SELL", str(trade))
                    notify_telegram(f"SELL {cfg['symbol']} @ {trade['price']:.2f} | RSI: {last['rsi']:.2f}")
                    position = None

        except Exception as e:
            logging.error(f"Trading error: {e}")
            notify_email("Bot Error", str(e))
            notify_telegram(f"Error: {e}")

        time.sleep(10)

if __name__ == "__main__":
    run_bot()
