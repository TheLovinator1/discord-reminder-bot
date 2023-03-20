import re
from datetime import datetime
from typing import TYPE_CHECKING

import dateparser
import interactions
import pytz
from apscheduler.job import Job
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from interactions.ext.paginator import Page

from discord_reminder_bot.create_pages import (
    _get_pages,
    _get_pause_or_unpause_button,
    _get_row_of_buttons,
    _get_trigger_text,
    _make_button,
    _pause_job,
    _unpause_job,
)
from discord_reminder_bot.main import send_to_discord

if TYPE_CHECKING:
    from collections.abc import Generator


def _test_pause_unpause_button(job: Job, button_label: str) -> None:
    button2: interactions.Button | None = _get_pause_or_unpause_button(job)
    assert button2
    assert button2.label == button_label
    assert button2.style == interactions.ButtonStyle.PRIMARY
    assert button2.type == interactions.ComponentType.BUTTON
    assert button2.emoji is None
    assert button2.custom_id == button_label.lower()
    assert button2.url is None
    assert button2.disabled is None


class TestCountdown:
    jobstores: dict[str, SQLAlchemyJobStore] = {"default": SQLAlchemyJobStore(url="sqlite:///:memory")}
    job_defaults: dict[str, bool] = {"coalesce": True}
    scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        timezone=pytz.timezone("Europe/Stockholm"),
        job_defaults=job_defaults,
    )

    parsed_date: datetime | None = dateparser.parse(
        "18 January 2040",
        settings={
            "PREFER_DATES_FROM": "future",
            "TO_TIMEZONE": "Europe/Stockholm",
        },
    )
    assert parsed_date

    run_date: str = parsed_date.strftime("%Y-%m-%d %H:%M:%S")
    normal_job: Job = scheduler.add_job(
        send_to_discord,
        run_date=run_date,
        kwargs={
            "channel_id": 865712621109772329,
            "message": "Running PyTest",
            "author_id": 126462229892694018,
        },
    )

    cron_job: Job = scheduler.add_job(
        send_to_discord,
        "cron",
        minute="0",
        kwargs={
            "channel_id": 865712621109772329,
            "message": "Running PyTest",
            "author_id": 126462229892694018,
        },
    )

    interval_job: Job = scheduler.add_job(
        send_to_discord,
        "interval",
        minutes=1,
        kwargs={
            "channel_id": 865712621109772329,
            "message": "Running PyTest",
            "author_id": 126462229892694018,
        },
    )

    def test_get_trigger_text(self) -> None:  # noqa: ANN101
        # FIXME: This try except train should be replaced with a better solution lol
        trigger_text: str = _get_trigger_text(self.normal_job)
        try:
            regex: str = r"2040-01-18 00:00 \(in \d+ days, \d+ hours, \d+ minutes\)"
            assert re.match(regex, trigger_text)
        except AssertionError:
            try:
                regex2: str = r"2040-01-18 00:00 \(in \d+ days, \d+ minutes\)"
                assert re.match(regex2, trigger_text)
            except AssertionError:
                regex3: str = r"2040-01-18 00:00 \(in \d+ days\, \d+ minutes\)"
                assert re.match(regex3, trigger_text)

    def test_make_button(self) -> None:  # noqa: ANN101
        button_name: str = "Test"

        button: interactions.Button = _make_button(label=button_name, style=interactions.ButtonStyle.PRIMARY)
        assert button.label == button_name
        assert button.style == interactions.ButtonStyle.PRIMARY
        assert button.custom_id == button_name.lower()
        assert button.disabled is None
        assert button.emoji is None

    def test_get_pause_or_unpause_button(self) -> None:  # noqa: ANN101
        button: interactions.Button | None = _get_pause_or_unpause_button(self.normal_job)
        assert button is None

        _test_pause_unpause_button(self.cron_job, "Pause")
        self.cron_job.pause()

        _test_pause_unpause_button(self.cron_job, "Unpause")
        self.cron_job.resume()

        _test_pause_unpause_button(self.interval_job, "Pause")
        self.interval_job.pause()

        _test_pause_unpause_button(self.interval_job, "Unpause")
        self.interval_job.resume()

    def test_get_row_of_buttons(self) -> None:  # noqa: ANN101
        row: interactions.ActionRow = _get_row_of_buttons(self.normal_job)
        assert row
        assert row.components

        # A normal job should have 2 buttons, edit and delete
        assert len(row.components) == 2  # noqa: PLR2004

        row2: interactions.ActionRow = _get_row_of_buttons(self.cron_job)
        assert row2
        assert row2.components

        # A cron job should have 3 buttons, edit, delete and pause/unpause
        assert len(row2.components) == 3  # noqa: PLR2004

        # A cron job should have 3 buttons, edit, delete and pause/unpause
        assert len(row2.components) == 3  # noqa: PLR2004

    def test_get_pages(self) -> None:  # noqa: ANN101
        ctx = None  # TODO: We should check ctx as well and not only channel id
        channel: interactions.Channel = interactions.Channel(id=interactions.Snowflake(865712621109772329))

        pages: Generator[Page, None, None] = _get_pages(job=self.normal_job, channel=channel, ctx=ctx)  # type: ignore  # noqa: PGH003, E501
        assert pages

        for page in pages:
            assert page
            assert page.title == "Running PyTest"
            assert page.components
            assert page.embeds
            assert page.embeds.fields is not None  # type: ignore  # noqa: PGH003
            assert page.embeds.fields[0].name == "**Channel:**"  # type: ignore  # noqa: PGH003
            assert page.embeds.fields[0].value == "#"  # type: ignore  # noqa: PGH003
            assert page.embeds.fields[1].name == "**Message:**"  # type: ignore  # noqa: PGH003
            assert page.embeds.fields[1].value == "Running PyTest"  # type: ignore  # noqa: PGH003
            assert page.embeds.fields[2].name == "**Trigger:**"  # type: ignore  # noqa: PGH003
            trigger_text: str = page.embeds.fields[2].value  # type: ignore  # noqa: PGH003

            # FIXME: This try except train should be replaced with a better solution lol
            try:
                regex: str = r"2040-01-18 00:00 \(in \d+ days, \d+ hours, \d+ minutes\)"
                assert re.match(regex, trigger_text)
            except AssertionError:
                try:
                    regex2: str = r"2040-01-18 00:00 \(in \d+ days, \d+ minutes\)"
                    assert re.match(regex2, trigger_text)
                except AssertionError:
                    regex3: str = r"2040-01-18 00:00 \(in \d+ days\, \d+ minutes\)"
                    assert re.match(regex3, trigger_text)

            # Check if type is Page
            assert isinstance(page, Page)

    def test_pause_job(self) -> None:  # noqa: ANN101
        assert _pause_job(self.interval_job, self.scheduler) == f"Job {self.interval_job.id} paused."
        assert _pause_job(self.cron_job, self.scheduler) == f"Job {self.cron_job.id} paused."
        assert _pause_job(self.normal_job, self.scheduler) == f"Job {self.normal_job.id} paused."

    def test_unpause_job(self) -> None:  # noqa: ANN101
        assert _unpause_job(self.interval_job, self.scheduler) == f"Job {self.interval_job.id} unpaused."
        assert _unpause_job(self.cron_job, self.scheduler) == f"Job {self.cron_job.id} unpaused."
        assert _unpause_job(self.normal_job, self.scheduler) == f"Job {self.normal_job.id} unpaused."
