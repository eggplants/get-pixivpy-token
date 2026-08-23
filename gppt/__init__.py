""".. include:: ../README.md"""  # noqa: D415

import importlib.metadata

from gppt.api import get_token, login, oauth_login, refresh
from gppt.oauth import LoginError
from gppt.token import Token, TokenError

try:
    __version__ = importlib.metadata.version(__name__)
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.0.0"


__all__ = [
    "LoginError",
    "Token",
    "TokenError",
    "__version__",
    "get_token",
    "login",
    "oauth_login",
    "refresh",
]
