import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".adwize"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "api_url": "http://localhost:8000",
    "api_key": None,
    "webhook_url": None,
    "project_dir": None,
}


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        return dict(DEFAULTS)

    try:
        with open(CONFIG_FILE) as f:
            saved = json.load(f)
        merged = dict(DEFAULTS)
        merged.update(saved)
        return merged
    except (json.JSONDecodeError, OSError):
        return dict(DEFAULTS)


def save(config: dict[str, Any]) -> Path:
    _ensure_dir()
    clean = {k: v for k, v in config.items() if v is not None}
    with open(CONFIG_FILE, "w") as f:
        json.dump(clean, f, indent=2)
        f.write("\n")
    return CONFIG_FILE


def get(key: str, default: Any = None) -> Any:
    """Read a config value. Env vars take priority over config file."""
    env_map = {
        "api_url": "ADWIZE_API_URL",
        "api_key": "ADWIZE_API_KEY",
        "webhook_url": "WEBHOOK_URL",
    }
    env_key = env_map.get(key)
    if env_key:
        env_val = os.getenv(env_key)
        if env_val:
            return env_val

    config = load()
    return config.get(key, default)
