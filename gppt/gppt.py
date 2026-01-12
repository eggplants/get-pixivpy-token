"""This module contains the GetPixivToken class, which is used to obtain an OAuth token from Pixiv.

It uses the Pixiv API and Playwright to automate the login process. The class supports both headless and
non-headless modes for the web browser.

It also provides a method to refresh the token using the refresh token obtained during login.
The code is based on the work of other developers and has been modified for better readability and maintainability.

The original code was found in the following Gists:
- Original 1: https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362
- Original 2: https://gist.github.com/upbit/6edda27cb1644e94183291109b8a5fde
"""

from __future__ import annotations

import re
import sys
from typing import TYPE_CHECKING, Final, cast
from urllib.parse import urlencode

import requests
from install_playwright import install
from playwright.async_api import Request, async_playwright

from .consts import (
    AUTH_TOKEN_URL,
    CALLBACK_URI,
    CLIENT_ID,
    CLIENT_SECRET,
    LOGIN_URL,
    REDIRECT_URI,
    USER_AGENT,
)
from .utils import PROXIES, _get_browser_options, _oauth_pkce, _slow_type

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page
    from playwright.async_api._generated import Playwright as AsyncPlaywright

    from .model_types import LoginInfo

TIMEOUT = 10.0


class GetPixivToken:
    """GetPixivToken class for obtaining OAuth tokens from Pixiv.

    This class uses Playwright to automate the login process and retrieve the OAuth token.
    It supports both headless and non-headless modes for the browser.
    """

    def __init__(
        self,
        *,
        headless: bool | None = False,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        """Initialize the GetPixivToken class.

        Args:
            headless (bool | None): Whether to run the browser in headless mode. Defaults to False.
            username (str | None): The username for Pixiv login. Defaults to None.
            password (str | None): The password for Pixiv login. Defaults to None.

        Raises:
            ValueError: If headless mode is enabled but username or password is not provided.
        """
        self.headless = headless
        self.username = username
        self.password = password
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.code: str | None = None

    async def login(
        self,
        *,
        headless: bool | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> LoginInfo:
        """Login to Pixiv and obtain the OAuth token.

        This method uses Playwright to automate the login process and retrieve the OAuth token.

        Args:
            headless (bool | None): Whether to run the browser in headless mode. Defaults to None.
            username (str | None): The username for Pixiv login. Defaults to None.
            password (str | None): The password for Pixiv login. Defaults to None.

        Returns:
            LoginInfo: The login information containing the OAuth token and other details.

        Raises:
            ValueError: If headless mode is enabled but username or password is not provided.
        """
        self.__update_credentials(
            headless=headless,
            username=username,
            password=password,
        )
        code_verifier = await self.__perform_browser_login()
        return self.__exchange_code_for_token(code_verifier)

    def __update_credentials(
        self,
        *,
        headless: bool | None,
        username: str | None,
        password: str | None,
    ) -> None:
        if headless is not None:
            self.headless = headless
        if username is not None:
            self.username = username
        if password is not None:
            self.password = password

        if self.headless is True and (self.username is None or self.password is None):
            self.headless = False

    async def __perform_browser_login(self) -> str:
        async with async_playwright() as p:
            await self.__setup_browser(p)
            code_verifier = await self.__navigate_and_login()

            if self.browser is not None:
                await self.browser.close()

        if self.code is None:
            msg = "Failed to capture OAuth code from callback URL"
            raise ValueError(msg)

        return code_verifier

    async def __setup_browser(self, p: AsyncPlaywright) -> None:
        install([p.chromium], with_deps=True)
        browser_options = _get_browser_options(headless=self.headless)

        # Extract proxy and args from options
        proxy = browser_options["proxy"]
        args = browser_options["args"]
        headless = browser_options["headless"]

        self.browser = await p.chromium.launch(
            headless=headless,
            args=args,
        )

        context_options: dict = {}
        if proxy:
            context_options["proxy"] = proxy

        self.context = await self.browser.new_context(**context_options)

        self.page = await self.context.new_page()

        # Set up network listener to capture the OAuth callback URL
        self.code = None

        async def handle_request(request: Request) -> None:
            url = request.url
            if not url.startswith("pixiv://"):
                return
            if m := re.search(r"code=([^&]*)", url):
                self.code = m.group(1)

        self.page.on("request", handle_request)

    async def __navigate_and_login(self) -> str:
        assert self.page is not None  # noqa: S101

        code_verifier, code_challenge = _oauth_pkce()
        login_params = {
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "client": "pixiv-android",
        }

        await self.page.goto(f"{LOGIN_URL}?{urlencode(login_params)}")

        # Wait for login form to appear
        try:
            await self.page.wait_for_selector(".sc-bn9ph6-6", timeout=20000)
        except Exception as e:
            msg = f"Login form is not appeared. Please check connectivity for {LOGIN_URL}"
            raise ValueError(msg) from e

        if self.username is not None and self.password is not None:
            await self.__fill_login_form()
            await self.__try_login()
        else:
            print("Waiting for manual login.", file=sys.stderr)  # noqa: T201
            await self.__wait_for_redirect()

        await self.page.wait_for_timeout(1000)

        return code_verifier

    def __exchange_code_for_token(self, code_verifier: str) -> LoginInfo:
        response = requests.post(
            AUTH_TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": self.code,
                "code_verifier": code_verifier,
                "grant_type": "authorization_code",
                "include_policy": "true",
                "redirect_uri": CALLBACK_URI,
            },
            headers={
                "user-agent": USER_AGENT,
                "app-os-version": "14.6",
                "app-os": "ios",
            },
            proxies=PROXIES,
            timeout=TIMEOUT,
        )

        return cast("LoginInfo", response.json())

    @staticmethod
    def refresh(refresh_token: str) -> LoginInfo:
        """Refresh the OAuth token using the refresh token.

        This method sends a request to the Pixiv API to refresh the token.

        Args:
            refresh_token (str): The refresh token obtained during login.

        Returns:
            LoginInfo: The login information containing the new OAuth token and other details.

        Raises:
            ValueError: If the refresh token is not provided.
        """
        response = requests.post(
            AUTH_TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "refresh_token",
                "include_policy": "true",
                "refresh_token": refresh_token,
            },
            headers={
                "user-agent": USER_AGENT,
                "app-os-version": "14.6",
                "app-os": "ios",
            },
            proxies=PROXIES,
            timeout=TIMEOUT,
        )
        return cast("LoginInfo", response.json())

    async def __fill_login_form(self) -> None:
        if self.page is None:
            return

        if self.username:
            el = self.page.locator("input[autocomplete^='username']")
            await _slow_type(el, self.username)

        if self.password:
            el = self.page.locator("input[autocomplete^='current-password']")
            await _slow_type(el, self.password)

    async def __try_login(self) -> None:
        if self.page is None:
            return

        labels: Final[list[str]] = ["ログイン", "Log In", "登录", "로그인", "登入"]
        label_conditions = " or ".join([f"contains(text(), '{label}')" for label in labels])
        el = self.page.locator(f"xpath=//button[@type='submit'][{label_conditions}]")
        await el.press("Enter")

        await self.__wait_for_redirect()

    async def __wait_for_redirect(self) -> None:
        assert self.page is not None  # noqa: S101

        try:
            await self.page.wait_for_url(
                re.compile(f"^{re.escape(REDIRECT_URI)}"), wait_until="networkidle", timeout=60000
            )
        except Exception as err:
            if self.browser:
                await self.browser.close()
            msg = "Failed to login. Please check your information or proxy. (Maybe restricted by pixiv?)"
            raise ValueError(msg) from err
