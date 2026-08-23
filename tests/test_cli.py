from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

import pytest

from gppt import api, cli, config, token, __version__
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
    monkeypatch.delenv(config.AUTH_METHOD_ENV, raising=False)
    return tmp_path


@pytest.fixture
def no_browser(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace the browser login with a recorder, so no Chromium is launched."""
    calls: list[dict[str, Any]] = []

    def fake_fetch(username: str, password: str, *, headless: bool, totp: Any = None) -> Authorization:
        calls.append({"username": username, "password": password, "headless": headless, "totp": totp})
        return Authorization(code="the-code", code_verifier="the-verifier")

    monkeypatch.setattr(api, "fetch_authorization", fake_fetch)
    monkeypatch.setattr(api, "is_chromium_installed", lambda: True)
    monkeypatch.setattr(token, "exchange", lambda _: _token())
    return calls


@pytest.fixture
def oauth_flow(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replace the paste-the-code flow with a recorder, so nothing reads stdin."""
    calls: list[dict[str, Any]] = []

    def fake_request(**kwargs: Any) -> Authorization:
        calls.append(kwargs)
        return Authorization(code="the-code", code_verifier="the-verifier")

    monkeypatch.setattr(api, "request_authorization", fake_request)
    monkeypatch.setattr(token, "exchange", lambda _: _token())
    return calls


@pytest.fixture
def no_login(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make either login method an immediate test failure."""

    def explode(*_: Any, **__: Any) -> Authorization:
        msg = "should not have logged in"
        raise AssertionError(msg)

    monkeypatch.setattr(api, "fetch_authorization", explode)
    monkeypatch.setattr(api, "request_authorization", explode)


def test_login_runs_the_browser_and_saves_the_token(
    config_dir: Path,
    no_browser: list[dict[str, Any]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    config.save("work", config.ProfileConfig(username="me", password="pw"))

    assert cli.main(["login", "--profile", "work"]) == 0

    assert no_browser[0]["username"] == "me"
    assert no_browser[0]["password"] == "pw"
    assert no_browser[0]["headless"] is True
    assert "access_token: at" in capsys.readouterr().out
    assert (config_dir / "work.token.json").exists()


def test_login_defaults_to_the_default_profile(
    config_dir: Path,
    no_browser: list[dict[str, Any]],  # noqa: ARG001
) -> None:
    assert cli.main(["login"]) == 0

    assert (config_dir / f"{config.DEFAULT_PROFILE}.token.json").exists()


def test_login_without_credentials_forces_a_visible_window(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
) -> None:
    assert cli.main(["login"]) == 0

    assert no_browser[0]["headless"] is False


def test_no_headless_shows_the_window(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
) -> None:
    config.save("work", config.ProfileConfig(username="me", password="pw"))

    assert cli.main(["login", "-p", "work", "--no-headless"]) == 0

    assert no_browser[0]["headless"] is False


def test_login_reuses_a_valid_cached_token(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    token.save("work", _token("cached"))

    assert cli.main(["login", "-p", "work"]) == 0

    assert no_browser == []
    assert "access_token: cached" in capsys.readouterr().out


def test_force_bypasses_the_cache(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
) -> None:
    token.save("work", _token("cached"))

    assert cli.main(["login", "-p", "work", "--force"]) == 0

    assert len(no_browser) == 1


def test_an_expired_token_is_refreshed(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    token.save("work", _token("stale", seconds=-10))
    monkeypatch.setattr(token, "refresh", lambda _: _token("refreshed"))

    assert cli.main(["login", "-p", "work"]) == 0

    assert no_browser == []
    assert "access_token: refreshed" in capsys.readouterr().out


def test_a_failed_refresh_falls_back_to_the_browser(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
) -> None:
    token.save("work", _token("stale", seconds=-10))

    def fail(_: str) -> token.Token:
        msg = "invalid_grant"
        raise token.TokenError(msg)

    monkeypatch.setattr(token, "refresh", fail)

    assert cli.main(["login", "-p", "work"]) == 0

    assert len(no_browser) == 1


def test_json_output(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],  # noqa: ARG001
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["login", "--json"]) == 0

    printed = json.loads(capsys.readouterr().out)
    assert printed["access_token"] == "at"
    assert printed["refresh_token"] == "rt"
    assert printed["expires_in"] == 3600


def test_login_failure_exits_nonzero(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],  # noqa: ARG001
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(*_: Any, **__: Any) -> Authorization:
        msg = "boom"
        raise LoginError(msg)

    monkeypatch.setattr(api, "fetch_authorization", fail)

    assert cli.main(["login"]) == 1
    assert "error: boom" in capsys.readouterr().err


def test_configure_writes_the_profile(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    answers = iter(["e2e", "me@example.com"])
    secrets = iter(["hunter2", "JBSWY3DPEHPK3PXP"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: next(secrets))

    assert cli.main(["configure", "-p", "work"]) == 0

    assert config.load("work") == config.ProfileConfig(
        username="me@example.com",
        password="hunter2",
        totp_secret="JBSWY3DPEHPK3PXP",
    )
    assert str(config_dir / "work.json") in capsys.readouterr().out


def test_configure_keeps_existing_values_on_empty_input(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,  # noqa: ARG001
) -> None:
    stored = config.ProfileConfig(username="old", password="old-pw", totp_secret="old-totp")
    config.save("work", stored)
    answers = iter(["", ""])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: "")

    assert cli.main(["configure", "-p", "work"]) == 0

    assert config.load("work") == stored


@pytest.mark.parametrize("flag", ["-V", "--version"])
def test_version_flag_prints_the_version(flag: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main([flag])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"gppt {__version__}"


def test_no_subcommand_is_an_error() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main([])

    assert exc.value.code == 2


def test_login_follows_the_profiles_oauth_method(
    config_dir: Path,
    oauth_flow: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_: Any, **__: Any) -> Authorization:
        msg = "the e2e path should not run for an oauth profile"
        raise AssertionError(msg)

    monkeypatch.setattr(api, "fetch_authorization", explode)
    config.save("work", config.ProfileConfig(auth_method=config.AUTH_OAUTH))

    assert cli.main(["login", "-p", "work"]) == 0

    assert len(oauth_flow) == 1
    assert json.loads((config_dir / "work.token.json").read_text(encoding="utf-8"))["access_token"] == "at"


def test_login_oauth_flag_overrides_an_e2e_profile(
    config_dir: Path,  # noqa: ARG001
    oauth_flow: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*_: Any, **__: Any) -> Authorization:
        msg = "the e2e path should not run under --oauth"
        raise AssertionError(msg)

    monkeypatch.setattr(api, "fetch_authorization", explode)
    config.save("work", config.ProfileConfig(username="me", password="pw"))

    assert cli.main(["login", "-p", "work", "--oauth"]) == 0

    assert len(oauth_flow) == 1


def test_login_e2e_flag_overrides_an_oauth_profile(
    config_dir: Path,  # noqa: ARG001
    no_browser: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(**_: Any) -> Authorization:
        msg = "the oauth path should not run under --e2e"
        raise AssertionError(msg)

    monkeypatch.setattr(api, "request_authorization", explode)
    config.save("work", config.ProfileConfig(username="me", password="pw", auth_method=config.AUTH_OAUTH))

    assert cli.main(["login", "-p", "work", "--e2e"]) == 0

    assert no_browser[0]["username"] == "me"


def test_login_reuses_the_cached_token_before_asking_for_a_code(
    config_dir: Path,  # noqa: ARG001
    no_login: None,  # noqa: ARG001
) -> None:
    config.save("work", config.ProfileConfig(auth_method=config.AUTH_OAUTH))
    token.save("work", _token("cached"))

    assert cli.main(["login", "-p", "work", "--oauth"]) == 0


def test_login_rejects_both_method_flags_at_once() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["login", "--e2e", "--oauth"])

    assert exc.value.code == 2


def test_login_reports_an_unknown_configured_method(
    config_dir: Path,  # noqa: ARG001
    no_login: None,  # noqa: ARG001
    capsys: pytest.CaptureFixture[str],
) -> None:
    config.save("work", config.ProfileConfig(auth_method="chrome"))

    assert cli.main(["login", "-p", "work"]) == 1

    assert "chrome" in capsys.readouterr().err


def test_configure_oauth_skips_the_credential_prompts(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,  # noqa: ARG001
    capsys: pytest.CaptureFixture[str],
) -> None:
    stored = config.ProfileConfig(username="old", password="old-pw", totp_secret="old-totp")
    config.save("work", stored)

    def explode(_: str) -> str:
        msg = "oauth should not ask for a password"
        raise AssertionError(msg)

    monkeypatch.setattr("builtins.input", lambda _: "oauth")
    monkeypatch.setattr(cli.getpass, "getpass", explode)

    assert cli.main(["configure", "-p", "work"]) == 0

    assert config.load("work") == config.ProfileConfig(
        username="old",
        password="old-pw",
        totp_secret="old-totp",
        auth_method=config.AUTH_OAUTH,
    )
    assert "Keeping the stored credentials" in capsys.readouterr().out


def test_configure_re_asks_until_the_method_is_a_known_one(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,  # noqa: ARG001
    capsys: pytest.CaptureFixture[str],
) -> None:
    answers = iter(["firefox", "oauth"])
    monkeypatch.setattr("builtins.input", lambda _: next(answers))

    assert cli.main(["configure", "-p", "work"]) == 0

    assert config.load("work").auth_method == config.AUTH_OAUTH
    assert "firefox" in capsys.readouterr().out


def test_configure_suggests_e2e_when_the_stored_method_is_unreadable(
    monkeypatch: pytest.MonkeyPatch,
    config_dir: Path,  # noqa: ARG001
) -> None:
    config.save("work", config.ProfileConfig(auth_method="chrome"))
    monkeypatch.setattr("builtins.input", lambda _: "")
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: "")

    assert cli.main(["configure", "-p", "work"]) == 0

    assert config.load("work").auth_method == config.AUTH_E2E
