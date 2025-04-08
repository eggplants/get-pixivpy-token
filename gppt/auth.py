"""Pixiv Authentication module.

This module provides a class for authenticating with the Pixiv API.
It includes methods for reading client credentials from a JSON file,
logging in with a username and password, and retrieving a refresh token.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pwinput  # type: ignore[import,unused-ignore]
from pixivpy3 import AppPixivAPI

from .gppt import GetPixivToken
from .model_types import LoginCred, LoginInfo, PixivLoginFailedError


class PixivAuth:
    """Pixiv Authentication class."""

    def __init__(self, auth_json_path: str = "client.json") -> None:
        """Initialize the PixivAuth class.

        Args:
            auth_json_path (str): Path to the JSON file containing client credentials.
                Defaults to "client.json".
        """
        self.auth_json_path = auth_json_path

    def auth(self) -> tuple[AppPixivAPI, LoginInfo]:
        """Authenticate the user with Pixiv.

        This method attempts to log in to Pixiv using the provided credentials.
        It first checks for existing credentials in a JSON file. If the credentials
        are not found or if the login fails, it prompts the user for their ID and
        password. The method will retry the login process up to three times before
        raising a PixivLoginFailed exception.

        Returns:
            tuple[AppPixivAPI, LoginInfo]: A tuple containing the authenticated
                AppPixivAPI instance and the login information.

        Raises:
            PixivLoginFailed: If the login process fails after three attempts.
        """
        cnt = 0
        while cnt < 3:  # noqa: PLR2004
            try:
                aapi, login_info = self.__auth(cnt)
            except (ValueError, UnboundLocalError):
                print("\x1b[?25h[!]: Failed to login. Check your ID or PW.")
            else:
                return aapi, login_info
            cnt += 1

        print("[!]: The number of login attempts has been exceeded.")
        raise PixivLoginFailedError

    def __auth(self, cnt: int) -> tuple[AppPixivAPI, LoginInfo]:
        aapi: AppPixivAPI = AppPixivAPI()
        login_cred: LoginCred | None = self.read_client_cred()

        if login_cred is not None and cnt == 0:
            ref = self.get_refresh_token(login_cred["pixiv_id"], login_cred["password"])
            print("\x1b[?25l[+]: Login...")
            login_info = aapi.auth(refresh_token=ref)
        elif login_cred is None or cnt > 0:
            print("[+]: ID is mail address, username, or account name.")
            stdin_login = (
                pwinput.pwinput(prompt="[?]: ID: ", mask=" "),
                pwinput.pwinput(prompt="[?]: PW: ", mask=" "),
            )
            print("\x1b[?25l[+]: Login...", end="\r")
            ref = self.get_refresh_token(stdin_login[0], stdin_login[1])
            login_info = aapi.auth(refresh_token=ref)
            print("\033[K[+]: Login...OK!\x1b[?25h")
        else:
            raise PixivLoginFailedError

        return (aapi, login_info)

    @staticmethod
    def get_refresh_token(pixiv_id: str, pixiv_pass: str) -> str:
        """Get the refresh token for the given Pixiv ID and password.

        This method uses the GetPixivToken class to perform the login and
        retrieve the refresh token.

        Args:
            pixiv_id (str): The Pixiv ID (email address, username, or account name).
            pixiv_pass (str): The password for the Pixiv account.

        Returns:
            str: The refresh token for the Pixiv account.
        """
        g = GetPixivToken(headless=True, username=pixiv_id, password=pixiv_pass)
        return g.login()["refresh_token"]

    def read_client_cred(self) -> LoginCred | None:
        """Read the client credentials from the JSON file.

        This method checks if the JSON file containing the client credentials
        exists and attempts to load the credentials. If the credentials are
        successfully loaded and contain the required keys, they are returned
        as a LoginCred object. If the file does not exist or the credentials
        are invalid, None is returned.

        Returns:
            LoginCred | None: The loaded client credentials as a LoginCred object,
                or None if the file does not exist or the credentials are invalid.
        """
        path = Path(self.auth_json_path)
        if path.exists():
            cred_data = json.load(path.open())
            if set(cred_data.keys()) == {"pixiv_id", "password"}:
                return cast("LoginCred", cred_data)
            return None
        return None
