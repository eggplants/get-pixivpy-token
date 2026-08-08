from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import pyotp
import pytest

import gppt
from gppt import api, config, token
from gppt.browser import Authorization, LoginError

if TYPE_CHECKING:
    from pathlib import Path


def _token(access_token: str = "at", *, seconds: int = 3600) -> token.Token:
    return token.Token(
        access_token=access_token,
        refresh_token="rt",
        expires_in=seconds,
        expires_at=(datetime.now(tz=timezone.utc) + timedelta(seconds=seconds)).isoformat(),
        user_name="Me",
        user_account="me",
    )


@pytest.fixture
def config_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.delenv(config.USERNAME_ENV, raising=False)
    monkeypatch.delenv(config.PASSWORD_ENV, raising=False)
    monkeypatch.delenv(config.TOTP_SECRET_ENV, raising=False)
    return tmp_path


@pytest.fixture
def no_browser(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_fetch(username: str, password: str, *, headless: bool, totp: Any = None) -> Authorization:
        calls.append({"username": username, "password": password, "headless": headless, "totp": totp})
        return Authorization(code="the-code", code_verifier="the-verifier")

    monkeypatch.setattr(api, "fetch_authorization", fake_fetch)
    monkeypatch.setattr(api, "is_chromium_installed", lambda: True)
    monkeypatch.setattr(token, "exchange", lambda _: _token())
    return calls


def test_the_public_surface_is_importable() -> None:
    assert gppt.login is api.login
    assert gppt.refresh is api.refresh
    assert gppt.get_token is api.get_token
    assert gppt.Token is token.Token
    assert issubclass(gppt.TokenError, RuntimeError)
    assert issubclass(gppt.LoginError, RuntimeError)


def test_login_returns_a_token_without_touching_disk(
    config_dir: Path,
    no_browser: list[dict[str, Any]],
) -> None:
    issued = gppt.login("me", "pw")

    assert issued.access_token == "at"
    assert no_browser[0]["username"] == "me"
    assert no_browser[0]["password"] == "pw"
    assert no_browser[0]["headless"] is True
    assert list(config_dir.iterdir()) == []


def test_login_without_credentials_shows_a_window(no_browser: list[dict[str, Any]]) -> None:
    gppt.login()

    assert no_browser[0]["headless"] is False


def test_login_honours_an_explicit_headless_false(no_browser: list[dict[str, Any]]) -> None:
    gppt.login("me", "pw", headless=False)

    assert no_browser[0]["headless"] is False


def test_login_rejects_headless_without_credentials(no_browser: list[dict[str, Any]]) -> None:
    with pytest.raises(ValueError, match="needs both a username and a password"):
        gppt.login(headless=True)

    assert no_browser == []


def test_login_resolves_op_references(
    monkeypatch: pytest.MonkeyPatch,
    no_browser: list[dict[str, Any]],
) -> None:
    monkeypatch.setattr(api, "resolve_secret", lambda value: f"resolved:{value}" if value else value)

    gppt.login("op://v/i/user", "op://v/i/pass")

    assert no_browser[0]["username"] == "resolved:op://v/i/user"
    assert no_browser[0]["password"] == "resolved:op://v/i/pass"


def test_refresh_delegates_to_the_token_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(token, "refresh", lambda rt: _token(f"refreshed:{rt}"))

    assert gppt.refresh("rt").access_token == "refreshed:rt"


def test_get_token_logs_in_and_caches(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
) -> None:
    config.save("work", config.ProfileConfig(username="me", password="pw"))

    issued = gppt.get_token("work")

    assert issued.access_token == "at"
    assert len(no_browser) == 1
    assert token.load("work") == issued


def test_get_token_reuses_the_cache(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
) -> None:
    token.save("work", _token("cached"))

    assert gppt.get_token("work").access_token == "cached"
    assert no_browser == []


def test_get_token_can_skip_saving(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],  # noqa: ARG001
) -> None:
    gppt.get_token("work", save=False)

    assert token.load("work") is None


def test_get_token_is_silent_by_default(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],  # noqa: ARG001
    capsys: pytest.CaptureFixture[str],
) -> None:
    gppt.get_token("work")

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_get_token_reports_progress_when_asked(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],  # noqa: ARG001
) -> None:
    messages: list[str] = []

    gppt.get_token("work", notify=messages.append)

    assert "Opening browser for pixiv login ..." in messages


def test_get_token_propagates_a_login_failure(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],  # noqa: ARG001
) -> None:
    def fail(*_: Any, **__: Any) -> Authorization:
        msg = "boom"
        raise LoginError(msg)

    monkeypatch.setattr(api, "fetch_authorization", fail)

    with pytest.raises(LoginError, match="boom"):
        gppt.get_token("work")


def test_login_passes_the_totp_secret_to_the_browser(no_browser: list[dict[str, Any]]) -> None:
    gppt.login("me", "pw", "JBSWY3DPEHPK3PXP")

    assert no_browser[0]["totp"].code() == pyotp.TOTP("JBSWY3DPEHPK3PXP").now()


def test_login_rejects_a_malformed_totp_secret_before_opening_a_browser(
    no_browser: list[dict[str, Any]],
) -> None:
    with pytest.raises(ValueError, match="not valid base32"):
        gppt.login("me", "pw", "not base32!")

    assert no_browser == []


def test_login_wires_up_the_totp_prompt(no_browser: list[dict[str, Any]]) -> None:
    gppt.login("me", "pw", totp_prompt=lambda: "654321")

    assert no_browser[0]["totp"].code() == "654321"


def test_get_token_uses_the_profiles_totp_secret(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
) -> None:
    config.save(
        "work",
        config.ProfileConfig(username="me", password="pw", totp_secret="JBSWY3DPEHPK3PXP"),
    )

    gppt.get_token("work")

    assert no_browser[0]["totp"].code() == pyotp.TOTP("JBSWY3DPEHPK3PXP").now()


def test_get_token_prefers_the_totp_environment_variable(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
) -> None:
    config.save("work", config.ProfileConfig(username="me", password="pw", totp_secret="AAAAAAAAAAAAAAAA"))
    monkeypatch.setenv(config.TOTP_SECRET_ENV, "JBSWY3DPEHPK3PXP")

    gppt.get_token("work")

    assert no_browser[0]["totp"].code() == pyotp.TOTP("JBSWY3DPEHPK3PXP").now()


def test_get_token_falls_back_to_the_totp_prompt(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
) -> None:
    config.save("work", config.ProfileConfig(username="me", password="pw"))

    gppt.get_token("work", totp_prompt=lambda: "654321")

    assert no_browser[0]["totp"].code() == "654321"
