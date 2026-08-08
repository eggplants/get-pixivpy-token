"""Profile configuration stored at ``~/.config/gppt/<profile>.json``."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

CONFIG_DIR = Path(
    os.environ.get("GPPT_CONFIG_DIR") or (Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "gppt"),
)

DEFAULT_PROFILE = "default"

USERNAME_ENV = "GPPT_USERNAME"
PASSWORD_ENV = "GPPT_PASSWORD"  # noqa: S105
TOTP_SECRET_ENV = "GPPT_TOTP_SECRET"  # noqa: S105


@dataclass
class ProfileConfig:
    """A single pixiv account's login settings."""

    # Credentials -- if both are present the browser login runs unattended.
    # Either may be an ``op://`` 1Password reference resolved at login time.
    username: str = ""  # e-mail address, pixiv ID, or account name
    password: str = ""  # pixiv account password
    # Base32 secret or otpauth:// URI, for accounts with two-factor
    # authentication enabled. Empty means "ask when pixiv asks".
    totp_secret: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProfileConfig:
        """Build a config from a JSON object, ignoring unknown keys.

        Args:
            data (dict[str, Any]): Decoded JSON object.

        Returns:
            ProfileConfig: The parsed configuration.
        """
        known = {field: data[field] for field in cls.__dataclass_fields__ if field in data}
        return cls(**known)

    def to_dict(self) -> dict[str, Any]:
        """Return the config as a JSON-serialisable object.

        Returns:
            dict[str, Any]: The serialisable configuration.
        """
        return asdict(self)


def profile_path(profile: str) -> Path:
    """Return the path of the profile's configuration file.

    Args:
        profile (str): Profile name.

    Returns:
        Path: Path to ``<config dir>/<profile>.json``.
    """
    return CONFIG_DIR / f"{profile}.json"


def token_path(profile: str) -> Path:
    """Return the path of the profile's cached token file.

    Args:
        profile (str): Profile name.

    Returns:
        Path: Path to ``<config dir>/<profile>.token.json``.
    """
    return CONFIG_DIR / f"{profile}.token.json"


def load(profile: str) -> ProfileConfig:
    """Load the profile's configuration file.

    Args:
        profile (str): Profile name.

    Returns:
        ProfileConfig: The stored configuration.

    Raises:
        FileNotFoundError: If the profile has not been configured yet.
    """
    path = profile_path(profile)
    if not path.exists():
        msg = f"No configuration for profile '{profile}'. Run `gppt configure --profile {profile}` first."
        raise FileNotFoundError(msg)
    with path.open(encoding="utf-8") as fp:
        return ProfileConfig.from_dict(json.load(fp))


def load_or_default(profile: str) -> ProfileConfig:
    """Load the profile's configuration, falling back to an empty one.

    ``GPPT_USERNAME`` / ``GPPT_PASSWORD`` / ``GPPT_TOTP_SECRET`` override the
    stored values so a throwaway environment (a container, CI) can log in
    without a config file.

    Args:
        profile (str): Profile name.

    Returns:
        ProfileConfig: The stored configuration with environment overrides
            applied, or an all-default configuration if none is stored.
    """
    try:
        config = load(profile)
    except FileNotFoundError:
        config = ProfileConfig()

    config.username = os.environ.get(USERNAME_ENV) or config.username
    config.password = os.environ.get(PASSWORD_ENV) or config.password
    config.totp_secret = os.environ.get(TOTP_SECRET_ENV) or config.totp_secret
    return config


def save(profile: str, config: ProfileConfig) -> Path:
    """Write the profile's configuration file.

    Args:
        profile (str): Profile name.
        config (ProfileConfig): Configuration to store.

    Returns:
        Path: Path the configuration was written to.
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    path = profile_path(profile)
    with path.open("w", encoding="utf-8") as fp:
        json.dump(config.to_dict(), fp, indent=2, ensure_ascii=False)
        fp.write("\n")
    # The config may hold a plaintext password -- keep it private.
    path.chmod(0o600)
    return path
