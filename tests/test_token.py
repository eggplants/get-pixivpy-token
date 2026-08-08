from __future__ import annotations

import stat
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, cast

import pytest

from gppt import config, token
from gppt.browser import Authorization

if TYPE_CHECKING:
    from pathlib import Path

RESPONSE: dict[str, Any] = {
    "access_token": "at",
    "refresh_token": "rt",
    "expires_in": 3600,
    "user": {"id": "123", "name": "Me", "account": "me"},
}


def _response(**overrides: Any) -> Any:
    return {**RESPONSE, **overrides}


def test_from_response_computes_an_absolute_expiry() -> None:
    before = datetime.now(tz=timezone.utc)

    parsed = token.Token.from_response(_response())

    assert parsed.access_token == "at"
    assert parsed.refresh_token == "rt"
    assert parsed.user_name == "Me"
    assert parsed.user_account == "me"
    assert datetime.fromisoformat(parsed.expires_at) >= before + timedelta(seconds=3600)
    assert parsed.is_expired is False


def test_from_response_without_a_token_raises() -> None:
    with pytest.raises(token.TokenError, match="did not return a token"):
        token.Token.from_response(cast("Any", {"error": "invalid_grant"}))


def test_a_lapsed_token_is_expired() -> None:
    stale = token.Token(
        access_token="at",
        refresh_token="rt",
        expires_in=3600,
        expires_at=(datetime.now(tz=timezone.utc) - timedelta(seconds=1)).isoformat(),
    )

    assert stale.is_expired is True


def test_a_token_expiring_within_the_margin_is_expired() -> None:
    almost = token.Token(
        access_token="at",
        refresh_token="rt",
        expires_in=3600,
        expires_at=(datetime.now(tz=timezone.utc) + token.EXPIRY_MARGIN / 2).isoformat(),
    )

    assert almost.is_expired is True


def test_a_corrupt_expiry_counts_as_expired() -> None:
    broken = token.Token(access_token="at", refresh_token="rt", expires_in=0, expires_at="not-a-date")

    assert broken.is_expired is True


def test_save_then_load_roundtrip(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    issued = token.Token.from_response(_response())

    path = token.save("work", issued)

    assert path == tmp_path / "work.token.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert token.load("work") == issued


def test_load_without_a_cache_returns_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)

    assert token.load("work") is None


def test_load_ignores_a_corrupt_cache(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    (tmp_path / "work.token.json").write_text("{not json", encoding="utf-8")

    assert token.load("work") is None


def test_exchange_posts_the_pkce_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, Any] = {}

    def fake_post(url: str, **kwargs: Any) -> Any:
        sent["url"] = url
        sent["data"] = kwargs["data"]
        return _FakeResponse(_response())

    monkeypatch.setattr(token.requests, "post", fake_post)

    issued = token.exchange(Authorization(code="the-code", code_verifier="the-verifier"))

    assert issued.access_token == "at"
    assert sent["url"] == token.AUTH_TOKEN_URL
    assert sent["data"]["grant_type"] == "authorization_code"
    assert sent["data"]["code"] == "the-code"
    assert sent["data"]["code_verifier"] == "the-verifier"


def test_refresh_posts_the_refresh_token(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict[str, Any] = {}

    def fake_post(_: str, **kwargs: Any) -> Any:
        sent["data"] = kwargs["data"]
        return _FakeResponse(_response(access_token="at2"))

    monkeypatch.setattr(token.requests, "post", fake_post)

    issued = token.refresh("rt")

    assert issued.access_token == "at2"
    assert sent["data"]["grant_type"] == "refresh_token"
    assert sent["data"]["refresh_token"] == "rt"


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload
