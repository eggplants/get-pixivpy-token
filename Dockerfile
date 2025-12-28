FROM mcr.microsoft.com/playwright/python:v1.57.0-noble
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

COPY . /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_NO_DEV=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app
RUN uv sync --locked --no-dev

ENV PATH="/app/.venv/bin:$PATH"

CMD ["uv", "run", "gppt"]
