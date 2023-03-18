import dataclasses
from datetime import datetime

import dateparser
from dateparser.conf import SettingValidationError

from discord_reminder_bot.settings import config_timezone


@dataclasses.dataclass
class ParsedTime:
    """This is used when parsing a time or date from a string.

    We use this when adding a job with /reminder add.

    Attributes:
        date_to_parse: The string we parsed the time from.
        err: True if an error was raised when parsing the time.
        err_msg: The error message.
        parsed_time: The parsed time we got from the string.
    """

    date_to_parse: str | None = None
    err: bool = False
    err_msg: str = ""
    parsed_time: datetime | None = None


def parse_time(date_to_parse: str, timezone: str = config_timezone) -> ParsedTime:
    """Parse the datetime from a string.

    Args:
        date_to_parse: The string we want to parse.
        timezone: The timezone to use when parsing. This will be used when typing things like "22:00".

    Returns:
        ParsedTime
    """
    try:
        parsed_date: datetime | None = dateparser.parse(
            f"{date_to_parse}",
            settings={
                "PREFER_DATES_FROM": "future",
                "TIMEZONE": f"{timezone}",
                "TO_TIMEZONE": f"{timezone}",
            },
        )
    except SettingValidationError as e:
        return ParsedTime(
            err=True,
            err_msg=f"Timezone is possible wrong?: {e}",
            date_to_parse=date_to_parse,
        )
    except ValueError as e:
        return ParsedTime(
            err=True,
            err_msg=f"Failed to parse date. Unknown language: {e}",
            date_to_parse=date_to_parse,
        )
    except TypeError as e:
        return ParsedTime(err=True, err_msg=f"{e}", date_to_parse=date_to_parse)
    return (
        ParsedTime(parsed_time=parsed_date, date_to_parse=date_to_parse)
        if parsed_date
        else ParsedTime(
            err=True,
            err_msg="Could not parse the date.",
            date_to_parse=date_to_parse,
        )
    )
