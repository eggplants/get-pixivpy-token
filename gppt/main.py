from __future__ import annotations

import argparse
from json import dumps
from pprint import pprint
from sys import stderr

from ._selenium import GetPixivToken
from .auth import PixivAuth
from .login_response_types import LoginInfo


def print_auth_token_response(res: LoginInfo, json: bool | None = False) -> None:
    try:
        access_token = res["access_token"]
        refresh_token = res["refresh_token"]
        expires_in = res.get("expires_in", 0)
    except KeyError:
        print("error:")
        pprint(res)
        exit(1)

    if json:
        print(
            dumps(
                {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": expires_in,
                },
                indent=4,
            )
        )
    else:
        print("access_token:", access_token)
        print("refresh_token:", refresh_token)
        print("expires_in:", expires_in)


def func_login(ns: argparse.Namespace) -> None:
    g = GetPixivToken()
    print("[!]: Chrome browser will be launched. Please login.", file=stderr)
    res = g.login(username=ns.username, password=ns.password)
    print("[+]: Success!", file=stderr)
    print_auth_token_response(res, json=ns.json)


def func_logini(ns: argparse.Namespace) -> None:
    a = PixivAuth()
    _, res = a.auth()
    print("[+]: Success!", file=stderr)
    print_auth_token_response(res, json=ns.json)


def func_loginh(ns: argparse.Namespace) -> None:
    g = GetPixivToken()
    res = g.login(headless=True, username=ns.username, password=ns.password)
    print("[+]: Success!", file=stderr)
    print_auth_token_response(res, json=ns.json)


def func_refresh(ns: argparse.Namespace) -> None:
    g = GetPixivToken()
    res = g.refresh(ns.refresh_token)
    print("[+]: Success!", file=stderr)
    print_auth_token_response(res, json=ns.json)


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="gppt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description="Get your Pixiv token (for running upbit/pixivpy)",
    )

    parser.set_defaults(func=lambda _: parser.print_usage())

    subparsers = parser.add_subparsers()

    login_parser = subparsers.add_parser(
        "login", aliases=["l"], help="retrieving auth token"
    )
    login_parser.add_argument(
        "-u",
        "--username",
        metavar="USERNAME",
        type=str,
        help="your E-mail address / pixiv ID",
    )
    login_parser.add_argument(
        "-p",
        "--password",
        metavar="PASSWORD",
        type=str,
        help="your current pixiv password",
    )
    login_parser.add_argument(
        "-j", "--json", action="store_true", help="output response as json"
    )
    login_parser.set_defaults(func=func_login)

    logini_parser = subparsers.add_parser(
        "login-interactive", aliases=["li"], help="`login` in interactive mode"
    )
    logini_parser.add_argument(
        "-j", "--json", action="store_true", help="output response as json"
    )
    logini_parser.set_defaults(func=func_logini)

    loginh_parser = subparsers.add_parser(
        "login-headless", aliases=["lh"], help="`login` in headless mode"
    )
    loginh_parser.add_argument(
        "-u",
        "--username",
        metavar="USERNAME",
        type=str,
        required=True,
        help="your E-mail address / pixiv ID",
    )
    loginh_parser.add_argument(
        "-p",
        "--password",
        metavar="PASSWORD",
        type=str,
        required=True,
        help="your current pixiv password",
    )
    loginh_parser.add_argument(
        "-j", "--json", action="store_true", help="output response as json"
    )
    loginh_parser.set_defaults(func=func_loginh)

    refresh_parser = subparsers.add_parser(
        "refresh", aliases=["r"], help="refresh tokens"
    )
    refresh_parser.add_argument(
        "-j", "--json", action="store_true", help="output response as json"
    )
    refresh_parser.add_argument("refresh_token")
    refresh_parser.set_defaults(func=func_refresh)

    return parser.parse_args()


def main() -> None:
    args = parse()
    args.func(args)


if __name__ == "__main__":
    main()
