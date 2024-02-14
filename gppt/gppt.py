"""
Original 1: https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362
Original 2: https://gist.github.com/upbit/6edda27cb1644e94183291109b8a5fde
"""

from __future__ import annotations

import json
import re
import sys
from typing import cast
from urllib.parse import urlencode

import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC  # noqa: N812
from selenium.webdriver.support.ui import WebDriverWait

from .consts import (
    AUTH_TOKEN_URL,
    CALLBACK_URI,
    CLIENT_ID,
    CLIENT_SECRET,
    LOGIN_URL,
    REDIRECT_URI,
    USER_AGENT,
)
from .types import LoginInfo
from .utils import PROXIES, _get_chrome_option, _oauth_pkce, _slow_type

TIMEOUT = 10.0


class GetPixivToken:
    def __init__(
        self,
        *,
        headless: bool | None = False,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self.headless = headless
        self.username = username
        self.password = password

    def login(
        self,
        *,
        headless: bool | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> LoginInfo:
        if headless is not None:
            self.headless = headless
        if username is not None:
            self.username = username
        if password is not None:
            self.password = password

        # No headless if username or password are missing, manual input needed
        if self.headless is True and (self.username is None or self.password is None):
            self.headless = False

        self.driver = webdriver.Chrome(
            options=_get_chrome_option(self.headless),
        )

        code_verifier, code_challenge = _oauth_pkce()
        login_params = {
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "client": "pixiv-android",
        }

        self.driver.get(f"{LOGIN_URL}?{urlencode(login_params)}")
        WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located((By.CLASS_NAME, "sc-bn9ph6-6")),
            f"Login form is not appeared. Please check connectivity for {LOGIN_URL}",
        )

        if self.username is not None and self.password is not None:
            self.__fill_login_form()
            self.__try_login()
        else:
            print("Waiting for manual login.", file=sys.stderr)  # noqa: T201
            self.__wait_for_redirect()

        # filter code url from performance logs
        code = self.__parse_log()
        self.driver.close()

        response = requests.post(
            AUTH_TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
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

        return cast(LoginInfo, response.json())

    @staticmethod
    def refresh(refresh_token: str) -> LoginInfo:
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
        return cast(LoginInfo, response.json())

    def __fill_login_form(self) -> None:
        if self.username:
            el = self.driver.find_element(By.XPATH, "//input[@autocomplete='username']")
            _slow_type(el, self.username)

        if self.password:
            el = self.driver.find_element(By.XPATH, "//input[@autocomplete='current-password']")
            _slow_type(el, self.password)

    def __try_login(self) -> None:
        label_selectors = [f"contains(text(), '{label}')" for label in ["ログイン", "Log In", "登录", "로그인", "登入"]]
        el = self.driver.find_element(By.XPATH, f"//button[@type='submit'][{' or '.join(label_selectors)}]")
        el.send_keys(Keys.ENTER)

        self.__wait_for_redirect()

    def __parse_log(self) -> str | None:
        perf_log: list[dict[str, str | int]]
        perf_log = self.driver.get_log("performance")
        messages = [
            json.loads(row["message"]) for row in perf_log if "message" in row and isinstance(row["message"], str)
        ]
        messages = [
            message["message"]
            for message in messages
            if "message" in message
            and "method" in message["message"]
            and message["message"]["method"] == "Network.requestWillBeSent"
        ]

        for message in messages:
            url = message.get("params", {}).get("documentURL")
            if url is not None and str(url).startswith("pixiv://"):
                m = re.search(r"code=([^&]*)", url)
                return None if m is None else str(m.group(1))

        return None

    def __wait_for_redirect(self) -> None:
        try:
            WebDriverWait(self.driver, 20).until(EC.url_matches(f"^{REDIRECT_URI}"))
        except TimeoutException as err:
            self.driver.close()
            msg = "Failed to login. Please check your information or proxy. (Maybe restricted by pixiv?)"
            raise ValueError(msg) from err
