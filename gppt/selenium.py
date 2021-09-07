#!/usr/bin/env python

# Original 1: https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362
# Original 2: https://gist.github.com/upbit/6edda27cb1644e94183291109b8a5fde

import json
import re
import time
from base64 import urlsafe_b64encode
from hashlib import sha256
from random import uniform
from secrets import token_urlsafe
from time import sleep
from typing import Any, Optional
from urllib.parse import urlencode

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
REQUESTS_KWARGS: dict[str, Any] = {
    # 'proxies': {
    #     'https': 'http://127.0.0.1:1087',
    # },
    # 'verify': False
}


class GetPixivToken(object):
    def __init__(self) -> None:

        self.caps = DesiredCapabilities.CHROME.copy()
        self.caps["goog:loggingPrefs"] = {
            "performance": "ALL"
        }  # enable performance logs

    def login(self,
              headless: Optional[bool] = False,
              user: Optional[str] = None,
              pass_: Optional[str] = None) -> LoginInfo:
        self.headless, self.user, self. pass_ = headless, user, pass_

        if headless:
            opts = self.__get_headless_option()
            self.driver = webdriver.Chrome(
                options=opts, desired_capabilities=self.caps)

        else:
            self.driver = webdriver.Chrome(desired_capabilities=self.caps)

        code_verifier, code_challenge = self.__oauth_pkce()
        login_params = {
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "client": "pixiv-android",
        }

        self.driver.get(f"{LOGIN_URL}?{urlencode(login_params)}")
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.ID, "LoginComponent")))
        self.__fill_login_form()

        if self.headless:
            self.__try_login()

        while self.driver.current_url[:40] != REDIRECT_URI:
            time.sleep(1)  # wait for login

        # filter code url from performance logs
        code = self.__parse_log(self.driver)
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
            **REQUESTS_KWARGS
        )

        return response.json()

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
            **REQUESTS_KWARGS
        )
        return response.json()

    def __fill_login_form(self) -> None:
        if self.user is not None:
            el = self.driver.find_element_by_xpath(
                "//div[@id='LoginComponent']//*/input[@type='text']")
            self.__slow_type(el, self.user)

        if self.pass_ is not None:
            el = self.driver.find_element_by_xpath(
                "//div[@id='LoginComponent']//*/input[@type='password']")
            self.__slow_type(el, self.pass_)

    @staticmethod
    def __slow_type(elm: Any, text: str) -> None:
        for character in text:
            elm.send_keys(character)
            sleep(uniform(0.3, 0.7))

    def __try_login(self) -> None:
        el = self.driver.find_element_by_xpath(
            "//div[@id='LoginComponent']"
            "//button[@class='signup-form__submit']")
        el.send_keys(Keys.ENTER)

        sleep(0.1)
        WebDriverWait(self.driver, 10).until_not(
            EC.presence_of_element_located((By.CLASS_NAME, "busy-container")))
        sleep(0.1)
        c = 0
        while 10 > c and self.driver.current_url[:40] != REDIRECT_URI:
            c += 1
            sleep(1)
        else:
            if c == 10:
                self.driver.close()
                raise ValueError("Failed to login")

    @staticmethod
    def __get_headless_option() -> webdriver.chrome.options.Options:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-extensions')
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-browser-side-navigation")
        options.add_argument('--proxy-server="direct://"')
        options.add_argument('--proxy-bypass-list=*')
        options.add_argument('--start-maximized')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--user-agent=' + USER_AGENT)
        options.add_experimental_option(
            "excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
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

    @staticmethod
    def __parse_log(driver: webdriver.chrome.webdriver.WebDriver) -> str:
        messages = [
            json.loads(row.get("message", {})).get("message", {})
            for row in driver.get_log('performance')
        ]

        code = "(None)"
        for message in [_ for _ in messages
                        if _.get("method") == "Network.requestWillBeSent"]:
            url = message.get("params", {}).get("documentURL")
            if url[:8] == "pixiv://":
                _ = re.search(r'code=([^&]*)', url)
                return code if _ is None else _.groups()[0]
        else:
            return code
