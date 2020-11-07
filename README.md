Discord-reminder-bot
=========

Discord bot that allows you to set reminders.

## Installation

* Install latest version of Python 3.
* Install pipenv
    * `pip install pipenv`
* Install requirements and make virtual enviroment
    * `pipenv install`
* Rename .env-example to .env and fill in.
* Start the bot
    * `pipenv run python main.py`

## Autostart - Linux (systemd)
* Keep services running after logout
    * `loginctl enable-linger`
* Move service file to correct location (You may have to modify WorkingDirectory and/or ExecStart)
    * `cp discord-reminder-bot.service ~/.config/systemd/user/discord-reminder-bot.service`
* Start bot now and at boot
    * `systemctl --user enable --now discord-reminder-bot`


systemd examples:
* Start bot automatically at boot
    *  `systemctl --user enable discord-reminder-bot`
* Don't start automatically
    *  `systemctl --user disable discord-reminder-bot`
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
* Steam: https://steamcommunity.com/id/TheLovinator/

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details