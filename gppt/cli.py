"""Command-line interface: ``gppt configure`` and ``gppt login``."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import TYPE_CHECKING

from gppt import api, config, token
from gppt.browser import LoginError

if TYPE_CHECKING:
    from gppt.token import Token


def main(argv: list[str] | None = None) -> int:
    """Run the command-line interface.

    Args:
        argv (list[str] | None): Argument vector, or None to read ``sys.argv``.

    Returns:
        int: Process exit code.
    """
    parser = argparse.ArgumentParser(
        prog="gppt",
        description="Get your pixiv token (for running upbit/pixivpy).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    conf = sub.add_parser("configure", help="Create/update a profile interactively.")
    _add_profile_argument(conf)
    conf.set_defaults(func=cmd_configure)

    login = sub.add_parser("login", help="Log in and print/store pixiv tokens.")
    _add_profile_argument(login)
    login.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        help="Show the browser window. The default is a headless run.",
    )
    login.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Ignore the cached token and log in through the browser again.",
    )
    login.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Print the token as JSON.",
    )
    login.set_defaults(func=cmd_login)

    args = parser.parse_args(argv)
    try:
        exit_code: int = args.func(args)
    except (LoginError, token.TokenError, FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print("\naborted", file=sys.stderr)
        return 130
    return exit_code


def _add_profile_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-p",
        "--profile",
        default=config.DEFAULT_PROFILE,
        help=f"Profile name (default: {config.DEFAULT_PROFILE}).",
    )


def _prompt(text: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return input(f"{text}{suffix}: ").strip() or default


def cmd_configure(args: argparse.Namespace) -> int:
    """Create or update a profile interactively.

    Args:
        args (argparse.Namespace): Parsed ``configure`` arguments.

    Returns:
        int: Process exit code.
    """
    try:
        existing = config.load(args.profile)
    except FileNotFoundError:
        existing = config.ProfileConfig()

    print(f"Configuring profile '{args.profile}'. Press Enter to keep the current value.\n")
    print("Tip: every field accepts a 1Password reference (op://...), resolved via")
    print("`op read` at login time instead of storing the secret itself.\n")
    print("All are optional. Without a username and password, a browser window opens")
    print("for a manual login. Values are stored in plaintext (file mode 0600) unless")
    print("you use an op:// reference.\n")

    username = _prompt("pixiv ID / e-mail address (or op://...)", existing.username)
    password = getpass.getpass("pixiv password (optional, hidden; op:// allowed): ").strip() or existing.password
    print("\nIf your account has two-factor authentication enabled, store its TOTP secret")
    print("to log in unattended. Leave it blank to be asked for a code at login time.")
    totp_secret = (
        getpass.getpass("TOTP secret or otpauth:// URI (optional, hidden; op:// allowed): ").strip()
        or existing.totp_secret
    )

    path = config.save(
        args.profile,
        config.ProfileConfig(username=username, password=password, totp_secret=totp_secret),
    )
    print(f"\nSaved: {path}")
    return 0


def cmd_login(args: argparse.Namespace) -> int:
    """Log in to pixiv and store the resulting tokens.

    A cached token is reused while it is still valid, then refreshed via its
    refresh token, and only then is the browser opened.

    Args:
        args (argparse.Namespace): Parsed ``login`` arguments.

    Returns:
        int: Process exit code.
    """
    issued = api.get_token(
        args.profile,
        headless=args.headless,
        force=args.force,
        notify=_to_stderr,
        totp_prompt=_prompt_totp,
    )

    path = config.token_path(args.profile)
    _print_token(issued, as_json=args.json)
    if issued.user_name:
        print(f"Logged in as: {issued.user_name} (@{issued.user_account})", file=sys.stderr)
    print(f"Token expires at: {issued.expires_at}", file=sys.stderr)
    print(f"Saved to: {path} (profile '{args.profile}')", file=sys.stderr)
    return 0


def _to_stderr(message: str) -> None:
    print(message, file=sys.stderr)


def _prompt_totp() -> str:
    """Ask for a verification code, for a 2FA account with no stored TOTP secret."""
    print("pixiv is asking for a two-factor verification code.", file=sys.stderr)
    return input("Verification code: ").strip()


def _print_token(issued: Token, *, as_json: bool) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "access_token": issued.access_token,
                    "refresh_token": issued.refresh_token,
                    "expires_in": issued.expires_in,
                    "expires_at": issued.expires_at,
                },
                indent=4,
            ),
        )
        return

    print("access_token:", issued.access_token)
    print("refresh_token:", issued.refresh_token)
    print("expires_in:", issued.expires_in)


if __name__ == "__main__":
    raise SystemExit(main())
