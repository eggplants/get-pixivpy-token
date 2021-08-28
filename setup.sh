#!/usr/bin/env bash

CHROME_URI="https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb"

for i in apt curl pip python; do
  command -v "$i" >/dev/null || {
    echo "require: $i" >&2
    exit 1
  }
done

echo "[install google-chrome]"
command -v google-chrome >/dev/null || {
  out="/tmp/google-chrome-stable.deb"
  [ -f "$out" ] || curl -s "$CHROME_URI" \
    -o "$out" \
    sudo apt -f install -y -qq "$out"
}

command -v google-chrome >/dev/null || {
  echo "failed to install: google-chrome" >&2
  exit 1
}

echo "[install selenium with driver]"
dpkg -l | grep python3-selenium -q || {
  sudo apt -f install -y -qq python3-selenium
}
dpkg -l | grep python3-selenium -q || {
  echo "failed to install: python3-selenium" >&2
  exit 1
}

echo "[install selenium module to python]"
python -c "import selenium;print(selenium.__version__)" >/dev/null || {
  python -m pip install selenium
}
python -c "import selenium;print(selenium.__version__)" >/dev/null || {
  echo "failed to install: selenium module" >&2
  exit 1
}

echo "[test]"
if python -c'
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

options = Options()
options.add_argument("--headless")
webdriver.Chrome(options=options).close()
'; then
  echo "success!"
else
  echo "failed!" >&2
  exit 1
fi
