# Upgrading from v4 to v5

v5 is a rewrite. The CLI is now exactly two commands — `gppt configure` and
`gppt login`, and the Python API has been rebuilt on top of the same pieces.

## What v5 adds

- **Profiles.** `-p/--profile` keeps several pixiv accounts side by side, each
  with its own config and cached token. `GPPT_CONFIG_DIR` moves the directory.
- **A token cache**, so repeated logins are instant and rarely touch pixiv's
  login form. See [step 3](#3-drop-gppt-refresh).
- **1Password references.** Any credential may be stored as
  `op://Vault/item/field` instead of the secret itself; it is expanded with
  `op read` at login time, so nothing sensitive is written to disk.
- **Two-factor authentication.** v4 could not get past pixiv's verification-code
  screen unattended. v5 takes a `totp_secret` (base32 secret or `otpauth://`
  URI) per profile and types the code itself, or prompts on stdin when no
  secret is stored. Accounts without 2FA are unaffected.
- **Everything but the token goes to stderr**, so
  `gppt login --json | jq -r .access_token` works.
- **File modes.** Config and token files are written `0600`.
- **A longer manual-login window** — 5 minutes instead of 60 seconds, enough
  to work through a captcha or a 2FA prompt.
- **A synchronous, typed Python API** — `gppt.login()`, `gppt.get_token()`,
  `gppt.refresh()`, returning a `Token` dataclass instead of a bare dict.

## What has not changed

- The pixiv OAuth flow itself, and the tokens it produces.
- Proxy support: `ALL_PROXY` / `HTTPS_PROXY` / `HTTP_PROXY` still apply to both
  the browser and the token requests.
- Playwright still downloads Chromium on first run.
- Supported Python versions: 3.10 through 3.14.

## Staying on v4

```toml
dependencies = [ "gppt<5" ]
```

---

## Command mapping

**`-p` no longer means `--password`.** In v5 it means `--profile`.

| v4 | v5 |
| --- | --- |
| `gppt login` | `gppt login` (with no credentials configured) |
| `gppt login -u <id> -p <pw>` | `gppt configure` once, then `gppt login` |
| `gppt login-headless -u <id> -p <pw>` (`lh`) | same as above — v5 is headless by default |
| (no v4 equivalent) | `gppt login --no-headless` shows the browser window |
| `gppt login-interactive` (`li`) | `gppt configure`, then `gppt login` — the interactive prompt moved to `configure` |
| `gppt refresh <token>` (`r`) | `gppt login` — refreshing is automatic |
| `-j` / `--json` | unchanged |
| aliases `l`, `li`, `lh`, `r` | removed |

## Migrating

### 1. Store your account once

```console
$ gppt configure
pixiv ID / e-mail address (or op://...): me@example.com
pixiv password (optional, hidden; op:// allowed):
TOTP secret or otpauth:// URI (optional, hidden; op:// allowed):

Saved: /home/me/.config/gppt/default.json
```

This writes `~/.config/gppt/default.json` with mode `0600`. From then on,
`gppt login` needs no arguments. Every field is optional: leave the username
and password blank and `gppt login` opens a visible browser window for a
manual login, exactly like a bare `gppt login` did in v4.

### 2. Replace `login-headless` in scripts

v5 has no `-u` / `-p` flags. For unattended runs where storing a profile is
awkward (containers, CI), pass the credentials through the environment:

```bash
# v4
gppt login-headless -u "$PIXIV_ID" -p "$PIXIV_PW" --json

# v5
GPPT_USERNAME="$PIXIV_ID" GPPT_PASSWORD="$PIXIV_PW" gppt login --json
```

`GPPT_USERNAME` / `GPPT_PASSWORD` override whatever the profile holds, so this
works with no config file at all.

### 3. Drop `gppt refresh`

v5 caches the token it issues in `~/.config/gppt/<profile>.token.json` and
reuses it. A repeated `gppt login`:

1. returns the cached token while it is still valid,
1. otherwise refreshes it with the stored refresh token,
1. and only opens a browser when both of those fail.

So the v4 habit of "log in once, then call `gppt refresh` on a timer" becomes
just calling `gppt login` whenever you need a token. Use `gppt login --force`
to skip the cache and go through the browser regardless.

### 4. Carry over an existing refresh token

If you already hold a refresh token from v4 and would rather not log in again,
seed the cache by hand. An empty `expires_at` reads as "expired", so the next
`gppt login` goes straight to the refresh path:

```bash
mkdir -p ~/.config/gppt
cat > ~/.config/gppt/default.token.json <<'EOF'
{"access_token": "", "refresh_token": "<your v4 refresh token>", "expires_in": 0, "expires_at": ""}
EOF
chmod 600 ~/.config/gppt/default.token.json
gppt login
```

From Python, `gppt.refresh("<your v4 refresh token>")` does the same thing
without going near the cache.

### 5. If you used `client.json`

v4's `PixivAuth` read a `client.json` of the form
`{"pixiv_id": "...", "password": "..."}` from the working directory. v5 does
not read that file. Move the two values into a profile with `gppt configure`
(or into `GPPT_USERNAME` / `GPPT_PASSWORD`) and delete `client.json` — it was
an unprotected plaintext password sitting in a project directory.

### 6. Docker

The image now has an entrypoint, so the subcommand is the whole argument list:

```bash
# v4
docker run --rm -it ghcr.io/eggplants/get-pixivpy-token lh -u <id> -p <pw>

# v5
docker run --rm \
  -e GPPT_USERNAME=<id> -e GPPT_PASSWORD=<pw> \
  ghcr.io/eggplants/get-pixivpy-token login --json
```

With no arguments the image runs `gppt login`.

## Library users

You can still get a token from Python, but the API is new: three functions
instead of two classes, synchronous, returning a `Token` dataclass instead of
a raw dict.

| v4 | v5 |
| --- | --- |
| `GetPixivToken().login(username=…, password=…)` (async) | `gppt.login(username, password, totp_secret)` (sync) |
| `GetPixivToken.refresh(rt)` | `gppt.refresh(rt)` |
| `PixivAuth().auth()` | `gppt.get_token()` — see [below](#pixivauth) |
| `res["access_token"]` | `token.access_token` |
| `res["response"]`, `OAuthAPIResponse` | removed; the flattened fields are the response |
| `PixivLoginFailedError` | `gppt.LoginError` (browser) / `gppt.TokenError` (pixiv rejected the request) |
| `LoginCred` | removed together with `client.json` |
| `gppt.gppt`, `gppt.main`, `gppt.auth`, `gppt.utils` | `gppt.api`, `gppt.cli`, `gppt.config`, `gppt.browser`, `gppt.token`, `gppt.secrets` |

`LoginInfo`, `LoginUserInfo` and `ProfileURIs` still exist in
`gppt.model_types`, but they now describe the raw HTTP response and are no
longer re-exported from `gppt`. Read `Token` instead.

### Short example

```python
# v4
import asyncio
from gppt import GetPixivToken

g = GetPixivToken(headless=True, username="...", password="...")
res = asyncio.run(g.login())
refresh_token = res["refresh_token"]

# v5
import gppt

token = gppt.login("...", "...")
refresh_token = token.refresh_token
```

### `PixivAuth`

`PixivAuth` bundled three things: read `client.json`, prompt on stdin, log in
and retry. v5 splits them — `gppt configure` does the prompting and stores the
account, and `gppt.get_token()` does the rest:

```python
# v4
from gppt import PixivAuth

aapi, login_info = PixivAuth().auth()

# v5
import gppt
from pixivpy3 import AppPixivAPI

token = gppt.get_token()  # reads local configuration

aapi = AppPixivAPI()
aapi.auth(refresh_token=token.refresh_token)
```

`pixivpy3` is no longer a dependency of `gppt`, so add it to your own project
if you use `AppPixivAPI`.

`get_token()` is the library form of `gppt login`, including the cache: it
returns the stored token while it is valid, refreshes it when it is not, and
opens the browser only as a last resort. It is silent; pass `notify=print` for
the CLI's progress messages, or `save=False` to leave the cache alone.
