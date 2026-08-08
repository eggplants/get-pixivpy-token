from __future__ import annotations

import json
import stat
from typing import TYPE_CHECKING

import pytest

from gppt import config

if TYPE_CHECKING:
    from pathlib import Path


def _use_tmp_config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    return tmp_path


def test_save_then_load_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_tmp_config_dir(monkeypatch, tmp_path)

    saved = config.ProfileConfig(
        username="me@example.com",
        password="hunter2",
        totp_secret="JBSWY3DPEHPK3PXP",
    )
    path = config.save("work", saved)

    assert path == tmp_path / "work.json"
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "username": "me@example.com",
        "password": "hunter2",
        "totp_secret": "JBSWY3DPEHPK3PXP",
    }
    assert config.load("work") == saved


def test_save_makes_the_file_private(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_tmp_config_dir(monkeypatch, tmp_path)

    path = config.save("work", config.ProfileConfig(password="hunter2"))

    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_load_missing_profile_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_tmp_config_dir(monkeypatch, tmp_path)

    with pytest.raises(FileNotFoundError, match="gppt configure --profile nope"):
        config.load("nope")


def test_from_dict_ignores_unknown_keys() -> None:
    parsed = config.ProfileConfig.from_dict({"username": "me", "legacy_field": 1})

    assert parsed == config.ProfileConfig(username="me")


def test_load_or_default_falls_back_to_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_tmp_config_dir(monkeypatch, tmp_path)
    monkeypatch.delenv(config.USERNAME_ENV, raising=False)
    monkeypatch.delenv(config.PASSWORD_ENV, raising=False)

    assert config.load_or_default("nope") == config.ProfileConfig()


def test_load_or_default_prefers_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_tmp_config_dir(monkeypatch, tmp_path)
    config.save("work", config.ProfileConfig(username="stored", password="stored-pw"))
    monkeypatch.setenv(config.USERNAME_ENV, "from-env")
    monkeypatch.delenv(config.PASSWORD_ENV, raising=False)

    loaded = config.load_or_default("work")

    assert loaded.username == "from-env"
    assert loaded.password == "stored-pw"


def test_token_path_sits_beside_the_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _use_tmp_config_dir(monkeypatch, tmp_path)

    assert config.token_path("work") == tmp_path / "work.token.json"
