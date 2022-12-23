"""
Original 1: https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362
Original 2: https://gist.github.com/upbit/6edda27cb1644e94183291109b8a5fde
"""

from __future__ import annotations

import json
import re
from base64 import urlsafe_b64encode
from hashlib import sha256
from random import uniform
from secrets import token_urlsafe
from time import sleep
from typing import Any, cast
from urllib.parse import urlencode
from urllib.request import getproxies

import pyderman
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .login_response_types import LoginInfo

# Latest app version can be found using GET /v1/application-info/android
USER_AGENT = "PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)"
CALLBACK_URI = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
REDIRECT_URI = "https://accounts.pixiv.net/post-redirect"
LOGIN_URL = "https://app-api.pixiv.net/web/v1/login"
AUTH_TOKEN_URL = "https://oauth.secure.pixiv.net/auth/token"
CLIENT_ID = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"
PROXIES = getproxies()

OptionsType = webdriver.chrome.options.Options


class GetPixivToken:
    def __init__(self) -> None:
        self.caps = DesiredCapabilities.CHROME.copy()
        self.caps["goog:loggingPrefs"] = {
            "performance": "ALL"
        }  # enable performance logs

    def login(
        self,
        headless: bool | None = False,
        username: str | None = None,
        password: str | None = None,
    ) -> LoginInfo:
        self.headless = headless
        self.username = username
        self.password = password

        executable_path = pyderman.install(verbose=False, browser=pyderman.chrome)
        if type(executable_path) is not str:
            raise ValueError("Executable path is not str somehow.")

        self.driver = webdriver.Chrome(
            executable_path=executable_path,
            options=self.__get_chrome_option(headless),
            desired_capabilities=self.caps,
        )

        code_verifier, code_challenge = self.__oauth_pkce()
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

        self.__fill_login_form()
        sleep(uniform(0.3, 0.7))
        self.__try_login()

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
        )
        return cast(LoginInfo, response.json())

    def __fill_login_form(self) -> None:
        if self.username:
            el = self.driver.find_element(By.XPATH, "//input[@autocomplete='username']")
            self.__slow_type(el, self.username)

        if self.password:
            el = self.driver.find_element(
                By.XPATH, "//input[@autocomplete='current-password']"
            )
            self.__slow_type(el, self.password)

    @staticmethod
    def __slow_type(elm: Any, text: str) -> None:
        for character in text:
            elm.send_keys(character)
            sleep(uniform(0.3, 0.7))

    def __try_login(self) -> None:
        if self.headless:
            label_selectors = [
                f"contains(text(), '{label}')"
                for label in ["ログイン", "Login", "登录", "로그인", "登入"]
            ]
            el = self.driver.find_element(
                By.XPATH, f"//button[@type='submit'][{' or '.join(label_selectors)}]"
            )
            el.send_keys(Keys.ENTER)

        WebDriverWait(self.driver, 60).until_not(
            EC.presence_of_element_located((By.CLASS_NAME, "busy-container")),
            "Please fill in login forms and press enter within 60 seconds.",
        )

        for _ in range(20):
            if self.driver.current_url[:40] == REDIRECT_URI:
                break
            sleep(1)
        else:
            self.driver.close()
            raise ValueError(
                "Failed to login. Please check your information or proxy. "
                "(Maybe restricted by pixiv?)"
            )

    @staticmethod
    def __get_chrome_option(headless: bool | None) -> OptionsType:
        options = webdriver.ChromeOptions()

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
            options.add_experimental_option("useAutomationExtension", False)

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

    @staticmethod
    def __oauth_pkce() -> tuple[str, str]:
        """Proof Key for Code Exchange by OAuth Public Clients (RFC7636)."""

        def __s256(data: bytes) -> str:
            """S256 transformation method."""
            b = urlsafe_b64encode(sha256(data).digest()).rstrip(b"=")
            return b.decode("ascii")

        code_verifier = token_urlsafe(32)
        code_challenge = __s256(code_verifier.encode("ascii"))

        return code_verifier, code_challenge

    def __parse_log(self) -> str | None:
        perf_log: list[dict[str, str | int]]
        perf_log = self.driver.get_log("performance")  # type: ignore[no-untyped-call]
        messages = [
            json.loads(row["message"])
            for row in perf_log
            if "message" in row and type(row["message"]) is str
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
