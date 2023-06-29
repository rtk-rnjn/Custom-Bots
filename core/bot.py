from __future__ import annotations

import asyncio
import datetime
import logging
import logging.handlers
import os
from collections import Counter
from typing import Any

import discord
import jishaku  # noqa: F401  # pylint: disable=unused-import
import pymongo
from discord.ext import commands
from discord.message import Message
from pymongo.errors import ConnectionFailure
from pymongo.results import DeleteResult, InsertOneResult

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

        self._was_ready: bool = False
        self.lock: "asyncio.Lock" = asyncio.Lock()
        self.timer_task: asyncio.Task | None = None
        self._current_timer: dict[str, Any] | None = {}
        self._have_data: asyncio.Event = asyncio.Event()
        self.reminder_event: asyncio.Event = asyncio.Event()

        self.message_cache: dict[int, Message] = {}

    def init_db(self) -> None:
        self.main_db = self.mongo["customBots"]  # type: ignore
        self.bot_configs = self.main_db["botConfigs"]
        self.timers = self.main_db["timerCollections"]
        self.giveaways = self.main_db["giveawayCollections"]

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
        if self._was_ready:
            return

        self._was_ready = True

        if not hasattr(self, "uptime"):
            self.uptime = discord.utils.utcnow()

        getattr(self.user, "id", None)

        logger.info("Logged in as %s", self.user)
        self.timer_task = self.loop.create_task(self.dispatch_timers())

    async def get_or_fetch_member(
        self,
        guild: discord.Guild,
        member_id: int | str | discord.Object,
        in_guild: bool = True,
    ) -> discord.Member | discord.User | None:
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
        entity = get_function(entity)
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

    async def get_active_timer(self, **filters: Any) -> dict:
        return await self.timers.find_one(
            filters, sort=[("expires_at", pymongo.ASCENDING)]
        )

    async def wait_for_active_timers(self, **filters: Any) -> dict:
        timers = await self.get_active_timer(**filters)
        logger.info("received timers: %s", timers)

        if timers:
            self._have_data.set()
            return timers

        self._have_data.clear()
        self._current_timer = None
        logger.info("waiting for timers")
        await self._have_data.wait()

        return await self.get_active_timer()

    async def dispatch_timers(self):
        try:
            logger.info("Starting timer dispatch")
            while not self.is_closed():
                timers = self._current_timer = await self.wait_for_active_timers(bot_id=self.user.id)  # type: ignore

                if timers is None:
                    continue

                now = discord.utils.utcnow().timestamp()

                if timers["expires_at"] > now:
                    await asyncio.sleep(timers["expires_at"] - now)

                await self.call_timer(self.timers, **timers)
                await asyncio.sleep(0)
        except (OSError, discord.ConnectionClosed, ConnectionFailure) as e:
            logger.error("Error dispatching timer", exc_info=True)
            if self.timer_task:
                self.timer_task.cancel()
                self.timer_task = self.loop.create_task(self.dispatch_timers())

        except asyncio.CancelledError:
            raise

    async def call_timer(self, collection, **data: Any):
        deleted: DeleteResult = await collection.delete_one({"_id": data["_id"]})

        if deleted.deleted_count == 0:
            return

        if data.get("_event_name"):
            self.dispatch(f"{data['_event_name']}_timer_complete", **data)
        else:
            self.dispatch("timer_complete", **data)

    async def short_time_dispatcher(self, collection, **data: Any):
        await asyncio.sleep(discord.utils.utcnow().timestamp() - data["expires_at"])

        await self.call_timer(collection, **data)

    async def create_timer(
        self,
        *,
        expires_at: float,
        _event_name: str | None = None,
        created_at: float | None = None,
        content: str | None = None,
        message: discord.Message | int | None = None,
        dm_notify: bool = False,
        is_todo: bool = False,
        extra: dict[str, Any] | None = None,
        **kw,
    ) -> InsertOneResult:
        collection = self.timers

        embed: dict[str, Any] | None = kw.get("embed_like") or kw.get("embed")
        mod_action: dict[str, Any] | None = kw.get("mod_action")
        cmd_exec_str: str | None = kw.get("cmd_exec_str")

        # fmt: off
        post = {
            "_id": message.id if isinstance(message, discord.Message) else message,
            "bot_id": self.user.id,  # type: ignore
            "_event_name": _event_name,
            "expires_at": expires_at,
            "created_at": (
                created_at
                or kw.get("created_at")
                or (
                    message.created_at.timestamp() if isinstance(message, discord.Message) else discord.utils.utcnow().timestamp()
                )
            ),
            "content": content,
            "embed": embed,
            "guild": message.guild.id if isinstance(message, discord.Message) and message.guild else "DM",
            "messageURL": message.jump_url if isinstance(message, discord.Message) else kw.get("messageURL"),
            "messageAuthor": message.author.id if isinstance(message, discord.Message) else kw.get("messageAuthor"),
            "messageChannel": message.channel.id if isinstance(message, discord.Message) else kw.get("messageChannel"),
            "dm_notify": dm_notify,
            "is_todo": is_todo,
            "mod_action": mod_action,
            "cmd_exec_str": cmd_exec_str,
            "extra": extra,
            **kw,
        }
        # fmt: on
        insert_data = await collection.insert_one(post)

        self._have_data.set()

        if self._current_timer and self._current_timer["expires_at"] > expires_at:
            self._current_timer = post

            if self.timer_task:
                self.timer_task.cancel()

                self.timer_task = self.loop.create_task(self.dispatch_timers())

        return insert_data

    async def delete_timer(self, **kw: Any) -> DeleteResult:
        collection = self.timers
        data = await collection.delete_one({"_id": kw["_id"]})
        delete_count = data.deleted_count
        if delete_count == 0:
            return data

        if (
            delete_count
            and self._current_timer
            and self._current_timer["_id"] == kw["_id"]
            and self.timer_task
        ):
            self.timer_task.cancel()
            self.timer_task = self.loop.create_task(self.dispatch_timers())
        return data

    async def restart_timer(self) -> bool:
        if self.timer_task:
            self.timer_task.cancel()
            self.timer_task = self.loop.create_task(self.dispatch_timers())
            return True
        return False

    async def get_or_fetch_message(
        self, channel: discord.TextChannel, message_id: int
    ) -> discord.Message | None:
        try:
            return self.message_cache[message_id]
        except KeyError:
            pass

        try:
            msg = await channel.fetch_message(message_id)
            self.message_cache[message_id] = msg
        except discord.HTTPException:
            return None

    async def on_error(self, event: str, *args, **kwargs) -> None:
        logger.error(
            "Error in event %s. Args %s. Kwargs %s", event, args, kwargs, exc_info=True
        )
