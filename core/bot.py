from __future__ import annotations

import datetime
import logging
import logging.handlers
import os
from collections import Counter
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

logger = logging.getLogger("bot")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())
logger.addHandler(handler)


class Bot(commands.Bot):
    def __init__(self, config: Config, *args, **kwargs):
        super().__init__(
            command_prefix=commands.when_mentioned_or(config.prefix),
            intents=discord.Intents.all(),
            case_insensitive=True,
            strip_after_prefix=True,
            activity=config.activity,
            status=config.status,
            owner_ids=config.owner_ids,
        )
        self.cogs_to_load = config.cogs
        self.session = None

        self.spam_control: "commands.CooldownMapping" = (
            commands.CooldownMapping.from_cooldown(3, 5, commands.BucketType.user)
        )
        self._auto_spam_count: "Counter[int]" = Counter()
        self._BotBase__cogs = commands.core._CaseInsensitiveDict()

    async def setup_hook(self) -> None:
        await self.load_extension("jishaku")
        if len(self.cogs_to_load) == 1 and self.cogs_to_load[0] == "~":
            self.cogs_to_load = all_cogs

        for cog in self.cogs_to_load:
            try:
                await self.load_extension(cog)
            except commands.ExtensionNotFound:
                logger.warning("extension %s not found. Skipping.", cog)
            except commands.ExtensionFailed as e:
                logger.warning("extension %s failed to load: %s", cog, e, exc_info=True)
            except commands.NoEntryPointError:
                logger.warning("extension %s has no setup function. Skipping.", cog)
            except commands.ExtensionAlreadyLoaded:
                logger.warning("extension %s is already loaded. Skipping.", cog)
            else:
                logger.info("extension %s loaded", cog)

    async def on_ready(self) -> None:
        if not hasattr(self, "uptime"):
            self.uptime = discord.utils.utcnow()

        bot_id = getattr(self.user, "id", None)

        logger.info("Logged in as %s", self.user)

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

        if bucket := self.spam_control.get_bucket(message):
            if bucket.update_rate_limit(message.created_at.timestamp()):
                self._auto_spam_count[message.author.id] += 1
                if self._auto_spam_count[message.author.id] >= 3:
                    logger.debug(
                        "Auto spam detected, ignoring command. Context %s", ctx
                    )
                    return
            else:
                self._auto_spam_count.pop(message.author.id, None)
        await self.invoke(ctx)

    # TODO: Add timers

    async def on_command_error(self, ctx: Context, error: commands.CommandError):
        await self.wait_until_ready()

        if hasattr(ctx.command, "on_error"):
            return

        # get the original exception
        error = getattr(error, "original", error)

        ignore = (
            commands.CommandNotFound,
            discord.NotFound,
            discord.Forbidden,
            commands.PrivateMessageOnly,
            commands.NotOwner,
        )

        if isinstance(error, ignore):
            return

        if isinstance(error, commands.BotMissingPermissions):
            missing = [
                perm.replace("_", " ").replace("guild", "server").title()
                for perm in error.missing_permissions
            ]
            if len(missing) > 2:
                fmt = f'{", ".join(missing[:-1])}, and {missing[-1]}'
            else:
                fmt = " and ".join(missing)
            return await ctx.send(f"Bot is missing permissions: `{fmt}`")

        if isinstance(error, commands.MissingPermissions):
            missing = [
                perm.replace("_", " ").replace("guild", "server").title()
                for perm in error.missing_permissions
            ]
            if len(missing) > 2:
                fmt = f'{", ".join(missing[:-1])}, and {missing[-1]}'
            else:
                fmt = " and ".join(missing)
            return await ctx.send(
                f"You need the following permission(s) to the run the command: `{fmt}`"
            )

        if isinstance(error, commands.CommandOnCooldown):
            now = discord.utils.utcnow() + datetime.timedelta(seconds=error.retry_after)
            discord_time = discord.utils.format_dt(now, "R")
            return await ctx.send(
                f"This command is on cooldown. Try again in {discord_time}"
            )

        if isinstance(
            error,
            (
                commands.MissingRequiredArgument,
                commands.BadUnionArgument,
                commands.TooManyArguments,
            ),
        ):
            ctx.command.reset_cooldown(ctx)  # type: ignore
            return await ctx.send(
                f"Invalid Syntax. `{ctx.clean_prefix}help {ctx.invoked_with}` for more info."
            )

        if isinstance(error, commands.BadArgument):
            ctx.command.reset_cooldown(ctx)  # type: ignore
            return await ctx.send(f"Invalid argument: {error}")

        # return await ctx.send(f"Error: {error}")
