# syntax=docker/dockerfile:1
# check=error=true;experimental=all

FROM python:3.13-slim@sha256:27f90d79cc85e9b7b2560063ef44fa0e9eaae7a7c3f5a9f74563065c5477cc24

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
