"""pixiv OAuth response data types."""

from typing import TypedDict


class ProfileURIs(TypedDict):
    """Profile image URLs for a pixiv user."""

    px_16x16: str
    px_50x50: str
    px_170x170: str


class LoginUserInfo(TypedDict):
    """Account information returned alongside a token."""

    profile_image_urls: ProfileURIs
    id: str
    name: str
    account: str
    mail_address: str
    is_premium: bool
    x_restrict: int
    is_mail_authorized: bool
    require_policy_agreement: bool


class LoginInfo(TypedDict):
    """Body of a successful ``/auth/token`` response."""

    access_token: str
    expires_in: int
    token_type: str
    scope: str
    refresh_token: str
    user: LoginUserInfo
