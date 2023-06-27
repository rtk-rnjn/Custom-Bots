from __future__ import annotations

import contextlib
import json
import os

import discord

with contextlib.suppress(ImportError):
    from dotenv import dotenv_values, load_dotenv  # type: ignore

    load_dotenv()
    dotenv_values(".env")


with open("bots.json") as f:
    bots = json.load(f)

master_owner = bots["master_owner"]
all_cogs = bots["all_cogs"]

__all__ = ("Config", "bots", "master_owner", "all_cogs")


class Config:
    def __init__(self, **kwargs: str | int | bool | list[str]) -> None:
        # fmt: off
        self._id: int         = kwargs.pop("id")              # type: ignore
        self._name: str       = kwargs.pop("name")            # type: ignore
        self._token: str      = os.environ.get(f"BOT_{self.id}")  # type: ignore
        self._owner_id: int   = kwargs.pop("owner_id")        # type: ignore
        self._cogs: list[str] = kwargs.pop("cogs")            # type: ignore
        self._prefix: str     = kwargs.pop("prefix")          # type: ignore
        self._status: str     = kwargs.pop("status")          # type: ignore
        self._activity: str   = kwargs.pop("activity")        # type: ignore
        self._media: str      = kwargs.pop("media")           # type: ignore
        # fmt: on

    def __repr__(self) -> str:
        return f"<Config id={self.id} name={self.name}>"

    def __str__(self) -> str:
        return self.name

    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def token(self) -> str:
        return self._token

    @property
    def owner_id(self) -> int:
        return self._owner_id

    @property
    def owner_ids(self) -> set[int]:
        return {self.owner_id, master_owner}

    @property
    def cogs(self) -> list[str]:
        return self._cogs

    @property
    def prefix(self) -> str:
        return self._prefix

    @property
    def status(self) -> discord.Status:
        return getattr(discord.Status, self._status)

    @property
    def activity(self) -> discord.Activity:
        return discord.Activity(
            type=getattr(discord.ActivityType, self._activity), name=self._media
        )

    @classmethod
    def from_id(cls, id: int) -> Config:  # type: ignore
        for bot in bots["bots"]:
            if bot["id"] == id:
                return cls(**bot)
