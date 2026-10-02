FROM mcr.microsoft.com/playwright/python:v1.57.0-noble@sha256:3de745b23fc4b33fccbcb3f592ee52dd5c80ce79f19f839c825ce23364e403c1
COPY --from=ghcr.io/astral-sh/uv:latest@sha256:f513a91fc62fe7c17567eee97230dd198e43edb8a9fbecca843714a4358fe1bc /uv /bin/uv

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY . /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["gppt"]
CMD ["login"]
