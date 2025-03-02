This is a Discord.py bot that allows you to set date, cron and interval reminders with APScheduler. Dates are parsed using dateparser.

Use type annotation/hints.

Use try-except blocks.

Add logging.

Write Google style docstrings.

Add helpful message when using assert. Use f-strings.

Docstrings that doesn't return anything should not have a return section.

A function docstring should describe the function's behavior, arguments, side effects, exceptions, return values, and any other information that may be relevant to the user.

Including the exception object in the log message is redundant.

We use Github.

Channel reminders have the following kwargs: "channel_id", "message", "author_id".

User DM reminders have the following kwargs: "user_id", "guild_id", "message".

Bot has the following commands:

"/remind add message:<str> time:<str> dm_and_current_channel:<bool> user:<user> channel:<channel>"

"/remind remove id:<job_id>"

"/remind edit id:<job_id>"

"/remind pause_unpause id:<job_id>"

"/remind list"

"/remind cron message:<str> year:<int> month:<int> day:<int> week:<int> day_of_week:<str> hour:<int> minute:<int> second:<int> start_date:<str> end_date:<str> timezone:<str> jitter:<int> channel:<channel> user:<user> dm_and_current_channel:<bool>"

"/remind interval message:<str> weeks:<int> days:<int> hours:<int> minutes:<int> seconds:<int> start_date:<str> end_date:<str> timezone:<str> jitter:<int> channel:<channel> user:<user> dm_and_current_channel:<bool>"
