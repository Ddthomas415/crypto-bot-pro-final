#!/usr/bin/env bash
set -euo pipefail

PROJECT_NAME="crypto-bot-pro-final"
ROOT="$HOME/$PROJECT_NAME"

echo "📁 Creating $ROOT"
mkdir -p "$ROOT"/{app,bot,scripts,storage}

cd "$ROOT"

# -----------------------------
# .dockerignore
# -----------------------------
cat > .dockerignore <<'EOF'
.git
__pycache__/
*.pyc
storage/*.db
storage/*.log
.env
EOF

# -----------------------------
# .env.example
# -----------------------------
cat > .env.example <<'EOF'
# Copy this to .env and fill in your keys (or use Keychain on macOS via make setup)
EXCHANGE_API_KEY=
EXCHANGE_API_SECRET=
TRADING_MODE=paper
EXCHANGE_ID=coinbasepro
SYMBOL=BTC/USDT
TIMEFRAME=1h
TRADE_QTY=0.001
EOF

# -----------------------------
# requirements.txt  (no TA-Lib / no pandas-ta to avoid build pain)
# -----------------------------
cat > requirements.txt <<'EOF'
pandas==2.2.2
numpy<2.0
streamlit==1.38.0
scipy==1.14.1
scikit-learn==1.5.1
matplotlib==3.9.2
altair==5.4.1
requests==2.32.3
protobuf==4.25.3
python-binance==1.0.19
ccxt==4.3.88

# Dev
jupyter==1.0.0
notebook==7.2.2
ipykernel==6.29.5
EOF

# -----------------------------
# Dockerfile (simple, stable)
# -----------------------------
cat > Dockerfile <<'EOF'
FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    libffi-dev \
    libssl-dev \
 && rm -rf /var/lib/apt/lists/*

# Copy reqs and install
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "numpy<2.0" \
 && pip install --no-cache-dir -r requirements.txt

# App
COPY . .

EXPOSE 8501 8888
CMD ["streamlit", "run", "app/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
EOF

# -----------------------------
# docker-compose.yml
# -----------------------------
cat > docker-compose.yml <<'EOF'
services:
  crypto-bot:
    build: .
    container_name: crypto-bot
    working_dir: /app
    ports:
      - "8501:8501"   # Streamlit
      - "8888:8888"   # Jupyter (optional)
    volumes:
      - .:/app
    env_file:
      - .env
    environment:
      - EXCHANGE_API_KEY=${EXCHANGE_API_KEY}
      - EXCHANGE_API_SECRET=${EXCHANGE_API_SECRET}
    command: >
      bash -c "
        if [ -f ./start.sh ]; then chmod +x ./start.sh && ./start.sh;
        else streamlit run app/dashboard.py --server.port=8501 --server.address=0.0.0.0; fi
      "
EOF

# -----------------------------
# start.sh
# -----------------------------
cat > start.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
# Launch Streamlit (can add Jupyter if you want)
exec streamlit run app/dashboard.py --server.port=8501 --server.address=0.0.0.0
EOF
chmod +x start.sh

# -----------------------------
# Makefile
# -----------------------------
cat > Makefile <<'EOF'
.PHONY: setup check build run bot jupyter dev logs clean stop shell ps restart rebuild update status reset-all help

setup:
	./scripts/setup_api_keys.sh

check:
	./scripts/check_api_keys.sh

build:
	./scripts/keychain_env.sh docker compose build --no-cache

run:
	./scripts/keychain_env.sh docker compose up -d

bot:
	./scripts/keychain_env.sh docker compose run -d --service-ports crypto-bot \
		streamlit run app/dashboard.py --server.port=8501 --server.address=0.0.0.0

jupyter:
	./scripts/keychain_env.sh docker compose run -d --service-ports crypto-bot \
		jupyter notebook --ip=0.0.0.0 --port=8888 --no-browser --allow-root

dev:
	./scripts/keychain_env.sh docker compose run --service-ports --rm crypto-bot \
		streamlit run app/dashboard.py --server.port=8501 --server.address=0.0.0.0

logs:
	./scripts/keychain_env.sh docker logs -f crypto-bot

clean:
	./scripts/keychain_env.sh docker compose down -v || true

stop:
	./scripts/keychain_env.sh docker compose down || true

shell:
	./scripts/keychain_env.sh docker exec -it crypto-bot bash

ps:
	./scripts/keychain_env.sh docker compose ps

restart: stop run
	@echo "🔄 Restart complete!"

rebuild: clean build run
	@echo "🛠️ Rebuild complete! Fresh containers are up."

update:
	$(MAKE) rebuild

status: check ps
	@echo "📊 Status check complete."

reset-all:
	-security delete-generic-password -a "default" -s "crypto-bot-exchange-key" || true
	-security delete-generic-password -a "default" -s "crypto-bot-exchange-secret" || true
	./scripts/keychain_env.sh docker compose down -v || true
	@echo "💣 Full reset complete. Run 'make setup' to add API keys again."

help:
	@echo "Available targets: setup check build run bot jupyter dev logs clean stop shell ps restart rebuild update status reset-all help"
EOF

# -----------------------------
# scripts/setup_api_keys.sh (macOS keychain helper with .env fallback)
# -----------------------------
mkdir -p scripts
cat > scripts/setup_api_keys.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ "$OSTYPE" == "darwin"* ]]; then
  read -p "Exchange API KEY: " EXCHANGE_API_KEY
  read -p "Exchange API SECRET: " EXCHANGE_API_SECRET

  security add-generic-password -a "default" -s "crypto-bot-exchange-key" -U -w "$EXCHANGE_API_KEY"
  security add-generic-password -a "default" -s "crypto-bot-exchange-secret" -U -w "$EXCHANGE_API_SECRET"
  echo "✅ Keys saved to macOS Keychain."

  # Also write a local .env for Docker Compose
  echo "EXCHANGE_API_KEY=$EXCHANGE_API_KEY" > .env
  echo "EXCHANGE_API_SECRET=$EXCHANGE_API_SECRET" >> .env
  echo "TRADING_MODE=paper" >> .env
  echo "EXCHANGE_ID=coinbasepro" >> .env
  echo "SYMBOL=BTC/USDT" >> .env
  echo "TIMEFRAME=1h" >> .env
  echo "TRADE_QTY=0.001" >> .env
  echo "✅ .env created."
else
  echo "Non-macOS: creating .env"
  read -p "Exchange API KEY: " EXCHANGE_API_KEY
  read -p "Exchange API SECRET: " EXCHANGE_API_SECRET
  echo "EXCHANGE_API_KEY=$EXCHANGE_API_KEY" > .env
  echo "EXCHANGE_API_SECRET=$EXCHANGE_API_SECRET" >> .env
  echo "TRADING_MODE=paper" >> .env
  echo "EXCHANGE_ID=coinbasepro" >> .env
  echo "SYMBOL=BTC/USDT" >> .env
  echo "TIMEFRAME=1h" >> .env
  echo "TRADE_QTY=0.001" >> .env
  echo "✅ .env created."
fi
EOF
chmod +x scripts/setup_api_keys.sh

# -----------------------------
# scripts/check_api_keys.sh
# -----------------------------
cat > scripts/check_api_keys.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".env" ]]; then
  if grep -q "EXCHANGE_API_KEY=" .env && grep -q "EXCHANGE_API_SECRET=" .env; then
    echo "✅ .env has API keys."
    exit 0
  fi
fi

if [[ "$OSTYPE" == "darwin"* ]]; then
  if security find-generic-password -a "default" -s "crypto-bot-exchange-key" >/dev/null 2>&1 \
  && security find-generic-password -a "default" -s "crypto-bot-exchange-secret" >/dev/null 2>&1; then
    echo "✅ Keys found in Keychain."
    exit 0
  fi
fi

echo "❌ Missing API keys. Run: make setup"
exit 1
EOF
chmod +x scripts/check_api_keys.sh

# -----------------------------
# scripts/keychain_env.sh
# -----------------------------
cat > scripts/keychain_env.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ -f ".env" ]]; then
  export $(grep -v '^#' .env | xargs || true)
fi

if [[ "$OSTYPE" == "darwin"* ]]; then
  KEY=$(security find-generic-password -a "default" -s "crypto-bot-exchange-key" -w 2>/dev/null || true)
  SEC=$(security find-generic-password -a "default" -s "crypto-bot-exchange-secret" -w 2>/dev/null || true)
  if [[ -n "${KEY:-}" && -n "${SEC:-}" ]]; then
    export EXCHANGE_API_KEY="$KEY"
    export EXCHANGE_API_SECRET="$SEC"
    # Refresh .env each time
    {
      echo "EXCHANGE_API_KEY=$EXCHANGE_API_KEY"
      echo "EXCHANGE_API_SECRET=$EXCHANGE_API_SECRET"
      echo "TRADING_MODE=${TRADING_MODE:-paper}"
      echo "EXCHANGE_ID=${EXCHANGE_ID:-coinbasepro}"
      echo "SYMBOL=${SYMBOL:-BTC/USDT}"
      echo "TIMEFRAME=${TIMEFRAME:-1h}"
      echo "TRADE_QTY=${TRADE_QTY:-0.001}"
    } > .env
    echo "✅ Keys loaded from Keychain and written to .env"
  fi
fi

# Execute the rest of the command line
exec "$@"
EOF
chmod +x scripts/keychain_env.sh

# -----------------------------
# bot/config_loader.py
# -----------------------------
cat > bot/config_loader.py <<'EOF'
import os, yaml
from pathlib import Path

DEFAULT_CONFIG = {
    "mode": "paper",
    "exchange_id": "coinbasepro",
    "symbol": "BTC/USDT",
    "timeframe": "1h",
    "trade_qty": 0.001,
    "risk": {
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
    }
}

def load_config(config_path=None):
    if config_path is None:
        config_path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    cfg = {}
    if Path(config_path).exists():
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}
    # Env overrides
    env = {
        "mode": os.getenv("TRADING_MODE"),
        "exchange_id": os.getenv("EXCHANGE_ID"),
        "symbol": os.getenv("SYMBOL"),
        "timeframe": os.getenv("TIMEFRAME"),
        "trade_qty": os.getenv("TRADE_QTY"),
    }
    for k, v in env.items():
        if v is None: continue
        cfg[k] = float(v) if k == "trade_qty" else v

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
    return merge(DEFAULT_CONFIG, cfg)
EOF

# -----------------------------
# bot/broker.py (paper + ccxt live)
# -----------------------------
cat > bot/broker.py <<'EOF'
import os, random
from datetime import datetime, timezone
import pandas as pd

try:
    import ccxt
except Exception:
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
        data = self.exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
        df = pd.DataFrame(data, columns=["timestamp","open","high","low","close","volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        return df

    def place_order(self, symbol, side, qty, price=None):
        if self.mode == "paper":
            return {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "symbol": symbol,
                "side": side,
                "price": float(price if price else 30000 + random.uniform(-200, 200)),
                "qty": float(qty),
                "fee": 0.0,
                "pnl": 0.0
            }
        order = self.exchange.create_market_order(symbol, side, qty)
        filled_price = float(price if price else order.get("average") or order.get("price"))
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "symbol": symbol,
            "side": side,
            "price": filled_price,
            "qty": float(qty),
            "fee": 0.0,
            "pnl": 0.0
        }
EOF

# -----------------------------
# bot/bot.py (EMA crossover + SQLite journal)
# -----------------------------
cat > bot/bot.py <<'EOF'
import os, time, sqlite3, logging
from pathlib import Path
import pandas as pd
from datetime import datetime, timezone
from bot.broker import Broker
from bot.config_loader import load_config

STORAGE = Path(__file__).parents[1] / "storage"
DB_PATH = STORAGE / "journal.db"
KILL_FLAG = STORAGE / "kill.flag"
STORAGE.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

def init_db():
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

def ema_crossover(df, fast=12, slow=26):
    df = df.copy()
    df["ema_fast"] = df["close"].ewm(span=fast, adjust=False).mean()
    df["ema_slow"] = df["close"].ewm(span=slow, adjust=False).mean()
    df["signal"] = (df["ema_fast"] > df["ema_slow"]).astype(int)
    return df

def run_bot():
    cfg = load_config()
    mode = cfg["mode"]
    broker = Broker(exchange_id=cfg["exchange_id"], mode=mode)

    init_db()
    position = None
    logging.info(f"Bot started in {mode.upper()} on {cfg['symbol']} ({cfg['timeframe']})")

    while True:
        if KILL_FLAG.exists():
            logging.info("Kill flag detected. Exiting.")
            break
        try:
            df = broker.fetch_ohlcv(cfg["symbol"], cfg["timeframe"], limit=200)
            df = ema_crossover(df)
            last, prev = df.iloc[-1], df.iloc[-2]

            with sqlite3.connect(DB_PATH) as con:
                if prev["signal"] == 0 and last["signal"] == 1 and position is None:
                    trade = broker.place_order(cfg["symbol"], "buy", cfg["trade_qty"], float(last["close"]))
                    trade["pnl"] = 0.0
                    pd.DataFrame([trade]).to_sql("trades", con, if_exists="append", index=False)
                    logging.info(f"BUY {trade['symbol']} at {trade['price']}")
                    position = trade

                elif prev["signal"] == 1 and last["signal"] == 0 and position:
                    exit_trade = broker.place_order(cfg["symbol"], "sell", cfg["trade_qty"], float(last["close"]))
                    pnl = (exit_trade["price"] - position["price"]) * position["qty"]
                    exit_trade["pnl"] = float(pnl)
                    pd.DataFrame([exit_trade]).to_sql("trades", con, if_exists="append", index=False)
                    logging.info(f"SELL {exit_trade['symbol']} at {exit_trade['price']} | PnL: {pnl:.2f}")
                    position = None

        except Exception as e:
            logging.error(f"Error: {e}")

        time.sleep(10)

if __name__ == "__main__":
    run_bot()
EOF

# -----------------------------
# app/dashboard.py (Streamlit UI)
# -----------------------------
cat > app/dashboard.py <<'EOF'
import sqlite3
from pathlib import Path
import pandas as pd
import streamlit as st
from datetime import datetime
from bot.config_loader import load_config

st.set_page_config(page_title="Crypto Bot Dashboard", layout="wide")

STORAGE = Path(__file__).parents[1] / "storage"
DB_PATH = STORAGE / "journal.db"

def read_trades():
    if not DB_PATH.exists():
        return pd.DataFrame(columns=["timestamp","symbol","side","price","qty","fee","pnl"])
    with sqlite3.connect(DB_PATH) as con:
        return pd.read_sql("SELECT * FROM trades ORDER BY id DESC", con)

def compute_equity(trades: pd.DataFrame):
    if trades.empty: 
        return pd.DataFrame()
    trades = trades.copy()
    trades["timestamp"] = pd.to_datetime(trades["timestamp"])
    trades = trades.sort_values("timestamp")
    trades["equity"] = trades["pnl"].fillna(0).cumsum()
    return trades[["timestamp","equity"]]

st.title("🤖 Crypto Bot Pro — Dashboard")

cfg = load_config()
st.sidebar.header("Bot Config")
st.sidebar.write(cfg)

tabs = st.tabs(["Overview", "Live Feed", "Positions & Trades"])

with tabs[0]:
    st.subheader("Overview")
    st.write("Mode:", cfg["mode"])
    st.write("Symbol:", cfg["symbol"])
    st.write("Timeframe:", cfg["timeframe"])

    trades = read_trades()
    eq = compute_equity(trades)
    if not eq.empty:
        st.line_chart(eq.rename(columns={"timestamp":"index"}).set_index("index")["equity"], width="stretch")
    else:
        st.info("No equity yet. Start the bot (paper) to generate trades.")

with tabs[1]:
    st.subheader("Live Feed")
    trades = read_trades()
    c1, c2 = st.columns([2, 1])

    with c1:
        eq = compute_equity(trades)
        if not eq.empty:
            st.line_chart(
                eq.rename(columns={"timestamp": "index"}).set_index("index")["equity"],
                width="stretch"
            )
        else:
            st.info("No equity data yet. Start the bot in Paper mode.")

    with c2:
        st.metric("Trades", len(trades))
        if not trades.empty:
            pnl_total = float(trades["pnl"].fillna(0.0).sum())
            st.metric("Total PnL ($)", f"{pnl_total:,.2f}")
            st.dataframe(trades.head(50), use_container_width=True)

with tabs[2]:
    st.subheader("Positions & Trades")
    trades = read_trades()
    st.dataframe(trades, use_container_width=True)
    st.caption("💡 Bot runs inside the container. Use the Makefile to start/stop.")
EOF

# -----------------------------
# helper optional scripts
# -----------------------------
cat > save_keys.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
./scripts/setup_api_keys.sh
EOF
chmod +x save_keys.sh

cat > install_monitor.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "📝 (Optional) terminal monitor placeholder. Nothing to install."
EOF
chmod +x install_monitor.sh

# touch storage files
touch storage/journal.db

echo "✅ Project files written to $ROOT"

# -----------------------------
# Build & Run
# -----------------------------
echo "📦 Building image..."
docker build --no-cache -t crypto-bot-pro .

echo "🗝️ Setting keys (you can skip and edit .env manually):"
if [ ! -f .env ]; then
  echo "(Tip: you can press Enter and edit .env later)"
fi
make setup || true

echo "▶️ Starting containers..."
make run

echo "🎉 Done! Open http://localhost:8501"

