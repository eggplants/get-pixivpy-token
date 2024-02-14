# `gppt`: get-pixivpy-token

[![PyPI](
  <https://img.shields.io/pypi/v/gppt?color=blue>
  )](
  <https://pypi.org/project/gppt/>
) [![ghcr](
  <https://ghcr-badge.deta.dev/eggplants/get-pixivpy-token/size>
  )](
  <https://github.com/eggplants/get-pixivpy-token/pkgs/container/get-pixivpy-token>
) [![Maintainability](
  <https://api.codeclimate.com/v1/badges/b40b8fa2c9d71f869b9c/maintainability>
  )](
  <https://codeclimate.com/github/eggplants/get-pixiv-token/maintainability>
) [![pre-commit.ci status](
  <https://results.pre-commit.ci/badge/github/eggplants/get-pixivpy-token/main.svg>
  )](
  <https://results.pre-commit.ci/latest/github/eggplants/get-pixivpy-token/main>
)

- Get your Pixiv token (for running [upbit/pixivpy](https://github.com/upbit/pixivpy))
- Refine [pixiv_auth.py](https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362) + [its fork](https://gist.github.com/upbit/6edda27cb1644e94183291109b8a5fde)

## Install

```bash
pip install gppt
```

## Enable Proxy

Set `ALL_PROXY` or `HTTPS_PROXY` to your environment variables.

## Run

### Example

```python
from gppt import GetPixivToken
from pixivpy3 import AppPixivAPI

def get_refresh_token() -> str:
    with open("token.txt", "w+") as f:
        if refresh_token := f.read().strip():
            return refresh_token

        g = GetPixivToken(headless=True)
        refresh_token = g.login(username="...", password="...")["refresh_token"]
        f.write(refresh_token)
        return refresh_token

aapi = AppPixivAPI()
aapi.auth(refresh_token=get_refresh_token())
...
```

### From Docker

```shellsession
$ docker run --rm -it ghcr.io/eggplants/get-pixivpy-token lh -u <id> -p <pw>
[+]: Success!
access_token: ***
refresh_token: ***
expires_in: 3600
```

### From CLI

- Note: _In advance, please setup google-chrome-stable + selenium + webdriver_

```shellsession
# with browser
$ gppt login
[!]: Chrome browser will be launched. Please login.
(Log in to Pixiv from the login screen that starts up.)
[+]: Success!
access_token: ***
refresh_token: ***
expires_in: 3600
...

# with headless browser
$ gppt login-headless -u <id> -p <pw>
[!]: Chrome browser will be launched. Please login.
[+]: Success!
access_token: ***
refresh_token: ***
expires_in: 3600
```

### From Library

- Note: _In advance, please setup google-chrome-stable + selenium + webdriver_
If either username or password are missing, manual input will be required.

```python
from gppt import GetPixivToken

g = GetPixivToken(headless=False,username=None,password=None)
res = g.login(headless=None,username=None,password=None)
```

- `res.response` returns:

```json
{
  "access_token": "***",
  "expires_in": 3600,
  "refresh_token": "***",
  "scope": "",
  "token_type": "bearer",
  "user": {
    "account": "***",
    "id": "***",
    "is_mail_authorized": <bool>,
    "is_premium": <bool>,
    "mail_address": "***@***",
    "name": "***",
    "profile_image_urls": {
      "px_16x16": "https://s.pximg.net/common/images/no_profile_ss.png",
      "px_170x170": "https://s.pximg.net/common/images/no_profile.png",
      "px_50x50": "https://s.pximg.net/common/images/no_profile_s.png"
    },
    "require_policy_agreement": <bool>,
    "x_restrict": 2
  }
}
```

## Help

```shellsession
$ gppt -h
usage: gppt [-h]
            {login,l,login-interactive,li,login-headless,lh,refresh,r} ...

Get your Pixiv token (for running upbit/pixivpy)

positional arguments:
  {login,l,login-interactive,li,login-headless,lh,refresh,r}
    login (l)           retrieving auth token
    login-interactive (li)
                        `login` in interactive mode
    login-headless (lh)
                        `login` in headless mode
    refresh (r)         refresh tokens

optional arguments:
  -h, --help            show this help message and exit
```

```shellsession
$ gppt l -h
usage: gppt login [-h] [-u USERNAME] [-p PASSWORD] [-j]

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        your E-mail address / pixiv ID
  -p PASSWORD, --password PASSWORD
                        your current pixiv password
  -j, --json            output response as json
```

```shellsession
$ gppt li -h
usage: gppt login-interactive [-h] [-j]

optional arguments:
  -h, --help  show this help message and exit
  -j, --json  output response as json
```

```shellsession
$ gppt lh -h
usage: gppt login-headless [-h] -u USERNAME -p PASSWORD [-j]

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        your E-mail address / pixiv ID
  -p PASSWORD, --password PASSWORD
                        your current pixiv password
  -j, --json            output response as json
```

```shellsession
$ gppt r -h
usage: gppt refresh [-h] [-j] refresh_token

positional arguments:
  refresh_token

optional arguments:
  -h, --help     show this help message and exit
  -j, --json     output response as json
```
