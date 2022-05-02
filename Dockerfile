FROM python:3.10-slim

# We don't want apt-get to interact with us,
# and we want the default answers to be used for all questions.
ARG DEBIAN_FRONTEND=noninteractive

# Don't generate byte code (.pyc-files).
# These are only needed if we run the python-files several times.
# Docker doesn't keep the data between runs so this adds nothing.
ENV PYTHONDONTWRITEBYTECODE 1

# Force the stdout and stderr streams to be unbuffered.
# Will allow log messages to be immediately dumped instead of being buffered.
# This is useful when the bot crashes before writing messages stuck in the buffer.
ENV PYTHONUNBUFFERED 1

# Update packages and install needed packages to build our requirements.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc curl

# Create user so we don't run as root.
RUN useradd --create-home botuser
RUN chown -R botuser:botuser /home/botuser && chmod -R 755 /home/botuser
USER botuser

# Create directory for the sqlite database.
# You need to share this directory with the computer running
# the container to save the data.
RUN mkdir -p /home/botuser/data

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add poetry to our path
ENV PATH="/home/botuser/.local/bin/:${PATH}"

COPY pyproject.toml poetry.lock README.md /home/botuser/

# Change directory to where we will run the bot.
WORKDIR /home/botuser

RUN poetry install --no-interaction --no-ansi --no-dev

COPY discord_reminder_bot/main.py discord_reminder_bot/settings.py /home/botuser/discord_reminder_bot/

VOLUME ["/home/botuser/data/"]

# Run bot.
CMD [ "poetry", "run", "bot" ]
