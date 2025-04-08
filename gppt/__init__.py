""".. include:: ../README.md"""  # noqa: D415

import importlib.metadata

from .auth import PixivAuth
from .gppt import GetPixivToken
from .model_types import (
    LoginCred,
    LoginInfo,
    LoginUserInfo,
    OAuthAPIResponse,
    PixivLoginFailedError,
    ProfileURIs,
)

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"


__all__ = [
    "AUTH_TOKEN_URL",
    "CALLBACK_URI",
    "CLIENT_ID",
    "CLIENT_SECRET",
    "LOGIN_URL",
    "REDIRECT_URI",
    "USER_AGENT",
    "GetPixivToken",
    "LoginCred",
    "LoginInfo",
    "LoginUserInfo",
    "OAuthAPIResponse",
    "PixivAuth",
    "PixivAuth",
    "PixivLoginFailedError",
    "ProfileURIs",
]
