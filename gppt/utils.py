"""Utility functions."""

from __future__ import annotations

import asyncio
from base64 import urlsafe_b64encode
from hashlib import sha256
from random import uniform
from secrets import token_urlsafe
from typing import TYPE_CHECKING, TypedDict
from urllib.request import getproxies

from .consts import USER_AGENT

if TYPE_CHECKING:
    from playwright.async_api import Locator, ProxySettings

PROXIES = getproxies()


class BrowserOptions(TypedDict):
    headless: bool
    args: list[str]
    proxy: ProxySettings | None


def _get_browser_options(*, headless: bool | None) -> BrowserOptions:
    """Get browser launch options for Playwright.

    Args:
        headless (bool | None): Whether to run the browser in headless mode.

    Returns:
        dict: Browser launch options for Playwright.
    """
    args = [
        "--disable-gpu",
        "--disable-extensions",
        "--disable-infobars",
        "--disable-dev-shm-usage",
        "--disable-browser-side-navigation",
        "--start-maximized",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        f"--user-agent={USER_AGENT}",
    ]

    proxy: ProxySettings | None = None
    if "all" in PROXIES:
        proxy = {"server": PROXIES["all"]}
    elif "https" in PROXIES:
        proxy = {"server": PROXIES["https"]}
    elif "http" in PROXIES:
        proxy = {"server": PROXIES["http"]}

    return {
        "headless": headless if headless is not None else False,
        "args": args,
        "proxy": proxy,
    }


def _oauth_pkce() -> tuple[str, str]:
    """Proof Key for Code Exchange by OAuth Public Clients (RFC7636)."""

    def __s256(data: bytes) -> str:
        """S256 transformation method."""
        b = urlsafe_b64encode(sha256(data).digest()).rstrip(b"=")
        return b.decode("ascii")

    code_verifier = token_urlsafe(32)
    code_challenge = __s256(code_verifier.encode("ascii"))

    return code_verifier, code_challenge


async def _slow_type(elm: Locator, text: str) -> None:
    """Type text slowly into an element.

    Args:
        elm (Locator): The Playwright Locator to type into.
        text (str): The text to type.
    """
    for character in text:
        await elm.type(character)
        await asyncio.sleep(uniform(0.3, 0.7))  # noqa: S311


__all__ = ("_get_browser_options", "_oauth_pkce", "_slow_type")
