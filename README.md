# Discord-reminder-bot

Discord bot that allows you to set reminders.

![Bot](/Bot.png)

<sup>Theme is [DiscordNight by KillYoy](https://github.com/KillYoy/DiscordNight)<sup>

## Environment Variables

* `BOT_TOKEN` - Discord bot token ([Where to get one](https://discord.com/developers/applications))
* `TIMEZONE` - Your time zone ([List of time zones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones))
* `SQLITE_LOCATION` - (Optional) Where to store the database. Docker users need to change this to "/data/jobs.sqlite"
* `LOG_LEVEL` - Can be CRITICAL, ERROR, WARNING, INFO or DEBUG

## Installation

You have two choices, install directly on your computer or using [Docker](https://registry.hub.docker.com/r/thelovinator/discord-reminder-bot).

[Docker Hub](https://registry.hub.docker.com/r/thelovinator/discord-reminder-bot) | [docker-compose.yml](docker-compose.yml) | [Dockerfile](Dockerfile)

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

## Help

* Email: tlovinator@gmail.com
* Discord: TheLovinator#9276
* Steam: [steamcommunity.com/id/TheLovinator/](https://steamcommunity.com/id/TheLovinator/)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details
