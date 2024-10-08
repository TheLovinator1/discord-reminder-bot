FROM python:3.13-slim as base

ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV POETRY_VIRTUALENVS_IN_PROJECT=1
ENV POETRY_NO_INTERACTION=1
ENV POETRY_HOME=/opt/poetry
ENV PYSETUP_PATH=/opt/pysetup
ENV VENV_PATH="/opt/pysetup/.venv"
ENV PIP_NO_CACHE_DIR=off
ENV PIP_DISABLE_PIP_VERSION_CHECK=on
ENV PIP_DEFAULT_TIMEOUT=100
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONFAULTHANDLER=1
ENV PATH="$POETRY_HOME/bin:$VENV_PATH/bin:$PATH"
ENV PYTHONPATH="${PYTHONPATH}:/discord_reminder_bot"

FROM base as python-deps

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl build-essential

RUN --mount=type=cache,target=/root/.cache \
    curl -sSL https://install.python-poetry.org | python3 -

WORKDIR $PYSETUP_PATH
COPY pyproject.toml ./

RUN --mount=type=cache,target=/root/.cache \
    poetry install --only main

FROM base as runtime

# Copy virtual env from python-deps stage
COPY --from=python-deps $PYSETUP_PATH $PYSETUP_PATH

# Create directory for the sqlite database.
RUN mkdir -p /home/botuser/data

# Copy source code
COPY discord_reminder_bot /home/botuser/discord_reminder_bot/

WORKDIR /home/botuser

VOLUME ["/home/botuser/data/"]

# Run bot.
CMD [ "python", "/home/botuser/discord_reminder_bot/main.py" ]
