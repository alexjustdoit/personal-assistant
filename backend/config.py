import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f) or {}


def is_configured() -> bool:
    return CONFIG_PATH.exists()


def save_config():
    """Write the current in-memory config back to config.yaml."""
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)


config = load_config()
