from __future__ import annotations

from base64 import urlsafe_b64encode
from hashlib import sha256
from random import uniform
from secrets import token_urlsafe
from time import sleep
from typing import TYPE_CHECKING
from urllib.request import getproxies

from selenium.webdriver import ChromeOptions

from .consts import USER_AGENT

if TYPE_CHECKING:
    from selenium.webdriver.remote.webelement import WebElement

PROXIES = getproxies()


def _get_chrome_option(headless: bool | None) -> ChromeOptions:
    options = ChromeOptions()

    if headless:
        options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-browser-side-navigation")
    options.add_argument("--start-maximized")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--user-agent=" + USER_AGENT)
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)  # noqa: FBT003
    options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

    if "all" in PROXIES:
        options.add_argument(f"--proxy-server={PROXIES['all']}")
    elif "https" in PROXIES:
        options.add_argument(f"--proxy-server={PROXIES['https']}")
    elif "http" in PROXIES:
        options.add_argument(f"--proxy-server={PROXIES['http']}")
    else:
        options.add_argument('--proxy-server="direct://"')
        options.add_argument("--proxy-bypass-list=*")

    return options


def _oauth_pkce() -> tuple[str, str]:
    """Proof Key for Code Exchange by OAuth Public Clients (RFC7636)."""

    def __s256(data: bytes) -> str:
        """S256 transformation method."""
        b = urlsafe_b64encode(sha256(data).digest()).rstrip(b"=")
        return b.decode("ascii")

    code_verifier = token_urlsafe(32)
    code_challenge = __s256(code_verifier.encode("ascii"))

    return code_verifier, code_challenge


def _slow_type(elm: WebElement, text: str) -> None:
    for character in text:
        elm.send_keys(character)
        sleep(uniform(0.3, 0.7))  # noqa: S311


__all__ = ("_get_chrome_option", "_oauth_pkce", "_slow_type")
