from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256
from typing import Any

import pyotp
import pytest

from gppt import browser
from gppt.browser import LoginError, TotpProvider

SECRET = "JBSWY3DPEHPK3PXP"


class FakeLocator:
    """Just enough Locator for _handle_totp / _slow_type / _submit."""

    def __init__(self, page: FakePage, visible_after: int | None = None) -> None:
        self.page = page
        self._visible_after = visible_after
        self._checks = 0
        self.typed: list[str] = []
        self.pressed: list[str] = []

    @property
    def first(self) -> FakeLocator:
        return self

    def is_visible(self) -> bool:
        self._checks += 1
        return self._visible_after is not None and self._checks > self._visible_after

    def type(self, text: str) -> None:
        self.typed.append(text)

    def press(self, key: str) -> None:
        self.pressed.append(key)


class FakePage:
    def __init__(self, url: str = "https://accounts.pixiv.net/login", *, totp_after: int | None = None) -> None:
        self.url = url
        self.locators: dict[str, FakeLocator] = {}
        self.waits = 0
        self._totp_after = totp_after

    def locator(self, selector: str) -> FakeLocator:
        if selector not in self.locators:
            after = self._totp_after if selector == browser.TOTP_SELECTOR else None
            self.locators[selector] = FakeLocator(self, visible_after=after)
        return self.locators[selector]

    def wait_for_timeout(self, _: float) -> None:
        self.waits += 1


def _handle_totp(page: Any, totp: Any = None, captured: dict[str, str] | None = None) -> None:
    browser._handle_totp(page, totp, {} if captured is None else captured)  # noqa: SLF001


def test_oauth_pkce_challenge_is_the_s256_of_the_verifier() -> None:
    verifier, challenge = browser._oauth_pkce()  # noqa: SLF001

    expected = urlsafe_b64encode(sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    assert challenge == expected
    assert "=" not in challenge


def test_oauth_pkce_is_not_reused() -> None:
    assert browser._oauth_pkce()[0] != browser._oauth_pkce()[0]  # noqa: SLF001


def test_login_params_carry_the_challenge() -> None:
    assert browser._login_params("chal") == {  # noqa: SLF001
        "code_challenge": "chal",
        "code_challenge_method": "S256",
        "client": "pixiv-android",
    }


def test_proxy_settings_prefer_all_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "PROXIES", {"all": "socks5://a:1", "https": "http://b:2"})

    assert browser._proxy_settings() == {"server": "socks5://a:1"}  # noqa: SLF001


def test_proxy_settings_fall_back_to_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "PROXIES", {"http": "http://b:2"})

    assert browser._proxy_settings() == {"server": "http://b:2"}  # noqa: SLF001


def test_no_proxy_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(browser, "PROXIES", {})

    assert browser._proxy_settings() is None  # noqa: SLF001


def test_totp_provider_derives_a_code_from_a_base32_secret() -> None:
    provider = TotpProvider(SECRET)

    assert provider.code() == pyotp.TOTP(SECRET).now()


def test_totp_provider_accepts_a_spaced_secret() -> None:
    provider = TotpProvider("JBSW Y3DP EHPK 3PXP")

    assert provider.code() == pyotp.TOTP(SECRET).now()


def test_totp_provider_accepts_an_otpauth_uri() -> None:
    provider = TotpProvider(f"otpauth://totp/pixiv:me?secret={SECRET}&issuer=pixiv")

    assert provider.code() == pyotp.TOTP(SECRET).now()


def test_totp_provider_rejects_a_malformed_secret() -> None:
    with pytest.raises(ValueError, match="not valid base32"):
        TotpProvider("not base32!")


def test_totp_provider_rejects_an_hotp_uri() -> None:
    with pytest.raises(ValueError, match="HOTP"):
        TotpProvider(f"otpauth://hotp/pixiv:me?secret={SECRET}&counter=0")


def test_totp_provider_falls_back_to_the_prompt() -> None:
    provider = TotpProvider(prompt=lambda: "123456")

    assert provider.code() == "123456"


def test_the_secret_wins_over_the_prompt() -> None:
    provider = TotpProvider(SECRET, prompt=lambda: "123456")

    assert provider.code() == pyotp.TOTP(SECRET).now()


def test_totp_provider_without_a_source_explains_itself() -> None:
    with pytest.raises(LoginError, match="no TOTP secret"):
        TotpProvider().code()


def test_handle_totp_returns_when_the_code_was_already_captured() -> None:
    page = FakePage()

    _handle_totp(page, None, {"code": "already-there"})

    assert page.waits == 0


def test_handle_totp_returns_once_the_login_redirects() -> None:
    page = FakePage(url=browser.REDIRECT_URI + "?foo=1")

    _handle_totp(page)

    assert page.waits == 0


def test_handle_totp_gives_up_quietly_when_no_challenge_appears() -> None:
    page = FakePage()

    _handle_totp(page)

    # Polled for the whole window, then left the redirect wait to report failures.
    assert page.waits == browser.TOTP_TIMEOUT_MS // browser.POLL_INTERVAL_MS
    assert page.locator(browser.TOTP_SELECTOR).typed == []


def test_handle_totp_types_the_code_and_submits() -> None:
    page = FakePage(totp_after=3)

    _handle_totp(page, TotpProvider(SECRET))

    assert "".join(page.locator(browser.TOTP_SELECTOR).typed) == pyotp.TOTP(SECRET).now()
    submit = next(loc for sel, loc in page.locators.items() if sel.startswith("xpath="))
    assert submit.pressed == ["Enter"]


def test_handle_totp_uses_the_prompt_when_there_is_no_secret() -> None:
    page = FakePage(totp_after=0)

    _handle_totp(page, TotpProvider(prompt=lambda: "654321"))

    assert "".join(page.locator(browser.TOTP_SELECTOR).typed) == "654321"


def test_handle_totp_without_a_provider_explains_itself() -> None:
    page = FakePage(totp_after=0)

    with pytest.raises(LoginError, match="none is available"):
        _handle_totp(page, None)
