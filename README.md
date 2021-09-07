# `gppt`: get-pixivpy-token

[![PyPI](https://img.shields.io/pypi/v/gppt?color=blue)](https://pypi.org/project/gppt/) [![Docker Image Size (latest by date)](https://img.shields.io/docker/image-size/eggplanter/gppt)](https://hub.docker.com/r/eggplanter/gppt) [![Maintainability]](https://codeclimate.com/github/eggplants/get-pixiv-token/maintainability)

- Get your Pixiv token (for running [upbit/pixivpy](https://github.com/upbit/pixivpy))
- Refine [pixiv_auth.py](https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362) + [its fork](https://gist.github.com/upbit/6edda27cb1644e94183291109b8a5fde)

## Install

```bash
❭ pip install gppt
```

## Run

- Note: _In advance, please setup google-chrome-stable + selenium + webdriver_
- On Ubuntu, my setup script is available

```bash
❭ ./setup.sh
```

### From Library

```python
from gppt import GetPixivToken
g = GetPixivToken()
res = g.login(headless=True, user="...", pass_="...")
```

- `res.response` returns

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

### From CLI

```bash
# with browser
❭ gppt login
[!]: Chrome browser will be launched. Please login.
(Log in to Pixiv from the login screen that starts up.)
[+]: Success!
access_token: ***
refresh_token: ***
expires_in: 3600

# with headless browser
❭ gppt login-headless -u <id> -p <pw>
[!]: Chrome browser will be launched. Please login.
[+]: Success!
access_token: ***
refresh_token: ***
expires_in: 3600
```

### From Docker

```bash
❭ docker run -it eggplanter/gppt -e PIXIV_ID=<id> -e PIXIV_PASS=<pw>
```

- with envfile

```bash
# In .env
# PIXIV_ID=<id>
# PIXIV_PASS=<pw>
❭ docker run -it eggplanter/gppt --env-file .env
```

## Help

```bash
❭ gppt -h
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

```bash
❭ gppt l -h
usage: gppt login [-h] [-u USERNAME] [-p PASSWORD] [-j]

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        your E-mail address / pixiv ID
  -p PASSWORD, --password PASSWORD
                        your current pixiv password
  -j, --json            output response as json
```

```bash
❭ gppt li -h
usage: gppt login-interactive [-h] [-j]

optional arguments:
  -h, --help  show this help message and exit
  -j, --json  output response as json
```

```bash
❭ gppt lh -h
usage: gppt login-headless [-h] -u USERNAME -p PASSWORD [-j]

optional arguments:
  -h, --help            show this help message and exit
  -u USERNAME, --username USERNAME
                        your E-mail address / pixiv ID
  -p PASSWORD, --password PASSWORD
                        your current pixiv password
  -j, --json            output response as json
```

```bash
❭ gppt r -h
usage: gppt refresh [-h] [-j] refresh_token

positional arguments:
  refresh_token

optional arguments:
  -h, --help     show this help message and exit
  -j, --json     output response as json
```

[maintainability]: https://api.codeclimate.com/v1/badges/b40b8fa2c9d71f869b9c/maintainability
