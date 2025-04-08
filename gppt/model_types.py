"""Pixiv login related data types."""

from typing import TypedDict


class PixivLoginFailedError(Exception):
    """Custom exception for Pixiv login failures."""


class LoginCred(TypedDict):
    """Login credentials for Pixiv."""

    pixiv_id: str
    password: str


class ProfileURIs(TypedDict):
    """Profile image URLs for Pixiv user."""

    px_16x16: str
    px_50x50: str
    px_170x170: str


class LoginUserInfo(TypedDict):
    """Login user information for Pixiv."""

    profile_image_urls: ProfileURIs
    id: str
    name: str
    account: str
    mail_address: str
    is_premium: bool
    x_restrict: int
    is_mail_authorized: bool
    require_policy_agreement: bool


class OAuthAPIResponse(TypedDict):
    """OAuth API response for Pixiv login."""

    access_token: str
    expires_in: int
    token_type: str
    scope: str
    refresh_token: str
    user: LoginUserInfo


class LoginInfo(TypedDict):
    """Login information for Pixiv."""

    access_token: str
    expires_in: int
    token_type: str
    scope: str
    refresh_token: str
    user: LoginUserInfo
    response: OAuthAPIResponse
