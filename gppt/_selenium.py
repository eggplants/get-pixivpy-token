"""
Original 1: https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362
Original 2: https://gist.github.com/upbit/6edda27cb1644e94183291109b8a5fde
"""

from __future__ import annotations

import json
import re
import urllib.request
from base64 import urlsafe_b64encode
from hashlib import sha256
from random import uniform
from secrets import token_urlsafe
from time import sleep
from typing import Any, cast
from urllib.parse import urlencode

import pyderman
import requests
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
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
REQUESTS_KWARGS: dict[str, Any] = {
    # 'proxies': {
    #     'https': 'http://127.0.0.1:1087',
    # },
    # 'verify': False
}


def _get_system_proxy(proxy_type: str = "https") -> str | None:
    """
    Load proxy from system, such as `export ALL_PROXY=xxxx` in ~/.bashrc.
    """
    _sys_proxies = urllib.request.getproxies()
    if "all" in _sys_proxies:
        return _sys_proxies["all"]
    else:
        return _sys_proxies.get(proxy_type, None)


def _get_proxy(proxy: str | None = None, proxy_type: str = "https") -> str | None:
    """
    If `proxy` is given, just use this one, otherwise load proxy from system.
    """
    return proxy or _get_system_proxy(proxy_type)


def _get_proxies_for_requests(
    proxy: str | None = None, proxy_type: str = "https"
) -> dict[str, str] | None:
    """
    Load proxy to dict-formatted proxies for `requests` module.
    """
    _proxy = _get_proxy(proxy, proxy_type)
    return {"all": _proxy} if _proxy else None


class GetPixivToken:
    def __init__(self) -> None:

        self.caps = DesiredCapabilities.CHROME.copy()
        self.caps["goog:loggingPrefs"] = {
            "performance": "ALL"
        }  # enable performance logs

    def login(
        self,
        headless: bool | None = False,
        user: str | None = None,
        pass_: str | None = None,
        proxy: str | None = None,
    ) -> LoginInfo:
        self.headless, self.user, self.pass_ = headless, user, pass_
        executable_path = pyderman.install(verbose=False, browser=pyderman.chrome)
        if type(executable_path) is not str:
            raise ValueError("Executable path is not str somehow.")
        if headless is not None and headless:
            opts = self.__get_headless_option(proxy)
        else:
            opts = self.__get_option(proxy)

        self.driver = webdriver.Chrome(
            executable_path=executable_path,
            options=opts,
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
            proxies=_get_proxies_for_requests(proxy, "https"),
            **REQUESTS_KWARGS,
        )

        return cast(LoginInfo, response.json())

    @staticmethod
    def refresh(refresh_token: str, proxy: str | None = None) -> LoginInfo:
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
            proxies=_get_proxies_for_requests(proxy, "https"),
            **REQUESTS_KWARGS,
        )
        return cast(LoginInfo, response.json())

    def __fill_login_form(self) -> None:
        if self.user is not None:
            el = self.driver.find_element(By.XPATH, "//input[@autocomplete='username']")
            self.__slow_type(el, self.user)

        if self.pass_ is not None:
            el = self.driver.find_element(
                By.XPATH, "//input[@autocomplete='current-password']"
            )
            self.__slow_type(el, self.pass_)

    @staticmethod
    def __slow_type(elm: Any, text: str) -> None:
        for character in text:
            elm.send_keys(character)
            sleep(uniform(0.3, 0.7))

    # For the users in different language areas, this text will be different,
    # so using `Login` directly may cause `NoSuchElementException`.
    # The code here may also need to be supplemented with versions in other languages.
    __LOGIN_TEXTS__ = ["Login", "登录"]

    def __try_login(self) -> None:
        if self.headless:
            el, lerr = None, None
            for login_text in self.__LOGIN_TEXTS__:
                try:
                    el = self.driver.find_element(
                        By.XPATH,
                        f"//button[@type='submit'][contains(text(), {login_text!r})]",
                    )
                except NoSuchElementException as err:
                    lerr = err
                else:
                    break

            if isinstance(el, WebElement):
                el.send_keys(Keys.ENTER)
            elif isinstance(lerr, NoSuchElementException):
                raise lerr
            else:
                assert False, "Should not reach here!"

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
    def __get_option(proxy: str | None = None) -> webdriver.chrome.options.Options:
        options = webdriver.ChromeOptions()
        proxy = _get_proxy(proxy)
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")

        return options

    @staticmethod
    def __get_headless_option(
        proxy: str | None = None,
    ) -> webdriver.chrome.options.Options:
        options = webdriver.ChromeOptions()
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

        proxy = _get_proxy(proxy)
        if proxy:
            options.add_argument(f"--proxy-server={proxy}")
        else:
            options.add_argument('--proxy-server="direct://"')
            options.add_argument("--proxy-bypass-list=*")

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
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

    # Example of pref log:
    #
    # {
    #     'level': 'INFO',
    #     'message': '{
    #             "message":
    #                 {
    #                     "method": "Network.loadingFinished",
    #                     "params":{
    #                         "encodedDataLength": 0,
    #                         "requestId": "B13E7DBAD4EB28AAD6B05EEA5D628CE5",
    #                         "shouldReportCorbBlocking": false,
    #                         "timestamp":105426.696689
    #                     }
    #                 },
    #             "webview": "9D08CF686401F5B87539217E751861DD"
    #     }',
    #     'timestamp': 1653700994895
    # }
