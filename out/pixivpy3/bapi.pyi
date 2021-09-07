from .aapi import AppPixivAPI as AppPixivAPI
from typing import Any

class ByPassSniApi(AppPixivAPI):
    requests: Any
    def __init__(self, **requests_kwargs) -> None: ...
    hosts: Any
    def require_appapi_hosts(self, hostname: str = ..., timeout: int = ...): ...
