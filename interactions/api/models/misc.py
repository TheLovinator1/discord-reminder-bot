"""This file is only here so we can unpickle the old jobs."""

from __future__ import annotations


class Snowflake:
    __slots__: list[str] = ["_snowflake"]

    def __init__(self, snowflake: int | str | Snowflake) -> None:
        self._snowflake = str(snowflake)

    def __str__(self) -> str:
        return self._snowflake

    def __int__(self) -> int:
        return int(self._snowflake)
