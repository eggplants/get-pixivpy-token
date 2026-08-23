"""Command-line interface: ``gppt configure`` and ``gppt login``."""

from __future__ import annotations

import argparse
import getpass
import json
import sys
from typing import TYPE_CHECKING

from gppt import __version__, api, config, token
from gppt.oauth import LoginError

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
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
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
    method = login.add_mutually_exclusive_group()
    method.add_argument(
        "--e2e",
        dest="method",
        action="store_const",
        const=config.AUTH_E2E,
        help="Log in by driving a browser with the profile's stored credentials.",
    )
    method.add_argument(
        "--oauth",
        dest="method",
        action="store_const",
        const=config.AUTH_OAUTH,
        help=(
            "Log in through the OAuth2 PKCE flow: open pixiv in your own browser and paste "
            "the code back. Makes --no-headless irrelevant."
        ),
    )
    login.set_defaults(func=cmd_login, method=None)

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

    auth_method = _prompt_auth_method(existing.auth_method)
    credentials = _prompt_credentials(existing, method=auth_method)

    path = config.save(
        args.profile,
        config.ProfileConfig(
            username=credentials.username,
            password=credentials.password,
            totp_secret=credentials.totp_secret,
            auth_method=auth_method,
        ),
    )
    print(f"\nSaved: {path}")
    return 0


def _prompt_auth_method(default: str) -> str:
    """Ask which login method the profile should use, re-asking until it is a known one."""
    print("Authentication method:")
    print(f"  {config.AUTH_E2E:<6} gppt drives a headless browser and types the credentials below.")
    print("         Unattended, but it downloads Chromium and stores your password.")
    print(f"  {config.AUTH_OAUTH:<6} you log in in your own browser and paste the code back (OAuth2 PKCE).")
    print("         No credentials are stored, but you have to be there for each login.")

    methods = "/".join(config.AUTH_METHODS)
    # Not normalize_auth_method(): a profile with an unreadable method is exactly
    # what `gppt configure` is here to fix, so it must not raise on the way in.
    suggested = default.strip().lower()
    if suggested not in config.AUTH_METHODS:
        suggested = config.AUTH_E2E

    while True:
        answer = _prompt(f"\nAuthentication method ({methods})", suggested).strip().lower()
        if answer in config.AUTH_METHODS:
            return answer
        print(f"  Unknown authentication method '{answer}'. Expected one of: {methods}.")


def _prompt_credentials(existing: config.ProfileConfig, *, method: str) -> config.ProfileConfig:
    """Ask for the credentials the chosen method needs, keeping the stored ones otherwise."""
    if method == config.AUTH_OAUTH:
        if existing.username or existing.password or existing.totp_secret:
            print(f"\nKeeping the stored credentials ('{config.AUTH_OAUTH}' does not use them).")
            print(f"Re-run `gppt configure` and pick '{config.AUTH_E2E}' to change them.")
        return existing

    print("\nTip: every field accepts a 1Password reference (op://...), resolved via")
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
    return config.ProfileConfig(username=username, password=password, totp_secret=totp_secret)


def cmd_login(args: argparse.Namespace) -> int:
    """Log in to pixiv and store the resulting tokens.

    A cached token is reused while it is still valid, then refreshed via its
    refresh token, and only then is a login started -- by the profile's
    configured method, unless ``--e2e`` / ``--oauth`` says otherwise.

    Args:
        args (argparse.Namespace): Parsed ``login`` arguments.

    Returns:
        int: Process exit code.
    """
    issued = api.get_token(
        args.profile,
        method=args.method,
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
