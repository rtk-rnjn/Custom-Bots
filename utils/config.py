from __future__ import annotations

import contextlib
import json
import os
from typing import Any

import discord
from pymongo import MongoClient

from .converters import convert_bool

with contextlib.suppress(ImportError):
    from dotenv import dotenv_values, load_dotenv  # type: ignore

    load_dotenv()
    dotenv_values(".env")

with open("bots.json") as f:
    bots = json.load(f)

master_owner = bots["master_owner"]
all_cogs = bots["all_cogs"]

__all__ = ("Config", "bots", "master_owner", "all_cogs", "ENV", "MONGO_CLIENT", "BOT_CONFIGS")


class Config:
    def __init__(self, **kwargs: str | int | bool | list[str]) -> None:
        # fmt: off
        self._id: int         = kwargs.pop("id")        # type: ignore
        self._name: str       = kwargs.pop("name")      # type: ignore
        self._token: str      = kwargs.get("token")     # type: ignore
        self._owner_id: int   = kwargs.pop("owner_id")  # type: ignore
        self._cogs: list[str] = kwargs.pop("cogs")      # type: ignore
        self._prefix: str     = kwargs.pop("prefix")    # type: ignore
        self._status: str     = kwargs.pop("status")    # type: ignore
        self._activity: str   = kwargs.pop("activity")  # type: ignore
        self._media: str      = kwargs.pop("media")     # type: ignore
        self._guild_id: int   = kwargs.pop("guild_id")  # type: ignore
        # fmt: on

        """
        {
            "id": INT,
            "name": STR,
            "prefix": STR,
            "status": STR,
            "activity": STR,
            "token": STR,
            "media": STR,
            "guild_id": INT,
            "owner_id": INT,
            "cogs": [
                STR
            ]
        }
        """

        for key, value in kwargs.items():
            setattr(self, key, value)

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
        return discord.Activity(type=getattr(discord.ActivityType, self._activity), name=self._media)

    @property
    def guild_id(self) -> int:
        return self._guild_id

    @classmethod
    def from_id(cls, id: int) -> Config:  # type: ignore
        for bot in bots["bots"]:
            if bot["id"] == id:
                return cls(**bot)


class Null:
    def __repr__(self) -> str:
        return "Null()"

    def __str__(self) -> str:
        return "Null()"

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: Any) -> bool:
        return isinstance(other, Null)

    def __getattr__(self, name: str) -> Null:
        return self

    def __getitem__(self, name: str) -> Null:
        return self


ANY = Null | str | list | bool | dict | int | None


class Environment:
    def __init__(self):
        self.__dict = os.environ

    def __getattr__(self, name: str) -> ANY:
        return self.parse_entity(self.__dict.get(name))

    def parse_entity(self, entity: Any) -> ANY:
        if entity is None:
            return Null()

        entity = str(entity)

        try:
            return json.loads(entity)
        except json.JSONDecodeError:
            pass

        if entity.isdigit():
            return int(entity)

        if _bool := convert_bool(entity):
            return _bool

        if "," in entity:
            # list
            # recursive call
            return [self.parse_entity(e) for e in entity.split(",")]

        return entity

    def __getitem__(self, name: str) -> ANY:
        return self.__getattr__(name)


ENV = Environment()
MONGO_CLIENT = MongoClient(str(ENV.MONGO_URI))


def load_config(bot_id: int | None = None) -> Config | list[Config] | None:
    collection = MONGO_CLIENT["customBots"]["mainConfigCollection"]

    if not bot_id:
        ls = []
        for data in collection.find({}, {"_id": 0}):
            ls.append(Config(**data))

        return ls

    data = collection.find_one({"id": bot_id}, {"_id": 0})
    return Config(**data) if data else None


BOT_CONFIGS = load_config()
if not isinstance(BOT_CONFIGS, list):
    BOT_CONFIGS = [BOT_CONFIGS]
