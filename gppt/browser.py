"""Drive a real browser through the pixiv login and capture the OAuth code.

pixiv's mobile OAuth flow hands the browser an authorization code by
redirecting to a ``pixiv://`` deep link. We intercept that request to recover
the code, then exchange it for tokens with the PKCE verifier generated here.

Based on:
- https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362
- https://gist.github.com/upbit/6edda27cb1644e94183291109b8a5fde
"""

from __future__ import annotations

import re
import sys
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from random import uniform
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Final
from urllib.parse import urlencode
from urllib.request import getproxies

import pyotp
from install_playwright import install
from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeoutError
from playwright.sync_api import sync_playwright

from gppt.consts import LOGIN_URL, REDIRECT_URI, USER_AGENT

if TYPE_CHECKING:
    from collections.abc import Callable

    from playwright.sync_api import Locator, Page, ProxySettings, Request

PROXIES: Final = getproxies()

FORM_TIMEOUT_MS: Final = 20_000  # wait for the login form to render
REDIRECT_TIMEOUT_MS: Final = 60_000  # wait for the redirect after a filled-in form
MANUAL_TIMEOUT_MS: Final = 300_000  # ditto, but a human is typing (and maybe solving a captcha)
SETTLE_MS: Final = 1_000  # let the deep-link request fire after the redirect
TOTP_TIMEOUT_MS: Final = 15_000  # how long to wait before concluding 2FA was not asked for
POLL_INTERVAL_MS: Final = 200  # step size when polling for a selector

# Human-like randomised waits (seconds) between keystrokes, to avoid an
# obviously robotic input cadence.
TYPE_DELAY_S: Final = (0.3, 0.7)

USERNAME_SELECTOR: Final = "input[autocomplete^='username']"
PASSWORD_SELECTOR: Final = "input[autocomplete^='current-password']"  # noqa: S105
# Shown only when the account has two-factor authentication enabled.
TOTP_SELECTOR: Final = "input[autocomplete='one-time-code']"

OTPAUTH_PREFIX: Final = "otpauth://"

# The submit button is only identifiable by its label, which is localised.
SUBMIT_LABELS: Final[list[str]] = ["ログイン", "Log In", "登录", "로그인", "登入"]

BROWSER_ARGS: Final[list[str]] = [
    "--disable-gpu",
    "--disable-extensions",
    "--disable-infobars",
    "--disable-dev-shm-usage",
    "--disable-browser-side-navigation",
    "--start-maximized",
    "--no-sandbox",
    f"--user-agent={USER_AGENT}",
]


class LoginError(RuntimeError):
    """Raised when the browser login does not yield an authorization code."""


@dataclass
class Authorization:
    """An authorization code plus the PKCE verifier it must be exchanged with."""

    code: str
    code_verifier: str


class TotpProvider:
    """Yields two-factor verification codes, from a shared secret or from a prompt.

    The code is only produced when pixiv actually asks for one, so a provider
    backed by a prompt does not disturb an account without 2FA enabled.
    """

    def __init__(self, secret: str = "", prompt: Callable[[], str] | None = None) -> None:
        """Build a provider.

        Args:
            secret (str): A base32 TOTP secret or an ``otpauth://`` URI. Empty
                to fall back to ``prompt``.
            prompt (Callable[[], str] | None): Called to obtain a code when no
                secret is configured.

        Raises:
            ValueError: If ``secret`` is not a usable TOTP secret.
        """
        self._totp = _parse_totp(secret) if secret else None
        self._prompt = prompt

    def code(self) -> str:
        """Return a verification code to type into pixiv's 2FA form.

        Returns:
            str: The current code.

        Raises:
            LoginError: If there is neither a secret nor a prompt to ask.
        """
        if self._totp is not None:
            return self._totp.now()
        if self._prompt is not None:
            return self._prompt()
        msg = (
            "pixiv is asking for a two-factor verification code, but this profile has no TOTP secret. "
            "Run `gppt configure` and set one, or pass totp_secret=/totp_prompt= to gppt.login()."
        )
        raise LoginError(msg)


def _parse_totp(secret: str) -> pyotp.TOTP:
    """Accept either an ``otpauth://`` URI or a bare base32 secret."""
    if secret.startswith(OTPAUTH_PREFIX):
        parsed = pyotp.parse_uri(secret)
        if not isinstance(parsed, pyotp.TOTP):
            msg = "The configured TOTP secret is an otpauth:// URI for HOTP, not TOTP."
            raise ValueError(msg)
        return parsed

    # pixiv displays the secret in space-separated groups; accept it verbatim.
    totp = pyotp.TOTP(secret.replace(" ", ""))
    try:
        totp.now()
    # pyotp surfaces a bad secret late, as a binascii/TypeError from .now().
    except Exception as exc:
        msg = f"The configured TOTP secret is not valid base32: {exc}"
        raise ValueError(msg) from exc
    return totp


def is_chromium_installed() -> bool:
    """Whether the Chromium build Playwright needs is already downloaded locally.

    Returns:
        bool: True if the browser binary is present.
    """
    with sync_playwright() as pw:
        return Path(pw.chromium.executable_path).exists()


def fetch_authorization(
    username: str,
    password: str,
    *,
    headless: bool,
    totp: TotpProvider | None = None,
) -> Authorization:
    """Run the browser login and return the captured authorization code.

    When ``username`` and ``password`` are both set the login form is filled in
    automatically, including the two-factor verification code if pixiv asks for
    one; otherwise the browser is left open for a manual login.

    Args:
        username (str): pixiv ID / e-mail address, or an empty string.
        password (str): pixiv password, or an empty string.
        headless (bool): Run the browser without a visible window.
        totp (TotpProvider | None): Source of two-factor verification codes.

    Returns:
        Authorization: The captured code and its PKCE verifier.

    Raises:
        LoginError: If the login form never appears, the login fails, 2FA is
            required but unavailable, or no authorization code is captured.
    """
    code_verifier, code_challenge = _oauth_pkce()
    captured: dict[str, str] = {}

    with sync_playwright() as pw:
        # Ensure the Chromium browser is present (installs on first run).
        install([pw.chromium], with_deps=True)
        browser = pw.chromium.launch(headless=headless, args=BROWSER_ARGS)
        proxy = _proxy_settings()
        context = browser.new_context(proxy=proxy) if proxy else browser.new_context()
        page = context.new_page()

        def on_request(request: Request) -> None:
            if not request.url.startswith("pixiv://"):
                return
            if match := re.search(r"code=([^&]*)", request.url):
                captured["code"] = match.group(1)

        page.on("request", on_request)

        try:
            page.goto(f"{LOGIN_URL}?{urlencode(_login_params(code_challenge))}")
            _wait_for_form(page)
            if username and password:
                _fill_login_form(page, username, password)
                _submit(page)
                _handle_totp(page, totp, captured)
                timeout_ms = REDIRECT_TIMEOUT_MS
            else:
                print("Waiting for manual login in the browser window ...", file=sys.stderr)  # noqa: T201
                timeout_ms = MANUAL_TIMEOUT_MS
            _wait_for_redirect(page, timeout_ms)
            page.wait_for_timeout(SETTLE_MS)
        finally:
            context.close()
            browser.close()

    if "code" not in captured:
        msg = "Did not capture an authorization code from the pixiv:// callback."
        raise LoginError(msg)

    return Authorization(code=captured["code"], code_verifier=code_verifier)


def _login_params(code_challenge: str) -> dict[str, str]:
    return {
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "client": "pixiv-android",
    }


def _proxy_settings() -> ProxySettings | None:
    """Map ``ALL_PROXY`` / ``HTTPS_PROXY`` / ``HTTP_PROXY`` onto Playwright."""
    for key in ("all", "https", "http"):
        if key in PROXIES:
            return {"server": PROXIES[key]}
    return None


def _oauth_pkce() -> tuple[str, str]:
    """Generate a PKCE verifier/challenge pair (RFC 7636, S256)."""
    code_verifier = token_urlsafe(32)
    digest = urlsafe_b64encode(sha256(code_verifier.encode("ascii")).digest()).rstrip(b"=")
    return code_verifier, digest.decode("ascii")


def _wait_for_form(page: Page) -> None:
    try:
        page.wait_for_selector(USERNAME_SELECTOR, timeout=FORM_TIMEOUT_MS)
    except (PWTimeoutError, PWError) as exc:
        msg = f"Login form did not appear. Please check connectivity for {LOGIN_URL}"
        raise LoginError(msg) from exc


def _fill_login_form(page: Page, username: str, password: str) -> None:
    _slow_type(page.locator(USERNAME_SELECTOR), username)
    _slow_type(page.locator(PASSWORD_SELECTOR), password)


def _handle_totp(page: Page, totp: TotpProvider | None, captured: dict[str, str]) -> None:
    """Fill in the two-factor verification code, if pixiv asks for one.

    An account without 2FA never renders the field: the password submit
    redirects straight through instead. So this polls for either outcome and
    returns quietly when the login is already on its way, rather than blocking
    on a field that will never appear.
    """
    totp_input = page.locator(TOTP_SELECTOR)

    waited = 0
    while waited < TOTP_TIMEOUT_MS:
        if "code" in captured or page.url.startswith(REDIRECT_URI):
            return  # logged in without a 2FA challenge
        if _is_visible(totp_input):
            break
        page.wait_for_timeout(POLL_INTERVAL_MS)
        waited += POLL_INTERVAL_MS
    else:
        # No challenge and no redirect yet -- let _wait_for_redirect decide.
        return

    if totp is None:
        msg = (
            "pixiv is asking for a two-factor verification code, but none is available. "
            "Run `gppt configure` and set a TOTP secret."
        )
        raise LoginError(msg)

    _slow_type(totp_input, totp.code())
    _submit(page)


def _is_visible(locator: Locator) -> bool:
    try:
        return locator.first.is_visible()
    except (PWTimeoutError, PWError):
        return False


def _slow_type(element: Locator, text: str) -> None:
    """Type ``text`` one character at a time with a random pause per keystroke."""
    for character in text:
        element.type(character)
        element.page.wait_for_timeout(uniform(*TYPE_DELAY_S) * 1000)  # noqa: S311


def _submit(page: Page) -> None:
    conditions = " or ".join(f"contains(text(), '{label}')" for label in SUBMIT_LABELS)
    page.locator(f"xpath=//button[@type='submit'][{conditions}]").press("Enter")


def _wait_for_redirect(page: Page, timeout_ms: int) -> None:
    try:
        page.wait_for_url(
            re.compile(f"^{re.escape(REDIRECT_URI)}"),
            wait_until="networkidle",
            timeout=timeout_ms,
        )
    except (PWTimeoutError, PWError) as exc:
        msg = "Failed to login. Please check your credentials or proxy. (Maybe restricted by pixiv?)"
        raise LoginError(msg) from exc
