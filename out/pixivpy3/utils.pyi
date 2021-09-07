from typing import Any

class PixivError(Exception):
    reason: Any
    header: Any
    body: Any
    def __init__(self, reason, header: Any | None = ..., body: Any | None = ...) -> None: ...

class JsonDict(dict):
    def __getattr__(self, attr): ...
    def __setattr__(self, attr, value) -> None: ...
