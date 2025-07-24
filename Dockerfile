# syntax=docker/dockerfile:1
# check=error=true;experimental=all

FROM python:3.13-slim@sha256:4c2cf9917bd1cbacc5e9b07320025bdb7cdf2df7b0ceaccb55e9dd7e30987419

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN useradd -m botuser && mkdir -p /home/botuser/data
WORKDIR /home/botuser

COPY interactions /home/botuser/interactions
COPY discord_reminder_bot /home/botuser/discord_reminder_bot

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --no-install-project

ENV DATA_DIR=/home/botuser/data
ENV SQLITE_LOCATION=/data/jobs.sqlite
VOLUME ["/home/botuser/data/"]
CMD ["uv", "run", "python", "-m", "discord_reminder_bot.main"]
