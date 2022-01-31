# Changelog

All notable changes to discord-reminder-bot will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Updated dependencies:
  - Updating pluggy (0.13.1 -> 1.0.0)
  - Updating types-dateparser (1.0.10 -> 1.0.13)
  - Updating types-pytz (2021.3.3 -> 2021.3.4)
  - Updating multidict (5.2.0 -> 6.0.2)
  - Updating pyparsing (3.0.6 -> 3.0.7)
  - Updating regex (2021.11.10 -> 2022.1.18)
  - Updating sqlalchemy (1.4.29 -> 1.4.31)

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
- !remind is now /remind. You need to reinvite the bot with the `applications.commands` scope for this to work. It will also take up to an hour for the slash command to be registered.
