"""Exchange a pixiv authorization code for OAuth tokens and cache them on disk."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Final, cast
from urllib.request import getproxies

import requests

from gppt import config
from gppt.consts import AUTH_TOKEN_URL, CALLBACK_URI, CLIENT_ID, CLIENT_SECRET, USER_AGENT

if TYPE_CHECKING:
    from pathlib import Path

    from gppt.browser import Authorization
    from gppt.model_types import LoginInfo

TIMEOUT: Final = 10.0

# Treat a token that is about to lapse as already expired, so a cached one is
# never handed out with only seconds of life left.
EXPIRY_MARGIN: Final = timedelta(minutes=1)

_HEADERS: Final[dict[str, str]] = {
    "user-agent": USER_AGENT,
    "app-os-version": "14.6",
    "app-os": "ios",
}


class TokenError(RuntimeError):
    """Raised when the pixiv OAuth endpoint does not return a token."""


@dataclass
class Token:
    """A pixiv OAuth token pair with its absolute expiry time."""

    access_token: str
    refresh_token: str
    expires_in: int
    expires_at: str  # ISO 8601, absolute; `expires_in` is only relative to issue time
    user_id: str = ""
    user_name: str = ""
    user_account: str = ""

    @property
    def is_expired(self) -> bool:
        """Whether the access token has lapsed (or is about to).

        Returns:
            bool: True if the token should no longer be used.
        """
        try:
            expires_at = datetime.fromisoformat(self.expires_at)
        except ValueError:
            return True
        return _now() + EXPIRY_MARGIN >= expires_at

    @classmethod
    def from_response(cls, response: LoginInfo) -> Token:
        """Build a token from a pixiv OAuth response.

        Args:
            response (LoginInfo): Decoded response body.

        Returns:
            Token: The parsed token.

        Raises:
            TokenError: If the response carries no access token.
        """
        body = cast("dict[str, Any]", response)
        if "access_token" not in body:
            msg = f"pixiv did not return a token: {json.dumps(body, ensure_ascii=False)}"
            raise TokenError(msg)

        expires_in = int(body.get("expires_in", 0))
        user = body.get("user") or {}
        return cls(
            access_token=body["access_token"],
            refresh_token=body.get("refresh_token", ""),
            expires_in=expires_in,
            expires_at=(_now() + timedelta(seconds=expires_in)).isoformat(),
            user_id=str(user.get("id", "")),
            user_name=str(user.get("name", "")),
            user_account=str(user.get("account", "")),
        )


def exchange(authorization: Authorization) -> Token:
    """Exchange an authorization code for a token pair.

    Args:
        authorization (Authorization): Code and PKCE verifier from the browser login.

    Returns:
        Token: The issued token.

    Raises:
        TokenError: If pixiv rejects the exchange.
    """
    return Token.from_response(
        _post(
            {
                "code": authorization.code,
                "code_verifier": authorization.code_verifier,
                "grant_type": "authorization_code",
                "redirect_uri": CALLBACK_URI,
            },
        ),
    )


def refresh(refresh_token: str) -> Token:
    """Obtain a fresh token pair from a refresh token.

    Args:
        refresh_token (str): Refresh token from a previous login.

    Returns:
        Token: The issued token.

    Raises:
        TokenError: If pixiv rejects the refresh token.
    """
    return Token.from_response(
        _post(
            {
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        ),
    )


def load(profile: str) -> Token | None:
    """Read the profile's cached token, if any.

    Args:
        profile (str): Profile name.

    Returns:
        Token | None: The cached token, or None if absent or unreadable.
    """
    path = config.token_path(profile)
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as fp:
            data = json.load(fp)
    except (OSError, json.JSONDecodeError):
        return None
    known = {field: data[field] for field in Token.__dataclass_fields__ if field in data}
    try:
        return Token(**known)
    except TypeError:
        return None


def save(profile: str, token: Token) -> Path:
    """Write the profile's token cache.

    Args:
        profile (str): Profile name.
        token (Token): Token to store.

    Returns:
        Path: Path the token was written to.
    """
    config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = config.token_path(profile)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(asdict(token), fp, indent=2, ensure_ascii=False)
        fp.write("\n")
    # Anyone holding these can act as the account -- keep them private.
    path.chmod(0o600)
    return path


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _post(payload: dict[str, str]) -> LoginInfo:
    response = requests.post(
        AUTH_TOKEN_URL,
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "include_policy": "true",
            **payload,
        },
        headers=_HEADERS,
        proxies=getproxies(),
        timeout=TIMEOUT,
    )
    return cast("LoginInfo", response.json())
