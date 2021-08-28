#!/usr/bin/env python

import argparse
from pprint import pprint
from sys import stderr

from . import selenium as s


def print_auth_token_response(res: dict[str, str]) -> None:
    try:
        access_token = res["access_token"]
        refresh_token = res["refresh_token"]
    except KeyError:
        print("error:")
        pprint(res)
        exit(1)
    print("access_token:", access_token)
    print("refresh_token:", refresh_token)
    print("expires_in:", res.get("expires_in", 0))


def func_login(_: argparse.Namespace) -> None:
    g = s.GetPixivToken()
    print('[!]: The browser will start. Please login.', file=stderr)
    res = g.login()
    print('[+]: Success!', file=stderr)
    print_auth_token_response(res)


def func_refresh(ns:  argparse.Namespace) -> None:
    g = s.GetPixivToken()
    print('[!]: The browser will start. Please login.', file=stderr)
    res = g.refresh(ns.refresh_token)
    print('[+]: Success!', file=stderr)
    print_auth_token_response(res)


def parse() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    def func_help(_:  argparse.Namespace) -> None:
        parser.print_usage()
    parser.set_defaults(func=func_help)

    subparsers = parser.add_subparsers()

    login_parser = subparsers.add_parser("login")
    login_parser.set_defaults(func=func_login)

    refresh_parser = subparsers.add_parser("refresh")
    refresh_parser.add_argument("refresh_token")
    refresh_parser.set_defaults(func=func_refresh)

    return parser.parse_args()


def main() -> None:
    args = parse()
    args.func(args)


if __name__ == "__main__":
    main()
