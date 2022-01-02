# Discord-reminder-bot

<p align="center">
  <img src="https://raw.githubusercontent.com/TheLovinator1/discord-reminder-bot/master/Bot.png" title="/remind add message_reason: Remember to feed the cat! message_date: 2 November 2025 14:00 CET"/>
</p>
<p align="center"><sup>Theme is https://github.com/KillYoy/DiscordNight<sup></p>

A discord bot that allows you to set date, cron, and interval reminders.

## Usage

Type /remind in a Discord server where this bot exists to get a list of slash commands you can use.

| Environment Variable | Description                                                                                                                         |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| BOT_TOKEN            | [Discord bot token](https://discord.com/developers/applications)                                                                    |
| TIMEZONE             | Your time zone. You want the TZ database name. ([List of time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)) |
| SQLITE_LOCATION      | (Optional) Where to store the database. Defaults to `/jobs.sqlite`                                                                  |
| LOG_LEVEL            | Can be CRITICAL, ERROR, WARNING, INFO, or DEBUG. Defaults to `INFO`                                                                 |

## Installation

You have two choices, [install directly on your computer](#Install-directly-on-your-computer) or using [Docker](#docker-compose-with-env-file).

### Install directly on your computer

- Install latest version of [git](https://git-scm.com/), [Python](https://www.python.org/) and [Poetry](https://python-poetry.org/docs/#installation).
- Download project from GitHub and change directory into it.
- Open terminal in the repository folder.
- Install requirements:
  - `poetry install`
- Copy .env.example from extras and rename to .env and fill it out.
- Start the bot with:
  - `poetry run bot`

## Docker

- Install latest version of [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/install/).
- Download project from GitHub and change directory into it.
- Copy .env.example from extras and rename to .env and fill it out.
- Start the bot with, press ctrl+c to stop it:
  - `docker-compose up`
- Run in the background with:
  - `docker-compose up -d`

```yaml
version: "3"
services:
  discord-reminder-bot:
    image: thelovinator/discord-reminder-bot
    env_file:
      - .env
    container_name: discord-reminder-bot
    environment:
      - BOT_TOKEN=${BOT_TOKEN}
      - TIMEZONE=${TIMEZONE}
      - LOG_LEVEL=${LOG_LEVEL}
      - SQLITE_LOCATION=/data/jobs.sqlite
    restart: unless-stopped
    volumes:
      - data_folder:/home/botuser/data/
volumes:
  data_folder:
```

## Help

- Email: tlovinator@gmail.com
- Discord: TheLovinator#9276
- Steam: [steamcommunity.com/id/TheLovinator/](https://steamcommunity.com/id/TheLovinator/)
