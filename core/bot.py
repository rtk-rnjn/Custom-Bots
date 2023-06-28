from __future__ import annotations

import logging.handlers
import os
from typing import Any

import discord
import jishaku  # noqa: F401  # pylint: disable=unused-import
from discord.ext import commands
from discord.message import Message

from utils import Config, CustomFormatter, all_cogs

from .context import Context

os.environ["JISHAKU_HIDE"] = "True"
os.environ["JISHAKU_NO_UNDERSCORE"] = "True"
os.environ["JISHAKU_NO_DM_TRACEBACK"] = "True"
os.environ["JISHAKU_FORCE_PAGINATOR"] = "True"

discord.utils.setup_logging(
    formatter=CustomFormatter(),
    handler=logging.handlers.RotatingFileHandler(
        filename=".log",
        encoding="utf-8",
        maxBytes=1 * 1024 * 1024,  # 1 MiB
        backupCount=1,  # Rotate through 1 files
    ),
)


class Bot(commands.Bot):
    def __init__(self, config: Config, *args, **kwargs):
        super().__init__(
            command_prefix=config.prefix,
            intents=discord.Intents.all(),
            case_insensitive=True,
            strip_after_prefix=True,
            activity=config.activity,
            status=config.status,
            owner_ids=config.owner_ids,
        )
        self.cogs_to_load = config.cogs
        self.session = None

    async def setup_hook(self) -> None:
        await self.load_extension("jishaku")
        if len(self.cogs_to_load) == 1 and self.cogs_to_load[0] == "~":
            self.cogs_to_load = all_cogs

        for cog in self.cogs_to_load:
            try:
                await self.load_extension(cog)
            except commands.ExtensionNotFound:
                print(f"Extension {cog} not found. Skipping.")
            except commands.ExtensionFailed as e:
                print(f"Extension {cog} failed to load. Skipping.")
                print(e)
            else:
                print(f"Loaded extension {cog}.")

    async def on_ready(self) -> None:
        if not hasattr(self, "uptime"):
            self.uptime = discord.utils.utcnow()

        bot_id = getattr(self.user, "id", None)

        print(f"Logged in as {self.user} ({bot_id})")

    async def get_or_fetch_member(
        self,
        guild: discord.Guild,
        member_id: int | str | discord.Object,
        in_guild: bool = True,
    ) -> discord.Member | discord.User | None:
        """|coro|

        Looks up a member in cache or fetches if not found.

        Parameters
        -----------
        guild: Guild
            The guild to look in.
        member_id: int
            The member ID to search for.

        Returns
        ---------
        Optional[Member]
            The member or None if not found.
        """

        member_id = (
            member_id.id if isinstance(member_id, discord.Object) else int(member_id)
        )

        if not in_guild:
            return await self.getch(self.get_user, self.fetch_user, int(member_id))
        member = guild.get_member(member_id)
        if member is not None:
            return member

        try:
            return await guild.fetch_member(member_id)
        except discord.HTTPException:
            pass

        members = await guild.query_members(limit=1, user_ids=[member_id], cache=True)
        return members[0] if members else None

    async def getch(self, get_function, fetch_function, entity) -> Any:
        """|coro|

        Gets an entity from cache or fetches if not found.

        Parameters
        -----------
        get_function: Callable
            The function to get the entity from cache.
        fetch_function: Callable
            The function to fetch the entity if not found in cache.
        entity: Any
            The entity to search for.

        Returns
        ---------
        Any
            The entity or None if not found.
        """
        entity = await get_function(entity)
        if entity is not None:
            return entity

        try:
            return await fetch_function(entity)
        except discord.HTTPException:
            pass

        return None

    async def process_commands(self, message: Message) -> None:
        ctx: Context = await self.get_context(message, cls=Context)
        await self.invoke(ctx)
