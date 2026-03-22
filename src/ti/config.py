"""Configuration management and DB path resolution."""

import json
import os
import stat
from pathlib import Path

_DEFAULTS = {
    "mode": "local",
    "api_url": "",
    "api_key": "",
    "db_path": None,
    "proxy": "system",
}

_VALID_KEYS = set(_DEFAULTS.keys())
_VALID_MODES = {"local", "remote"}
_VALID_PROXY = {"system", "none"}


def _config_path() -> Path:
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        / "ti"
        / "config.json"
    )


def _xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def load_config() -> dict:
    path = _config_path()
    if not path.exists():
        return dict(_DEFAULTS)
    try:
        data = json.loads(path.read_text())
        return {k: data.get(k, v) for k, v in _DEFAULTS.items()}
    except (json.JSONDecodeError, OSError):
        return dict(_DEFAULTS)


def save_config(cfg: dict) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2) + "\n")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def resolve_db_path() -> Path:
    env_path = os.environ.get("TI_DB_PATH")
    if env_path:
        return Path(env_path)
    cfg = load_config()
    if cfg.get("db_path"):
        return Path(cfg["db_path"])
    return _xdg_data_home() / "ti" / "ti.db"


def mask_api_key(key: str) -> str:
    if not key:
        return ""
    return "****" + key[-4:]
