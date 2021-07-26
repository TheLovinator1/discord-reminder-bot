# Discord-reminder-bot

Discord bot that allows you to set date, cron and interval reminders.

## Usage

Type /remind in a Discord server where this bot exists to get a list of slash commands you can use.

## Environment Variables

* `BOT_TOKEN` - Discord bot token ([Where to get one](https://discord.com/developers/applications))
* `TIMEZONE` - Your time zone. You want the TZ database name. ([List of time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)). Defaults to `Europe/Stockholm`
* `SQLITE_LOCATION` - (Optional) Where to store the database. Defaults to `/jobs.sqlite`
* `LOG_LEVEL` - Can be CRITICAL, ERROR, WARNING, INFO or DEBUG. Defaults to `INFO`

## Installation

You have two choices, [install directly on your computer](#Install-directly-on-your-computer) or using [Docker](#docker-compose-with-env-file).

### Install directly on your computer

* Install latest version of [git](https://git-scm.com/), [Python](https://www.python.org/) and [Poetry](https://python-poetry.org/docs/#installation).
* Download project from GitHub and change directory into it.
* Open terminal in repository folder.
* Install requirements:
  * `poetry install`
* Rename .env.example to .env and fill it out.
* Start the bot:
  * `poetry run bot`

## Docker

### docker-compose with .env file

More information on [Docker Hub](https://hub.docker.com/r/thelovinator/discord-reminder-bot)

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

### docker cli

```console
docker run -d \
  --name=discord-reminder-bot \
  -e BOT_TOKEN=JFIiasfjioFIAOJFOIJIOSAF.AFo-7A.akwFakeopfaWPOKawPOFKOAKFPA \
  -e TIMEZONE=Europe/Stockholm \
  -e LOG_LEVEL=INFO \
  -e SQLITE_LOCATION=/data/jobs.sqlite \
  -v /path/to/data:/home/botuser/data/ \
  --restart unless-stopped \
  thelovinator/discord-reminder-bot
```

> **_NOTE:_**  SQLITE_LOCATION must be on a volume to keep the reminders if you restart the Docker container!

## Docker Environment Variables

|                                 Parameter                                  | Function                                                                            |
| :------------------------------------------------------------------------: | ----------------------------------------------------------------------------------- |
| `-e BOT_TOKEN=JFIiasfjioFIAOJFOIJIOSAF.AFo-7A.akwFakeopfaWPOKawPOFKOAKFPA` | Discord bot token ([Where to get one](https://discord.com/developers/applications)) |
|                           `-e TZ=Europe/London`                            | Your time zone. Select yours from TZ database name. ([List of time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)). |
|                  `-e SQLITE_LOCATION=/home/botuser/data/`                  | Where to store the database file. It should be stored on a volume.                  |
|                            `-e LOG_LEVEL=INFO`                             | Log severity. Can be CRITICAL, ERROR, WARNING, INFO or DEBUG.                       |
|                   `-v /path/to/data:/home/botuser/data/`                   | Folder to store the database                                                        |

## Help

* Email: tlovinator@gmail.com
* Discord: TheLovinator#9276
* Steam: [steamcommunity.com/id/TheLovinator/](https://steamcommunity.com/id/TheLovinator/)
