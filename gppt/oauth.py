"""OAuth2 PKCE login: you log in in your own browser and paste the code back.

pixiv's mobile OAuth flow ends by redirecting to a ``pixiv://`` deep link that
carries the authorization code. A desktop browser cannot follow that link, but
the request is still visible in the developer tools -- so instead of automating
a browser (see :mod:`gppt.browser`), this asks the user for the code.

Nothing is typed into pixiv's login form on the user's behalf, so a captcha, a
2FA challenge, or an already-logged-in session are all handled by the browser
the user already trusts.

Based on:
- https://github.com/mikf/gallery-dl/blob/master/gallery_dl/extractor/oauth.py
- https://github.com/modenicheng/pixiv-api/blob/master/pixiv-dl/src/main.rs
"""

from __future__ import annotations

import sys
import webbrowser
from base64 import urlsafe_b64encode
from dataclasses import dataclass
from hashlib import sha256
from secrets import token_urlsafe
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlencode, urlsplit

from gppt.consts import LOGIN_URL

if TYPE_CHECKING:
    from collections.abc import Callable

INSTRUCTIONS = """\
=== pixiv OAuth2 (PKCE) login ===

1. Open this URL in your browser (it may have been opened for you):

   {url}

2. Open the developer tools (F12), switch to the Network tab and tick
   "Preserve log".
3. Log in to pixiv.
4. Find the last entry -- `callback?state=...&code=...`, or a `pixiv://` URL.
5. Paste its `code` value below and press Enter. The whole URL works too.

The code expires about 30 seconds after you log in, so do not linger.
"""


class LoginError(RuntimeError):
    """Raised when a login does not yield an authorization code."""


@dataclass
class Authorization:
    """An authorization code plus the PKCE verifier it must be exchanged with."""

    code: str
    code_verifier: str


def generate_pkce() -> tuple[str, str]:
    """Generate a PKCE verifier/challenge pair (RFC 7636, S256).

    Returns:
        tuple[str, str]: The code verifier and its S256 challenge.
    """
    code_verifier = token_urlsafe(32)
    digest = urlsafe_b64encode(sha256(code_verifier.encode("ascii")).digest()).rstrip(b"=")
    return code_verifier, digest.decode("ascii")


def build_login_url(code_challenge: str) -> str:
    """Return the pixiv login URL that ends in a ``pixiv://`` callback.

    Args:
        code_challenge (str): S256 challenge from :func:`generate_pkce`.

    Returns:
        str: The URL to open in a browser.
    """
    params = {
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "client": "pixiv-android",
    }
    return f"{LOGIN_URL}?{urlencode(params)}"


def extract_code(text: str) -> str:
    """Pull the authorization code out of whatever the user pasted.

    Accepts the bare code, a ``code=...`` fragment, or a full callback URL --
    ``pixiv://account/login?code=...`` as well as the ``.../callback?state=...``
    one, whose ``code`` is not the first query parameter.

    Args:
        text (str): The pasted text.

    Returns:
        str: The authorization code.

    Raises:
        LoginError: If no code can be found.
    """
    pasted = text.strip()
    if not pasted:
        msg = "No authorization code was given."
        raise LoginError(msg)

    if "=" in pasted:
        # Everything after the first '?' is the query string; a bare
        # `code=...&state=...` fragment has no '?' and is a query string already.
        query = pasted.partition("?")[2] if "?" in pasted else pasted
        codes = parse_qs(urlsplit(f"?{query}").query).get("code", [])
        code = codes[0].strip() if codes else ""
    else:
        code = pasted

    if not code or any(character.isspace() for character in code):
        msg = (
            f"Could not find an authorization code in {pasted!r}. "
            "Paste the `code` query parameter, or the whole callback URL."
        )
        raise LoginError(msg)
    return code


def request_authorization(
    *,
    open_browser: bool = True,
    prompt: Callable[[str], str] | None = None,
    notify: Callable[[str], None] | None = None,
) -> Authorization:
    """Walk the user through the OAuth2 PKCE flow and return their code.

    Args:
        open_browser (bool): Also try to open the login URL in the user's
            default browser. It is printed either way.
        prompt (Callable[[str], str] | None): Called with a prompt string to
            read the pasted code. Defaults to reading a line from stdin, with
            the prompt itself written to stderr.
        notify (Callable[[str], None] | None): Called with the instructions and
            the login URL. Defaults to writing to stderr -- the user cannot
            complete this flow without seeing them.

    Returns:
        Authorization: The pasted code and the PKCE verifier it belongs to.

    Raises:
        LoginError: If the pasted text carries no authorization code.
    """
    ask = prompt or _ask
    say = notify or _to_stderr

    code_verifier, code_challenge = generate_pkce()
    url = build_login_url(code_challenge)

    say(INSTRUCTIONS.format(url=url))
    if open_browser and not _open_in_browser(url):
        say("(Could not open a browser for you -- please open the URL above yourself.)")

    return Authorization(code=extract_code(ask("code: ")), code_verifier=code_verifier)


def _ask(prompt_text: str) -> str:
    """Read a line from stdin, prompting on stderr so stdout stays pipeable."""
    print(prompt_text, end="", file=sys.stderr, flush=True)  # noqa: T201
    return input()


def _to_stderr(message: str) -> None:
    print(message, file=sys.stderr)  # noqa: T201


def _open_in_browser(url: str) -> bool:
    """Try to open ``url`` in the user's default browser, reporting whether it worked."""
    try:
        return webbrowser.open(url)
    except webbrowser.Error:
        return False
