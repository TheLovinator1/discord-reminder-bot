# Discord-reminder-bot

Discord bot that allows you to set reminders.

![Bot](/Bot.png)

<sup>Theme is [DiscordNight by KillYoy](https://github.com/KillYoy/DiscordNight)<sup>

## Usage

!remind <message_date> <message_reason>

message_date can be anything that is a date or time. For example:

* `in 2 days`
* `August 14, 2021 EST`,
* `tomorrow`
* `1 เดือนตุลาคม 2025, 1:00 AM`

message_reason is the message the bot will send at that time.

## Environment Variables

* `BOT_TOKEN` - Discord bot token ([Where to get one](https://discord.com/developers/applications))
* `TIMEZONE` - Your time zone ([List of time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones))
* `SQLITE_LOCATION` - (Optional) Where to store the database. Docker users need to change this to "/data/jobs.sqlite"
* `LOG_LEVEL` - Can be CRITICAL, ERROR, WARNING, INFO or DEBUG

## Installation

You have two choices, [install directly on your computer](#Install-directly-on-your-computer) or using [Docker](#docker-compose-with-env-file).

[Docker Hub](https://hub.docker.com/r/thelovinator/discord-reminder-bot) | [docker-compose.yml](docker-compose.yml) | [Dockerfile](Dockerfile)

### Install directly on your computer

* Install latest version of Python 3 for your operating system
* (Optional) Create a virtual environment:
  * `python -m venv .venv`
    * Activate virtual environment:
      * Windows:  `.\.venv\Scripts\activate`
      * Not windows:  `source .venv/bin/activate`
* Install requirements
  * `pip install -r requirements.txt`
* Rename .env.example to .env and fill it out.
* Start the bot (inside the virtual environment if you made one):
  * `python main.py`

### Start the bot when your Linux server boots

* Keep services running after logout
  * `loginctl enable-linger`
* Move service file to correct location (You may have to modify WorkingDirectory and/or ExecStart)
  * `cp discord-reminder-bot.service ~/.config/systemd/user/discord-reminder-bot.service`
* Start bot now and at boot
  * `systemctl --user enable --now discord-reminder-bot`

#### systemd examples

* Start bot automatically at boot
  * `systemctl --user enable discord-reminder-bot`
* Don't start automatically
  * `systemctl --user disable discord-reminder-bot`
* Restart
  * `systemctl --user restart discord-reminder-bot`
* Stop
  * `systemctl --user stop discord-reminder-bot`
* Start
  * `systemctl --user start discord-reminder-bot`
* Check status
  * `systemctl --user status discord-reminder-bot`
* Reading the journal
  * `journalctl --user-unit discord-reminder-bot`

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
|                           `-e TZ=Europe/London`                            | Specify a time zone to use, this is used by the time zone converter and APScheduler |
|                  `-e SQLITE_LOCATION=/home/botuser/data/`                  | Where to store the database file. It should be stored on a volume                   |
|                            `-e LOG_LEVEL=INFO`                             | Log severity. Can be CRITICAL, ERROR, WARNING, INFO or DEBUG                        |
|                   `-v /path/to/data:/home/botuser/data/`                   | Folder to store the database                                                        |

## Application Setup

Add reminders with the `![remind|reminder|remindme|at] <message_date> <message_reason>` command.

## Support Info

* Shell access whilst the container is running: `docker exec -it discord-reminder-bot /bin/bash`
* To monitor the logs of the container in real-time: `docker logs -f discord-reminder-bot`

## Updating

### Via Docker Compose

* Update all images: `docker-compose pull`
  * or update a single image: `docker-compose pull discord-reminder-bot`
* Let compose update all containers as necessary: `docker-compose up -d`
  * or update a single container: `docker-compose up -d discord-reminder-bot`
* You can also remove the old dangling images: `docker image prune`

### Via Docker Run

* Update the image: `docker pull thelovinator/discord-reminder-bot`
* Stop the running container: `docker stop discord-reminder-bot`
* Delete the container: `docker rm discord-reminder-bot`
* Recreate a new container with the same docker run parameters as instructed above (if you mapped `/home/botuser/data/` to your computer your `jobs.sqlite` file and reminders will be preserved)
* You can also remove the old dangling images: `docker image prune`

## Building locally

If you want to make local modifications to these images for development purposes or just to customize the logic:

```console
git clone https://github.com/TheLovinator1/discord-reminder-bot.git

cd discord-reminder-bot

docker build \
  --no-cache \
  --pull \
  -t thelovinator/discord-reminder-bot:latest .
```

### Acknowledgments

The Docker part of this README is based on the READMEs from [LinuxServer.io](https://github.com/linuxserver)

## Help

* Email: tlovinator@gmail.com
* Discord: TheLovinator#9276
* Steam: [steamcommunity.com/id/TheLovinator/](https://steamcommunity.com/id/TheLovinator/)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
