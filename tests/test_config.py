import json
import os
import pytest
from pathlib import Path


def test_resolve_db_path_env_var_takes_priority(tmp_path, monkeypatch):
    from ti.config import resolve_db_path

    db_file = tmp_path / "custom.db"
    db_file.touch()
    monkeypatch.setenv("TI_DB_PATH", str(db_file))
    assert resolve_db_path() == db_file


def test_resolve_db_path_config_second(tmp_path, monkeypatch):
    from ti.config import resolve_db_path, _config_path

    monkeypatch.delenv("TI_DB_PATH", raising=False)
    db_file = tmp_path / "from-config.db"
    db_file.touch()
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_file = config_dir / "config.json"
    config_file.write_text(json.dumps({"db_path": str(db_file)}))
    monkeypatch.setattr("ti.config._config_path", lambda: config_file)
    assert resolve_db_path() == db_file


def test_resolve_db_path_xdg_fallback(tmp_path, monkeypatch):
    from ti.config import resolve_db_path

    monkeypatch.delenv("TI_DB_PATH", raising=False)
    monkeypatch.setattr("ti.config._config_path", lambda: tmp_path / "no-config.json")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    result = resolve_db_path()
    assert result == tmp_path / "xdg" / "ti" / "ti.db"


def test_resolve_db_path_no_cwd_fallback(tmp_path, monkeypatch):
    from ti.config import resolve_db_path

    monkeypatch.delenv("TI_DB_PATH", raising=False)
    monkeypatch.setattr("ti.config._config_path", lambda: tmp_path / "no-config.json")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "ti.db").touch()
    result = resolve_db_path()
    assert result == tmp_path / "xdg" / "ti" / "ti.db"


def test_load_config_defaults(tmp_path, monkeypatch):
    from ti.config import load_config

    monkeypatch.setattr("ti.config._config_path", lambda: tmp_path / "nope.json")
    cfg = load_config()
    assert cfg["mode"] == "local"
    assert cfg["api_url"] == ""
    assert cfg["api_key"] == ""
    assert cfg["db_path"] is None


def test_save_and_load_config(tmp_path, monkeypatch):
    from ti.config import load_config, save_config

    config_file = tmp_path / "config.json"
    monkeypatch.setattr("ti.config._config_path", lambda: config_file)
    save_config(
        {
            "mode": "remote",
            "api_url": "https://x.com",
            "api_key": "sk-abc",
            "db_path": None,
        }
    )
    cfg = load_config()
    assert cfg["mode"] == "remote"
    assert cfg["api_url"] == "https://x.com"


def test_config_file_permissions(tmp_path, monkeypatch):
    from ti.config import save_config

    config_file = tmp_path / "config.json"
    monkeypatch.setattr("ti.config._config_path", lambda: config_file)
    save_config({"mode": "local", "api_url": "", "api_key": "", "db_path": None})
    assert oct(config_file.stat().st_mode & 0o777) == "0o600"


def test_mask_api_key():
    from ti.config import mask_api_key

    assert mask_api_key("sk-abcdefghijklmnopqrstuvwxyz123456") == "****3456"
    assert mask_api_key("") == ""
    assert mask_api_key("short") == "****hort"
