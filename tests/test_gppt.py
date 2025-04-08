from __future__ import annotations

from gppt import __version__


def test_check_version() -> None:
    assert __version__ is not None
