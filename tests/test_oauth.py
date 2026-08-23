from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import pytest

from gppt import oauth
from gppt.oauth import LoginError

if TYPE_CHECKING:
    from collections.abc import Callable

CALLBACK_URL = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback?state=abcdef&code=the-code&via=login"


def _prompt(answer: str) -> Callable[[str], str]:
    return lambda _: answer


def test_pkce_challenge_is_the_s256_of_the_verifier() -> None:
    verifier, challenge = oauth.generate_pkce()

    expected = urlsafe_b64encode(sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    assert challenge == expected
    assert "=" not in challenge


def test_pkce_is_not_reused() -> None:
    assert oauth.generate_pkce()[0] != oauth.generate_pkce()[0]


def test_login_url_carries_the_challenge() -> None:
    url = oauth.build_login_url("chal")

    assert url.startswith("https://app-api.pixiv.net/web/v1/login?")
    assert parse_qs(urlsplit(url).query) == {
        "code_challenge": ["chal"],
        "code_challenge_method": ["S256"],
        "client": ["pixiv-android"],
    }


@pytest.mark.parametrize(
    "pasted",
    [
        "the-code",
        "  the-code  ",
        "code=the-code",
        "code=the-code&state=abcdef",
        "pixiv://account/login?code=the-code",
        CALLBACK_URL,
        f"  {CALLBACK_URL}\n",
    ],
)
def test_extract_code_accepts_every_shape_the_user_might_paste(pasted: str) -> None:
    assert oauth.extract_code(pasted) == "the-code"


@pytest.mark.parametrize("pasted", ["", "   ", "no code here", "state=abcdef", "code=", "?code="])
def test_extract_code_rejects_text_without_a_code(pasted: str) -> None:
    with pytest.raises(LoginError):
        oauth.extract_code(pasted)


def test_request_authorization_returns_the_verifier_for_the_challenge_it_showed() -> None:
    messages: list[str] = []

    authorization = oauth.request_authorization(
        open_browser=False,
        prompt=_prompt(CALLBACK_URL),
        notify=messages.append,
    )

    assert authorization.code == "the-code"

    (challenge,) = [
        parse_qs(urlsplit(word).query)["code_challenge"][0]
        for message in messages
        for word in message.split()
        if word.startswith("https://app-api.pixiv.net/web/v1/login?")
    ]
    digest = sha256(authorization.code_verifier.encode("ascii")).digest()
    assert challenge == urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def test_request_authorization_does_not_touch_the_browser_when_not_asked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(_: str) -> bool:
        msg = "should not have been called"
        raise AssertionError(msg)

    monkeypatch.setattr(oauth.webbrowser, "open", explode)

    assert oauth.request_authorization(open_browser=False, prompt=_prompt("the-code"), notify=lambda _: None)


def test_request_authorization_still_prints_the_url_when_the_browser_will_not_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(oauth.webbrowser, "open", lambda _: False)
    messages: list[str] = []

    oauth.request_authorization(open_browser=True, prompt=_prompt("the-code"), notify=messages.append)

    assert any("https://app-api.pixiv.net/web/v1/login?" in message for message in messages)
    assert any("please open the URL above yourself" in message for message in messages)


def test_request_authorization_survives_a_browser_that_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error(_: str) -> bool:
        raise oauth.webbrowser.Error

    monkeypatch.setattr(oauth.webbrowser, "open", raise_error)

    assert oauth.request_authorization(prompt=_prompt("the-code"), notify=lambda _: None).code == "the-code"


def test_request_authorization_rejects_an_empty_answer() -> None:
    with pytest.raises(LoginError):
        oauth.request_authorization(open_browser=False, prompt=_prompt(""), notify=lambda _: None)


def test_request_authorization_keeps_stdout_clean_for_a_pipe(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("builtins.input", lambda: "the-code")

    assert oauth.request_authorization(open_browser=False).code == "the-code"

    captured = capsys.readouterr()
    assert "https://app-api.pixiv.net/web/v1/login?" in captured.err
    assert "code: " in captured.err
    assert captured.out == ""
