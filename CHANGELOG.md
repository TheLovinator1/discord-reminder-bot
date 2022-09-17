# Changelog

## [1.0.0] - 2022-09-17

### Added

- Added tests for checking if timezones are working correctly

### Changed

- Bot is now using [discord-py-interactions](https://github.com/interactions-py/library) instead of
  [discord-py-slash-command](https://github.com/interactions-py/library/tree/legacy-v3) and [discord.py]
  (https://github.com/Rapptz/discord.py).
- `/remind pause`, `/remind resume`, `/remind delete`, and `/remind modify` are now buttons under `/remind list`.
- `/remind list` uses pagination now.
- `/remind modify` uses a modal now.

### Fixed

- [Dockerfile](/Dockerfile) was broken, now it is fixed. (Thanks to [FirosStuart](https://github.com/FirosStuart)
  for the fix)
- Timezones are now handled correctly. (Thanks to [FirosStuart](https://github.com/FirosStuart))

### Breaking Changes

- You will need the latest version of Poetry to install the dependencies. (Or have Git installed)

## [0.3.0] - 2022-02-19

- Docker image is now built automatically
- Added more information to .env.example
- Rewrote install instructions and added how you create a Discord bot token to the README.md.
- `build: .` is now removed from docker-compose.yml as it broke `docker-compose up`
- `version: 3` is now removed from the docker-compose.yml as it is not needed anymore.
- `.env.example` is now located in extras and root folder.

### Fixed

- Date in CHANGELOG.md is now correct.

## [0.2.0] - 2022-01-09

### Added

- You can now now send reminders to another channel.
- Ads for [DiscordNight](https://github.com/KillYoy/DiscordNight).
- Some tests, need a lot more to actually be useful.
- More docstrings.
- `Flake8`, `Mypy` and `types-dateparser` as developer dependencies.

### Changed

- More examples for file locations in .env.example.
- Two if else statements are now one line each.
- Moved "the" outside markdown link in the error message.
- bot_token now has a default value and we raise an error if it is the default value.
- Extra files are now in the `extras` folder.
- Added `build:` to docker-compose.yml.
- Small changes to the Dockerfile.
- License is now GPLv3.
- Expand pyproject.toml.
- Move settings to settings.py.

### Removed

- Removed TODO from the code that will never be done.
- .github/workflows directory is now gone.

### Fixed

- Spelling mistakes.

## [0.1.0] - 2021-07-23

### Added

- Use Poetry to manage dependencies.
- Shorten name if longer than 256 characters and description if longer than 1024 characters.
- You can now pause and resume reminders.
- You can now set intervals for reminders.
- You can now add cron jobs.

### Changed

- `/remind modify` now has a list of all reminders instead of needing an ID.
- `/remind pause` now has a list of all reminders instead of needing an ID.
- `/remind resume` now has a list of all reminders instead of needing an ID.
- `/remind remove` now has a list of all reminders instead of needing an ID.
- `/remind list` now has a list of all reminders instead of needing an ID.
- !remind is now /remind. You need to reinvite the bot with the `applications.commands` scope for this to work. It will
  also take up to an hour for the slash command to be registered.
