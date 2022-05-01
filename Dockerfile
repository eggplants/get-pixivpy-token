FROM python:3.11.0a7

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

RUN wget -qO- https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list'

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get -y update \
    && apt-get install -y --no-install-recommends \
    google-chrome-stable \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# install chromedriver
RUN wget -qO /tmp/chromedriver.zip \
    "http://chromedriver.storage.googleapis.com/$(wget -qO- chromedriver.storage.googleapis.com/LATEST_RELEASE)/chromedriver_linux64.zip" \
    && unzip -qq /tmp/chromedriver.zip chromedriver -d /usr/local/bin/

# set display port to avoid crash
ENV DISPLAY=:99

# upgrade pip
RUN pip install --no-cache-dir -U pip

# install selenium
RUN pip install --no-cache-dir selenium gppt
# CMD ["gppt", "lh", "-u", "${PIXIV_ID}", "-p", "${PIXIV_PASS}"]
ENTRYPOINT ["gppt"]
