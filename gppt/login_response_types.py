from typing import TypedDict


class PixivLoginFailed(Exception):
    pass


class LoginCred(TypedDict):
    pixiv_id: str
    password: str


class ProfileURIs(TypedDict):
    px_16x16: str
    px_50x50: str
    px_170x170: str


class LoginUserInfo(TypedDict):
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
    access_token: str
    expires_in: int
    token_type: str
    scope: str
    refresh_token: str
    user: LoginUserInfo


class LoginInfo(TypedDict):
    access_token: str
    expires_in: int
    token_type: str
    scope: str
    refresh_token: str
    user: LoginUserInfo
    response: OAuthAPIResponse
