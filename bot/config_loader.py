import yaml
from pathlib import Path

def load_config(path=None):
    if path is None:
        path = Path(__file__).resolve().parents[1] / "config" / "config.yaml"
    with open(path, "r") as f:
        return yaml.safe_load(f)
