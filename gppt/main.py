#!/usr/bin/env python

import argparse
from json import dumps
from pprint import pprint
from sys import stderr
from typing import Optional

from .selenium import GetPixivToken


def print_auth_token_response(res: dict[str, str],
                              json: Optional[bool] = False) -> None:
    try:
        access_token = res["access_token"]
        refresh_token = res["refresh_token"]
        expires_in = res.get("expires_in", 0)
    except KeyError:
        print("error:")
        pprint(res)
        exit(1)

    if json:
        print(dumps({
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_in": expires_in
        }, indent=4))
    else:
        print("access_token:", access_token)
        print("refresh_token:", refresh_token)
        print("expires_in:", expires_in)


def func_login(ns: argparse.Namespace) -> None:
    g = GetPixivToken()
    print('[!]: The browser will start. Please login.', file=stderr)
    res = g.login(user=ns.username,                  pass_=ns.password)
    print('[+]: Success!', file=stderr)
    print_auth_token_response(res, json=ns.json)


def func_loginh(ns: argparse.Namespace) -> None:
    g = GetPixivToken()
    print('[!]: The browser will start.', file=stderr)
    res = g.login(headless=True,
                  user=ns.username,
                  pass_=ns.password)
    print('[+]: Success!', file=stderr)
    print_auth_token_response(res, json=ns.json)


def func_refresh(ns: argparse.Namespace) -> None:
    g = GetPixivToken()
    print('[!]: Chrome browser will be launched. Please login.', file=stderr)
    res = g.refresh(ns.refresh_token)
    print('[+]: Success!', file=stderr)
    print_auth_token_response(res, json=ns.json)


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='gppt',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='Get your Pixiv token (for running upbit/pixivpy)')

    parser.set_defaults(func=lambda _: parser.print_usage())

    subparsers = parser.add_subparsers()

    login_parser = subparsers.add_parser("login", aliases=["l"],
                                         help="retrieving auth token")
    login_parser.add_argument("-u", "--username", metavar="USERNAME", type=str,
                              help="your E-mail address / pixiv ID")
    login_parser.add_argument("-p", "--password", metavar="PASSWORD", type=str,
                              help="your current pixiv password")
    login_parser.add_argument("-j", "--json", action="store_true",
                              help="output response as json")
    login_parser.set_defaults(func=func_login)

    loginh_parser = subparsers.add_parser("login-headless", aliases=["lh"],
                                          help="`login` in headless mode")
    loginh_parser.add_argument("-u", "--username", metavar="USERNAME",
                               type=str, required=True,
                               help="your E-mail address / pixiv ID")
    loginh_parser.add_argument("-p", "--password", metavar="PASSWORD",
                               type=str, required=True,
                               help="your current pixiv password")
    loginh_parser.add_argument("-j", "--json", action="store_true",
                               help="output response as json")
    loginh_parser.set_defaults(func=func_loginh)

    refresh_parser = subparsers.add_parser("refresh", aliases=["r"],
                                           help="refresh tokens")
    refresh_parser.add_argument("-j", "--json", action="store_true",
                                help="output response as json")
    refresh_parser.add_argument("refresh_token")
    refresh_parser.set_defaults(func=func_refresh)

    return parser.parse_args()


def main() -> None:
    args = parse()
    args.func(args)


if __name__ == "__main__":
    main()
