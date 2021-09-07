from typing import Any, Optional

USER_AGENT: str
CALLBACK_URI: str
REDIRECT_URI: str
LOGIN_URL: str
AUTH_TOKEN_URL: str
CLIENT_ID: str
CLIENT_SECRET: str
REQUESTS_KWARGS: dict[str, Any]

class GetPixivToken:
    caps: Any
    def __init__(self) -> None: ...
    driver: Any
    def login(self, headless: Optional[bool] = ..., user: Optional[str] = ..., pass_: Optional[str] = ...) -> dict[str, str]: ...
    @staticmethod
    def refresh(refresh_token: str) -> dict[str, str]: ...
