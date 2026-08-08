"""Public Python API.

Three entry points, in increasing order of how much they do for you:

- :func:`refresh` turns a refresh token into a fresh one. No browser, no files.
- :func:`login` drives the browser once and returns the token. No files.
- :func:`get_token` is what ``gppt login`` runs: reuse the cached token,
  else refresh it, else open the browser -- against a stored profile.

Everything here is synchronous and returns a :class:`gppt.token.Token`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from gppt import config, token
from gppt.browser import TotpProvider, fetch_authorization, is_chromium_installed
from gppt.secrets import resolve_secret

if TYPE_CHECKING:
    from collections.abc import Callable

    from gppt.token import Token


def refresh(refresh_token: str) -> Token:
    """Obtain a fresh token pair from a refresh token.

    Args:
        refresh_token (str): Refresh token from a previous login.

    Returns:
        Token: The issued token.

    Raises:
        TokenError: If pixiv rejects the refresh token.
    """
    return token.refresh(refresh_token)


def login(
    username: str = "",
    password: str = "",
    totp_secret: str = "",
    *,
    headless: bool | None = None,
    totp_prompt: Callable[[], str] | None = None,
) -> Token:
    """Log in through the browser and return the issued token.

    Nothing is read from or written to disk, so this is the direct replacement
    for the v4 ``GetPixivToken().login()``. Every credential may be given as an
    ``op://`` 1Password reference.

    Args:
        username (str): pixiv ID / e-mail address. Empty means a manual login.
        password (str): pixiv password. Empty means a manual login.
        totp_secret (str): Base32 TOTP secret or ``otpauth://`` URI, for an
            account with two-factor authentication enabled.
        headless (bool | None): Run the browser without a visible window.
            Defaults to True when both credentials are given, False otherwise.
        totp_prompt (Callable[[], str] | None): Called for a verification code
            when 2FA is requested and no ``totp_secret`` is set.

    Returns:
        Token: The issued token.

    Raises:
        ValueError: If ``headless`` is True without both credentials -- nobody
            can type into a window that is not drawn -- or if ``totp_secret``
            is not a usable TOTP secret.
        LoginError: If the browser login does not yield an authorization code.
        TokenError: If pixiv rejects the authorization code.
    """
    username = resolve_secret(username)
    password = resolve_secret(password)
    has_credentials = bool(username and password)

    if headless is None:
        headless = has_credentials
    elif headless and not has_credentials:
        msg = "headless=True needs both a username and a password; a manual login needs a visible window."
        raise ValueError(msg)

    # Built before the browser starts, so a malformed secret fails immediately.
    totp = TotpProvider(resolve_secret(totp_secret), totp_prompt)

    return token.exchange(fetch_authorization(username, password, headless=headless, totp=totp))


def get_token(
    profile: str = config.DEFAULT_PROFILE,
    *,
    headless: bool = True,
    force: bool = False,
    save: bool = True,
    notify: Callable[[str], None] | None = None,
    totp_prompt: Callable[[], str] | None = None,
) -> Token:
    """Return a usable token for a stored profile, logging in only if needed.

    The cached token is returned while it is still valid, then refreshed with
    its refresh token, and only then is the browser opened. This is exactly
    what ``gppt login`` does.

    Args:
        profile (str): Profile name, as created by ``gppt configure``.
            ``GPPT_USERNAME`` / ``GPPT_PASSWORD`` override its credentials.
        headless (bool): Run the browser without a visible window. Forced to
            False when the profile has no credentials to type in.
        force (bool): Ignore the cached token and log in through the browser.
        save (bool): Write the issued token back to the profile's cache.
        notify (Callable[[str], None] | None): Called with progress messages
            ("Reusing the cached token.", ...). Silent by default.
        totp_prompt (Callable[[], str] | None): Called for a verification code
            when 2FA is requested and the profile has no TOTP secret.

    Returns:
        Token: A token that is valid now.

    Raises:
        LoginError: If the browser login does not yield an authorization code.
        TokenError: If pixiv rejects the authorization code.
    """
    say = notify or _silent

    issued = None if force else _from_cache(profile, say)
    if issued is None:
        issued = _browser_login(
            config.load_or_default(profile),
            headless=headless,
            say=say,
            totp_prompt=totp_prompt,
        )

    if save:
        token.save(profile, issued)
    return issued


def _silent(_: str) -> None:
    """Swallow progress messages, so a library call prints nothing."""


def _from_cache(profile: str, say: Callable[[str], None]) -> Token | None:
    """Return a still-usable token from the profile's cache, refreshing it if needed."""
    cached = token.load(profile)
    if cached is None:
        return None

    if not cached.is_expired:
        say("Reusing the cached token.")
        return cached

    if not cached.refresh_token:
        return None

    say("Cached token expired; refreshing ...")
    try:
        return token.refresh(cached.refresh_token)
    except token.TokenError as exc:
        say(f"Refresh failed ({exc}); falling back to a browser login.")
        return None


def _browser_login(
    profile_config: config.ProfileConfig,
    *,
    headless: bool,
    say: Callable[[str], None],
    totp_prompt: Callable[[], str] | None,
) -> Token:
    """Run the browser login for a profile, downgrading headless when it cannot work."""
    # Any field may be a 1Password `op://` reference; expand them here.
    username = resolve_secret(profile_config.username)
    password = resolve_secret(profile_config.password)
    totp = TotpProvider(resolve_secret(profile_config.totp_secret), totp_prompt)

    if headless and not (username and password):
        say("No stored credentials: falling back to a visible browser window.")
        headless = False

    say("Opening browser for pixiv login ...")
    if not is_chromium_installed():
        say("(The first run may take a while to download the headless browser.)")

    return token.exchange(fetch_authorization(username, password, headless=headless, totp=totp))
