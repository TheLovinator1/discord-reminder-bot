# syntax=docker/dockerfile:1
# check=error=true;experimental=all

FROM python:3.13-slim@sha256:faa4eb619170e3235375f94b2f3d6b0103ddf2c7e1c8b78c3676827f38d9166f

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
