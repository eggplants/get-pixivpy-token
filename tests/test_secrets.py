from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING, Any

import pytest

from gppt import secrets

if TYPE_CHECKING:
    from collections.abc import Sequence


def test_plain_values_pass_through() -> None:
    assert secrets.resolve_secret("hunter2") == "hunter2"
    assert secrets.resolve_secret("") == ""
    assert secrets.is_op_reference("hunter2") is False


def test_op_reference_is_read_via_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Sequence[str]] = []

    def fake_run(args: Sequence[str], **_: Any) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="resolved\n", stderr="")

    monkeypatch.setattr(secrets.shutil, "which", lambda _: "/usr/bin/op")
    monkeypatch.setattr(secrets.subprocess, "run", fake_run)

    assert secrets.resolve_secret("op://vault/item/password") == "resolved"
    assert calls == [["op", "read", "op://vault/item/password"]]


def test_missing_op_cli_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(secrets.shutil, "which", lambda _: None)

    with pytest.raises(ValueError, match="`op` CLI is not installed"):
        secrets.resolve_secret("op://vault/item/password")


def test_op_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: Sequence[str], **_: Any) -> subprocess.CompletedProcess[str]:
        raise subprocess.CalledProcessError(returncode=1, cmd=list(args), stderr="not signed in")

    monkeypatch.setattr(secrets.shutil, "which", lambda _: "/usr/bin/op")
    monkeypatch.setattr(secrets.subprocess, "run", fake_run)

    with pytest.raises(ValueError, match="not signed in"):
        secrets.resolve_secret("op://vault/item/password")
