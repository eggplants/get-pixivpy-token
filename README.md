# `gppt`: get-pixivpy-token

![PyPI](https://img.shields.io/pypi/v/gppt?color=blue) [![Maintainability]](https://codeclimate.com/github/eggplants/get-pixiv-token/maintainability)

- Get your Pixiv token (for running in pixivpy)
- Refine [pixiv_auth.py](https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362)

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

- Then

```bash
❭ gppt login
access_token: ***
refresh_token: ***
expires_in: 3600
```

[maintainability]: https://api.codeclimate.com/v1/badges/b40b8fa2c9d71f869b9c/maintainability
