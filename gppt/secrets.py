"""Resolve ``op://`` secret references via the 1Password CLI (``op read``).

Any profile field that starts with ``op://`` is treated as a 1Password secret
reference and expanded at login time by shelling out to ``op read <ref>``.
Plain values (and empty strings) are returned unchanged, so existing profiles
keep working.
"""

from __future__ import annotations

import shutil
import subprocess

OP_PREFIX = "op://"


def is_op_reference(value: str) -> bool:
    """Whether ``value`` looks like a 1Password secret reference.

    Args:
        value (str): Configured field value.

    Returns:
        bool: True if the value is an ``op://`` reference.
    """
    return value.startswith(OP_PREFIX)


def resolve_secret(value: str) -> str:
    """Return ``value`` verbatim, or expand it via ``op read`` if it is an op:// ref.

    Args:
        value (str): Configured field value.

    Returns:
        str: The resolved secret, or the original value.

    Raises:
        ValueError: If the ``op`` CLI is missing or the reference cannot be read.
    """
    if not is_op_reference(value):
        return value

    if shutil.which("op") is None:
        msg = (
            f"'{value}' is a 1Password reference but the `op` CLI is not installed. "
            "Install the 1Password CLI: https://developer.1password.com/docs/cli/"
        )
        raise ValueError(msg)

    try:
        result = subprocess.run(  # noqa: S603
            ["op", "read", value],  # noqa: S607
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        msg = f"Failed to resolve 1Password reference '{value}': {detail}"
        raise ValueError(msg) from exc

    return result.stdout.strip()
