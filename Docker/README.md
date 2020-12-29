# Discord-reminder-bot

Discord bot that allows you to set reminders.

![Bot](/Bot.png)

<sup>Theme is [DiscordNight by KillYoy](https://github.com/KillYoy/DiscordNight)<sup>

## Usage

### docker-compose with .env file

More information on [Docker Hub](https://hub.docker.com/repository/docker/thelovinator/discord-reminder-bot)

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

## Environment Variables

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

## Help

* Email: tlovinator@gmail.com
* Discord: TheLovinator#9276
* Steam: [steamcommunity.com/id/TheLovinator/](https://steamcommunity.com/id/TheLovinator/)

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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details

### Acknowledgments

This README is based on the READMEs from [LinuxServer.io](https://github.com/linuxserver)
