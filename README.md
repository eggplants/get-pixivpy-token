# `gppt`: get-pixivpy-token

[![PyPI](
  <https://img.shields.io/pypi/v/gppt?color=blue>
  )](
  <https://pypi.org/project/gppt/>
) [![ghcr](
  <https://ghcr-badge.egpl.dev/eggplants/get-pixivpy-token/size>
  )](
  <https://github.com/eggplants/get-pixivpy-token/pkgs/container/get-pixivpy-token>
) [![ci](
  <https://github.com/eggplants/get-pixivpy-token/actions/workflows/ci.yml/badge.svg>
  )](
  <https://github.com/eggplants/get-pixivpy-token/actions/workflows/ci.yml>
)

- Get your Pixiv token (for running [upbit/pixivpy](https://github.com/upbit/pixivpy))
- Refine [pixiv_auth.py](https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362) + [its fork](https://gist.github.com/upbit/6edda27cb1644e94183291109b8a5fde)

> [!IMPORTANT]
> v5 is a rewrite: the CLI is now just `gppt configure` and `gppt login`, and
> `GetPixivToken` / `PixivAuth` are replaced by `gppt.login()` and
> `gppt.get_token()`. See [UPGRADE-v5.md](./UPGRADE-v5.md) if you are coming
> from v4.

## Install

```bash
pip install gppt
```

## Usage

`gppt` has two commands: `configure` stores an account in a profile, `login` gets you a token.

```bash
# Configure a profile (writes to: ~/.config/gppt/<profile>.json by default)
gppt configure

# Log in (writes to: ~/.config/gppt/<profile>.token.json by default)
gppt login
```

`~/.config/gppt/<profile>.json`:

```json
{
  "username": "<plain username or op:// link>",
  "password": "<plain password or op:// link>",
  "totp_secret": "<base32 secret, otpauth:// URI, or op:// link>"
}
```

`~/.config/gppt/<profile>.token.json`:

```json
{
  "access_token": "***",
  "refresh_token": "***",
  "expires_in": 3600,
  "expires_at": "2026-08-08T16:34:57.776005+00:00",
  "user_id": "***",
  "user_name": "***",
  "user_account": "***"
}
```

### Two-factor authentication

If your account has 2FA enabled, pixiv asks for a verification code after the
password. `gppt` fills it in from `totp_secret` — the base32 secret pixiv shows
you when you set up an authenticator app, the `otpauth://` URI behind its QR
code, or an `op://` reference to either. This is what makes an unattended
headless login possible on a 2FA account.

Leave `totp_secret` blank and `gppt login` prompts for a code on stdin instead,
only when pixiv actually asks for one. Accounts without 2FA are unaffected.

### Environment variables

| Variable | Effect |
| --- | --- |
| `GPPT_USERNAME`, `GPPT_PASSWORD`, `GPPT_TOTP_SECRET` | Override the profile's credentials — lets a container or CI job log in with no config file |
| `GPPT_CONFIG_DIR` | Directory holding profiles and cached tokens (default: `$XDG_CONFIG_HOME/gppt`) |
| `ALL_PROXY`, `HTTPS_PROXY`, `HTTP_PROXY` | Proxy used by both the browser and the token requests |

### From Python

`gppt.get_token()` is the library form of `gppt login`: it reuses the cached
token, refreshes it, or opens the browser if needed.

```python
import gppt
from pixivpy3 import AppPixivAPI

token = gppt.get_token()  # profile "default", configured with `gppt configure`

aapi = AppPixivAPI()
aapi.auth(refresh_token=token.refresh_token)
```

It is silent by default; pass `notify=print` to see the same progress messages
the CLI writes.

For a one-off login that reads and writes nothing on disk, use `gppt.login()`:

```python
token = gppt.login(username="...", password="...")
token.access_token, token.refresh_token, token.expires_in
```

For a 2FA account, pass the TOTP secret — or a `totp_prompt` callable that is
invoked only if pixiv asks for a code:

```python
token = gppt.login("...", "...", "JBSWY3DPEHPK3PXP")
token = gppt.login("...", "...", totp_prompt=lambda: input("code: "))
```

And `gppt.refresh()` exchanges a refresh token you are storing yourself:

```python
token = gppt.refresh("...")
```

| Name | Purpose |
| --- | --- |
| `gppt.get_token(profile="default", *, headless=True, force=False, save=True, notify=None, totp_prompt=None)` | A valid token for a stored profile, logging in only if needed |
| `gppt.login(username="", password="", totp_secret="", *, headless=None, totp_prompt=None)` | One browser login; no files touched |
| `gppt.refresh(refresh_token)` | Refresh token → new token |
| `gppt.Token` | Result dataclass: `access_token`, `refresh_token`, `expires_in`, `expires_at`, `is_expired`, `user_id`, `user_name`, `user_account` |
| `gppt.LoginError`, `gppt.TokenError` | Raised when the browser login fails / pixiv rejects the request |
