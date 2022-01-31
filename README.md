# Discord-reminder-bot

<p align="center">
  <img src="extras/Bot.png" title="/remind add message_reason: Remember to feed the cat! message_date: 2 November 2025 14:00 CET"/>
</p>
<p align="center"><sup>Theme is https://github.com/KillYoy/DiscordNight<sup></p>

A discord bot that allows you to set a date, [cron](https://en.wikipedia.org/wiki/Cron), and interval reminders.

## Usage

Type /remind in a Discord server where this bot exists to get a list of slash commands you can use.

## Installation

You have two choices, [install directly on your computer](#Install-directly-on-your-computer) or using [Docker](#docker-compose-with-env-file).

### Creating a Discord bot token

- Create a [New Application](https://discord.com/developers/applications).
- Create a bot by going to Bot -> Add Bot -> Yes, do it!
- You can change Icon and Username here.
- Copy the bot token and paste it into the `BOT_TOKEN` environment variable.
- Go to the OAuth2 page -> URL Generator
  - Select the `bot` and `applications.commands` scope.
  - Select the bot permissions that you want the bot to have. Select `Administrator`. (TODO: Add a list of permissions that are needed)
  - Copy the generated URL and open it in your browser. You can now invite the bot to your server.

### Install directly on your computer

- Install latest version of [git](https://git-scm.com/), [Python](https://www.python.org/) and [Poetry](https://python-poetry.org/docs/master/#installation).
- Download project from GitHub with git or download the [ZIP](https://github.com/TheLovinator1/discord-reminder-bot/archive/refs/heads/master.zip).
  - If you want to update the bot, you can run `git pull` in the project folder or download the ZIP again.
- Rename .env.example to .env and open it in a text editor.
  - If you can't see the file extension:
    - Windows 10: Click the View Tab in File Explorer and click the box next to File name extensions.
    - Windows 11: Click View -> Show -> File name extensions.
- Open a terminal in the repository folder.
  - Windows 10: Shift + right-click in the folder and select `Open PowerShell window here`.'
  - Windows 11: Shift + right-click in the folder and select `Open in Windows Terminal`.'
- Install requirements:
  - `poetry install`
    - (You may have to restart your terminal if it can't find the `poetry` command)
- Start the bot with:
  - `poetry run bot`
    - You can stop the bot with ctrl + c.

Note: You will need to run `poetry install` again if poetry.lock has been modified.
Note: It can take up to one hour for the slash commands to be visible in the Discord server.

### Docker

Docker Hub: [thelovinator/discord-reminder-bot](https://hub.docker.com/r/thelovinator/discord-reminder-bot)

- Install latest version of [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/install/).
- Rename .env.example to .env and open it in a text editor.
  - If you can't see the file extension:
    - Windows 10: Click the View Tab in File Explorer and click the box next to File name extensions.
    - Windows 11: Click View -> Show -> File name extensions.
- Open a terminal in the extras folder.
  - Windows 10: Shift + right-click in the folder and select `Open PowerShell window here`
  - Windows 11: Shift + right-click in the folder and select `Open in Windows Terminal`
- Run the Docker Compose file:
  - `docker-compose up`
    - You can stop the bot with ctrl + c.
    - If you want to run the bot in the background, you can run `docker-compose up -d`.

## Help

- Email: tlovinator@gmail.com
- Discord: TheLovinator#9276
- Steam: [steamcommunity.com/id/TheLovinator/](https://steamcommunity.com/id/TheLovinator/)
