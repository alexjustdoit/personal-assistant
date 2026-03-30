import yaml
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
EXAMPLE_PATH = Path(__file__).parent.parent / "config.yaml.example"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.yaml not found. Copy config.yaml.example to config.yaml and fill in your values."
        )
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


config = load_config()
