#!/usr/bin/env python

import json
import re
import time
from base64 import urlsafe_b64encode
from hashlib import sha256
from secrets import token_urlsafe
from typing import Any
from urllib.parse import urlencode

import requests

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

# Original: https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362

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
    def __init__(self, headless: bool = False) -> None:
        caps = DesiredCapabilities.CHROME.copy()
        caps["goog:loggingPrefs"] = {
            "performance": "ALL"}  # enable performance logs
        if headless:
            opts = self.__get_headless_option()
            self.driver = webdriver.Chrome(
                options=opts, desired_capabilities=caps)

        else:
            self.driver = webdriver.Chrome(desired_capabilities=caps)

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
        options.add_argument('--user-agent=' + USER_AGENT)
        options.add_experimental_option(
            "excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        return options

    @staticmethod
    def __parse_log(driver: webdriver.chrome.webdriver.WebDriver) -> str:
        code = "(None)"
        for row in driver.get_log('performance'):
            message = json.loads(row.get("message", {})).get("message", {})
            if message.get("method") == "Network.requestWillBeSent":
                url = message.get("params", {}).get("documentURL")
                if url[:8] == "pixiv://":
                    _ = re.search(r'code=([^&]*)', url)
                    return code if _ is None else _.groups()[0]
        else:
            return code

    def login(self) -> dict[str, str]:

        code_verifier, code_challenge = self.__oauth_pkce()
        login_params = {
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "client": "pixiv-android",
        }

        self.driver.get(f"{LOGIN_URL}?{urlencode(login_params)}")

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
    def refresh(refresh_token: str) -> dict[str, str]:
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
