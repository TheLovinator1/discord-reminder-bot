FROM python:3.13-slim
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
VOLUME ["/home/botuser/data/"]
CMD ["uv", "run", "discord_reminder_bot/main.py"]
