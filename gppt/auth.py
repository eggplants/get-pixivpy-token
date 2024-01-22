from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pwinput  # type: ignore[import,unused-ignore]
from pixivpy3 import AppPixivAPI

from .gppt import GetPixivToken
from .types import LoginCred, LoginInfo, PixivLoginFailed


class PixivAuth:
    def __init__(self, auth_json_path: str = "client.json") -> None:
        self.auth_json_path = auth_json_path

    def auth(self) -> tuple[AppPixivAPI, LoginInfo]:
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
        raise PixivLoginFailed

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
            raise PixivLoginFailed

        return (aapi, login_info)

    @staticmethod
    def get_refresh_token(pixiv_id: str, pixiv_pass: str) -> str:
        g = GetPixivToken(headless=True, username=pixiv_id, password=pixiv_pass)
        return g.login()["refresh_token"]

    def read_client_cred(self) -> LoginCred | None:
        path = Path(self.auth_json_path)
        if path.exists():
            cred_data = json.load(path.open())
            if set(cred_data.keys()) == {"pixiv_id", "password"}:
                return cast(LoginCred, cred_data)
            return None
        return None
