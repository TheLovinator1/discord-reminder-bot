# database.py
from __future__ import annotations

from typing import Any

from sqlalchemy import Boolean, Column, Engine, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from discord_reminder_bot.settings import DATA_DIR

url: str = f"sqlite:///{DATA_DIR}/guilds.sqlite3?check_same_thread=False&timeout=10&journal_mode=WAL"
engine: Engine = create_engine(url=url, echo=True)
Base: Any = declarative_base()


class GuildsDB(Base):
    __tablename__: str = "guilds"

    # The guild id
    guild_id = Column(Integer, primary_key=True)

    # The timezone that time of day should be converted from (For example 22:00)
    timezone = Column(String)

    # If this is true, only admins can use the bot
    admin_only = Column(Boolean)

    # The list of admins that can use the bot with admin_only enabled
    admins = Column(String)

    # If the bot is enabled
    bot_enabled = Column(Boolean)


Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def save_guilds(guild: GuildsDB) -> None:
    """Save guild settings to the database.

    Args:
        guild: The guild object containing the settings to be saved.

    Returns:
        None
    """
    session = Session()

    guild_settings_db = GuildsDB(
        guild_id=guild.guild_id,
        timezone=guild.timezone,
        webhook_url=guild.webhook_url,
        admins=",".join(str(admin) for admin in guild.admins),
        admin_only=guild.admin_only,
        bot_enabled=guild.bot_enabled,
    )

    session.add(guild_settings_db)
    session.commit()
    session.close()


def get_guild(guild_id: int) -> GuildsDB:
    """Get guild settings from the database.

    Args:
        guild_id: The id of the guild to get the settings for.

    Returns:
        GuildsDB: The guild settings.
    """
    session = Session()
    guild: GuildsDB | None = (
        session.query(GuildsDB).filter_by(guild_id=guild_id).first()
    )
    session.close()
    return guild
