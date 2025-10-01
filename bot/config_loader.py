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
