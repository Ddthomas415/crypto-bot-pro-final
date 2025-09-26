# bot/config_loader.py
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
    else:
        config_path = Path(config_path)

    cfg = {}
    if config_path.exists():
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f) or {}
    else:
        print(f"⚠️ Config file not found at {config_path}, using defaults")

    # Override with env vars
    env_overrides = {
        "mode": os.getenv("TRADING_MODE"),
        "exchange_id": os.getenv("EXCHANGE_ID"),
        "symbol": os.getenv("SYMBOL"),
        "timeframe": os.getenv("TIMEFRAME"),
        "trade_qty": os.getenv("TRADE_QTY"),
    }

    for k, v in env_overrides.items():
        if v is not None:
            if k == "trade_qty":
                try:
                    cfg[k] = float(v)
                except ValueError:
                    cfg[k] = v
            else:
                cfg[k] = v

    # Merge defaults with custom config
    def merge(default, custom):
        result = {}
        for key in default:
            if key in custom:
                if isinstance(default[key], dict) and isinstance(custom[key], dict):
                    result[key] = merge(default[key], custom[key])
                else:
                    result[key] = custom[key]
            else:
                result[key] = default[key]
        for key in custom:
            if key not in default:
                result[key] = custom[key]
        return result

    return merge(DEFAULT_CONFIG, cfg)

