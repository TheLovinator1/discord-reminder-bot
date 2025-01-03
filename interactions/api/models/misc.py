"""This file is only here so we can unpickle the old jobs."""

from __future__ import annotations


class Snowflake:
    """A class to represent a Discord snowflake."""

    __slots__: list[str] = ["_snowflake"]

    def __init__(self, snowflake: int | str | Snowflake) -> None:
        """Initialize the Snowflake object.

        Args:
            snowflake (int | str | Snowflake): The snowflake to store.
        """
        self._snowflake = str(snowflake)

    def __str__(self) -> str:
        """Return the snowflake as a string."""
        return self._snowflake

    def __int__(self) -> int:
        """Return the snowflake as an integer."""
        return int(self._snowflake)
