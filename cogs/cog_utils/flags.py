from __future__ import annotations

from typing import Annotated

import discord
from discord.ext import commands

from utils import ShortTime, convert_bool


class AuditFlag(commands.FlagConverter, case_insensitive=True, prefix="--", delimiter=" "):
    guild: discord.Guild | None = commands.flag(
        name="guild",
        aliases=["g"],
        default=None,
        description="Filter by guild",
        override=True,
    )

    limit: int | None = commands.flag(
        name="limit",
        aliases=["l", "size"],
        default=100,
        description="Limit the number of actions to fetch",
        override=True,
    )

    action: str | None = commands.flag(
        name="action",
        aliases=["act"],
        default=None,
        description="Filter by action",
        override=True,
    )

    before: ShortTime | None = commands.flag(
        name="before",
        aliases=["b", "bf"],
        default=None,
        description="Filter actions before this time",
        override=True,
    )

    after: ShortTime | None = commands.flag(
        name="after",
        aliases=["a", "af"],
        default=None,
        description="Filter actions after this time",
        override=True,
    )

    oldest_first: Annotated[bool | None, convert_bool] = commands.flag(
        name="oldest_first",
        aliases=["of", "oldest-first"],
        default=None,
        description="Sort by oldest first",
        override=True,
    )

    user: discord.User | discord.Member | None = commands.flag(
        name="user",
        aliases=["member", "u", "m"],
        default=None,
        description="Filter by user",
        override=True,
    )
