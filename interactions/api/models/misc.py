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

    def __eq__(self, other: object) -> bool:
        """Compare the snowflake with another value.

        Supports comparison with int, str, and other Snowflake objects.

        Args:
            other: The value to compare with.

        Returns:
            True if the snowflake values match, False otherwise.
        """
        if isinstance(other, Snowflake):
            return self._snowflake == other._snowflake
        if isinstance(other, int | str):
            return self._snowflake == str(other)
        return NotImplemented

    def __hash__(self) -> int:
        """Return a hash based on the integer value.

        Allows Snowflake objects to be used in sets and as dict keys.
        """
        return int(self._snowflake)
