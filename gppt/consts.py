"""Pixiv API constants."""

from typing import Final

USER_AGENT: Final[str] = "PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)"
CALLBACK_URI: Final[str] = "https://app-api.pixiv.net/web/v1/users/auth/pixiv/callback"
REDIRECT_URI: Final[str] = "https://accounts.pixiv.net/post-redirect"
LOGIN_URL: Final[str] = "https://app-api.pixiv.net/web/v1/login"
AUTH_TOKEN_URL: Final[str] = "https://oauth.secure.pixiv.net/auth/token"  # noqa: S105
CLIENT_ID: Final[str] = "MOBrBDS8blbauoSck0ZfDbtuzpyT"
CLIENT_SECRET: Final[str] = "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj"  # noqa: S105
