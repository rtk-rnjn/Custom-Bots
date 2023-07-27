"""MIT License.

Copyright (c) 2023 Ritik Ranjan

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import logging.handlers
import os
import re
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import aiohttp
import discord
import jishaku  # noqa: F401  # pylint: disable=unused-import
import pymongo
from colorama import Fore
from discord.ext import commands, tasks
from pymongo.errors import ConnectionFailure
from pymongo.results import DeleteResult, InsertOneResult

from cogs.help import Help
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


T = TypeVar("T")


class Bot(commands.Bot):  # pylint: disable=too-many-instance-attributes
    """Custom Bot implementation of commands.Bot."""

    mongo: Any
    uptime: datetime.datetime
    user: discord.ClientUser
    session: aiohttp.ClientSession
    guild_id: int
    sync_mongo: pymongo.MongoClient

    def __init__(self, config: Config) -> None:
        super().__init__(
            command_prefix=self.get_prefix,  # type: ignore
            intents=discord.Intents.all(),
            case_insensitive=True,
            strip_after_prefix=True,
            activity=config.activity,
            status=config.status,
            owner_ids=config.owner_ids,
            help_command=Help(),
        )
        self.cogs_to_load = config.cogs

        self.spam_control: commands.CooldownMapping = commands.CooldownMapping.from_cooldown(
            3,
            5,
            commands.BucketType.user,
        )
        self._auto_spam_count: Counter[int] = Counter()
        self._BotBase__cogs = (
            commands.core._CaseInsensitiveDict()
        )  # pylint: disable=protected-access, no-member, invalid-name

        self._was_ready: bool = False
        self.lock: asyncio.Lock = asyncio.Lock()
        self.timer_task: asyncio.Task | None = None
        self._current_timer: dict[str, Any] | None = {}
        self._have_data: asyncio.Event = asyncio.Event()
        self.reminder_event: asyncio.Event = asyncio.Event()

        self.message_cache: dict[int, discord.Message] = {}
        self.before_invoke(self.__before_invoke)

        self.__config = config
        self.__universal_db_writer = []

    @property
    def config(self) -> Config:
        """Return the bot's config."""
        return self.__config

    def init_db(self) -> None:
        """Initialize the database collection."""
        self.main_db = self.mongo["customBots"]  # type: ignore # pylint: disable=attribute-defined-outside-init
        self.timers = self.main_db["timerCollections"]  # pylint: disable=attribute-defined-outside-init
        self.giveaways = self.main_db["giveawayCollections"]  # pylint: disable=attribute-defined-outside-init
        self.ticket = self.main_db["ticketCollections"]  # pylint: disable=attribute-defined-outside-init
        self.main_config_configuration = self.main_db[  # pylint: disable=attribute-defined-outside-init
            "mainConfigCollection"
        ]
        self.main_config = self.main_config_configuration  # pylint: disable=attribute-defined-outside-init

    async def setup_hook(self) -> None:
        """Setup the bot."""
        await self.load_extension("jishaku")
        if len(self.cogs_to_load) == 1 and self.cogs_to_load[0] == "~":
            self.cogs_to_load = all_cogs

        for cog in self.cogs_to_load:
            try:
                await self.load_extension(cog)
            except commands.ExtensionNotFound:
                logger.warning("extension %s not found. Skipping.", cog)
                await self.log_bot_event(content=f"Extension {cog} not found. Skipping.", log_lvl="WARNING")
            except commands.ExtensionFailed as err:
                logger.warning("extension %s failed to load: %s", cog, err, exc_info=True)
                await self.log_bot_event(content=f"Extension {cog} failed to load: {err}", log_lvl="WARNING")
            except commands.NoEntryPointError:
                logger.warning("extension %s has no setup function. Skipping.", cog)
                await self.log_bot_event(content=f"Extension {cog} has no setup function. Skipping.", log_lvl="WARNING")
            except commands.ExtensionAlreadyLoaded:
                logger.warning("extension %s is already loaded. Skipping.", cog)
                await self.log_bot_event(content=f"Extension {cog} is already loaded. Skipping.", log_lvl="WARNING")
            else:
                logger.info("extension %s loaded", cog)
                await self.log_bot_event(content=f"Extension {cog} loaded", log_lvl="INFO")

        self.update_to_db.start()  # pylint: disable=no-member

    async def close(self) -> None:
        """Close the bot."""
        if self.timer_task:
            self.timer_task.cancel()

        if self.update_to_db.is_running():  # pylint: disable=no-member
            self.update_to_db.cancel()  # pylint: disable=no-member

        await self.session.close()

        await super().close()

    async def on_ready(self) -> None:
        """Bot startup, sets uptime."""
        if self._was_ready:
            return

        self._was_ready = True

        if not hasattr(self, "uptime"):
            self.uptime = discord.utils.utcnow()

        getattr(self.user, "id", None)

        logger.info("Logged in as %s", self.user)
        await self.log_bot_event(content=f"Logged in as {self.user}", log_lvl="INFO")
        self.timer_task = self.loop.create_task(self.dispatch_timers())

    async def on_message(self, message: discord.Message) -> None:  # pylint: disable=arguments-differ
        """Handle message events."""
        if message.author.bot or message.guild is None:
            return

        if re.fullmatch(rf"<@!?{self.user.id}>", message.content):
            await message.channel.send(f"Hello! My prefix is `{self.config.prefix}`")
            return

        await self.process_commands(message)

    async def get_or_fetch_member(
        self,
        guild: discord.Guild,
        member_id: int | str | discord.Object,
    ) -> discord.Member | None:
        """Get a member from cache or fetch if not found."""
        member_id = member_id.id if isinstance(member_id, discord.Object) else int(member_id)

        member = guild.get_member(member_id)
        if member is not None:
            return member

        try:
            return await guild.fetch_member(member_id)
        except discord.HTTPException:
            pass

        members = await guild.query_members(limit=1, user_ids=[member_id], cache=True)
        return members[0] if members else None

    async def getch(
        self,
        get_function: Callable[[int], T],
        fetch_function: Callable[[int], Awaitable[T]],
        entity: int,
    ) -> T | None:  # noqa: ANN401
        """Get an entity from cache or fetch if not found."""
        resolved = get_function(entity)
        if resolved is not None:
            return resolved

        try:
            return await fetch_function(entity)
        except discord.HTTPException:
            pass

        return None

    async def process_commands(self, message: discord.Message) -> None:  # pylint: disable=arguments-differ
        """Process commands and send errors if any."""
        ctx: Context = await self.get_context(message, cls=Context)

        if bucket := self.spam_control.get_bucket(message):
            if bucket.update_rate_limit(message.created_at.timestamp()):
                self._auto_spam_count[message.author.id] += 1
                if self._auto_spam_count[message.author.id] >= 3:
                    logger.debug("Auto spam detected, ignoring command. Context %s", ctx)
                    return
            else:
                self._auto_spam_count.pop(message.author.id, None)

        await self.invoke(ctx)

    async def on_command_error(  # pylint: disable=arguments-differ, disable=too-many-return-statements
        self,
        ctx: Context,
        error: commands.CommandError,
    ) -> discord.Message | None:
        """Handle command errors."""
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
            missing = [perm.replace("_", " ").replace("guild", "server").title() for perm in error.missing_permissions]
            if len(missing) > 2:
                fmt = f'{", ".join(missing[:-1])}, and {missing[-1]}'
            else:
                fmt = " and ".join(missing)
            return await ctx.reply(f"Bot is missing permissions: `{fmt}`")

        if isinstance(error, commands.MissingPermissions):
            if await self.is_owner(ctx.author):
                return await ctx.reinvoke()

            missing = [perm.replace("_", " ").replace("guild", "server").title() for perm in error.missing_permissions]
            if len(missing) > 2:
                fmt = f'{", ".join(missing[:-1])}, and {missing[-1]}'
            else:
                fmt = " and ".join(missing)
            return await ctx.reply(f"You need the following permission(s) to the run the command: `{fmt}`")

        if isinstance(error, commands.CommandOnCooldown):
            if await self.is_owner(ctx.author):
                return await ctx.reinvoke()

            now = discord.utils.utcnow() + datetime.timedelta(seconds=error.retry_after)
            discord_time = discord.utils.format_dt(now, "R")
            return await ctx.reply(f"This command is on cooldown. Try again in {discord_time}")

        if isinstance(
            error,
            commands.MissingRequiredArgument | commands.BadUnionArgument | commands.TooManyArguments,
        ):
            ctx.command.reset_cooldown(ctx)
            return await ctx.reply(f"Invalid Syntax. `{ctx.clean_prefix}help {ctx.command.qualified_name}` for more info.")

        if isinstance(error, commands.BadArgument):
            ctx.command.reset_cooldown(ctx)
            return await ctx.reply(f"Invalid argument: {error}")

        raise error

    async def get_active_timer(self, **filters: dict) -> dict:
        """Get the active timer."""
        return await self.timers.find_one(filters, sort=[("expires_at", pymongo.ASCENDING)])

    async def wait_for_active_timers(self, **filters: dict) -> dict:
        """Wait for the active timer."""
        timers = await self.get_active_timer(**filters)
        logger.info("received timers: %s", timers)
        await self.log_bot_event(content=f"Received timers from database: {timers}", log_lvl="INFO")

        if timers:
            self._have_data.set()
            return timers

        self._have_data.clear()
        self._current_timer = None
        logger.info("waiting for timers")
        await self.log_bot_event(content="Waiting for timers from database", log_lvl="INFO")

        await self._have_data.wait()

        return await self.get_active_timer()

    async def dispatch_timers(self) -> None:
        """Main loop for dispatching timers."""
        try:
            logger.info("Starting timer dispatch")
            await self.log_bot_event(content="Starting timer dispatch", log_lvl="INFO")
            while not self.is_closed():
                timers = self._current_timer = await self.wait_for_active_timers(bot_id=self.user.id)  # type: ignore

                if timers is None:
                    continue

                now = discord.utils.utcnow().timestamp()

                if timers["expires_at"] > now:
                    await asyncio.sleep(timers["expires_at"] - now)

                await self.call_timer(self.timers, **timers)
                await asyncio.sleep(0)
        except (OSError, discord.ConnectionClosed, ConnectionFailure):
            logger.exception("Error dispatching timer")
            if self.timer_task:
                self.timer_task.cancel()
                self.timer_task = self.loop.create_task(self.dispatch_timers())

        except asyncio.CancelledError:
            logger.info("Timer dispatch cancelled")
            await self.log_bot_event(content="Timer dispatch cancelled", log_lvl="INFO")
            raise

    async def call_timer(self, collection, **data: dict | float) -> None:  # noqa: ANN001
        """Call the timer and delete it."""
        deleted: DeleteResult = await collection.delete_one({"_id": data["_id"]})

        if deleted.deleted_count == 0:
            return

        if data.get("_event_name"):
            self.dispatch(f"{data['_event_name']}_timer_complete", **data)
        else:
            self.dispatch("timer_complete", **data)

    async def short_time_dispatcher(self, collection, **data: float) -> None:  # noqa: ANN001
        """Sleep and call the timer."""
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
        extra: dict[str, Any] | None = None,
        **kw,
    ) -> InsertOneResult:
        """Create a timer."""
        collection = self.timers

        embed: dict[str, Any] | None = kw.get("embed_like") or kw.get("embed")
        mod_action: dict[str, Any] | None = kw.get("mod_action")
        kw.get("cmd_exec_str")

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
            "mod_action": mod_action,
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

    async def delete_timer(self, **kw: dict) -> DeleteResult:
        """Delete a timer."""
        collection = self.timers
        data: DeleteResult = await collection.delete_one({"_id": kw["_id"]})
        delete_count = data.deleted_count
        if delete_count == 0:
            return data

        if delete_count and self._current_timer and self._current_timer["_id"] == kw["_id"] and self.timer_task:
            self.timer_task.cancel()
            self.timer_task = self.loop.create_task(self.dispatch_timers())
        return data

    async def restart_timer(self) -> bool:
        """Restart the timer."""
        if self.timer_task:
            self.timer_task.cancel()
            self.timer_task = self.loop.create_task(self.dispatch_timers())
            return True
        return False

    async def get_or_fetch_message(self, channel: discord.abc.Messageable, message_id: int) -> discord.Message | None:
        """Try to get a message from the cache or fetch it if it is not in the cache."""
        try:
            return self.message_cache[message_id]
        except KeyError:
            pass

        if msg := discord.utils.get(self.cached_messages, id=message_id):
            self.message_cache[message_id] = msg
            return msg

        try:
            async for msg in channel.history(
                limit=1,
                before=discord.Object(message_id + 1),
                after=discord.Object(message_id - 1),
            ):
                self.message_cache[msg.id] = msg
                return msg
        except (discord.Forbidden, discord.HTTPException):
            return None

    async def on_error(self, event: str, *args, **kwargs) -> None:  # pylint: disable=unused-argument
        """Log errors from events."""
        logger.error("Error in event %s.", event, exc_info=True)

    async def __before_invoke(self, ctx: Context) -> None:
        """Check if the command is disabled in the guild."""
        if not ctx.guild.chunked:
            await ctx.guild.chunk(cache=True)

        guild_id = self.config.guild_id

        if ctx.guild and guild_id and ctx.guild.id != guild_id and not await self.is_owner(ctx.author):
            await ctx.reply("This command is disabled in this guild.")
            msg = "This command is disabled in this guild."
            raise commands.DisabledCommand(msg)

    async def get_prefix(self, message: discord.Message) -> list[str]:  # pylint: disable=arguments-differ
        """Get the prefix for the guild."""
        prefix = self.config.prefix
        comp = re.compile(f"^({re.escape(prefix)}).*", flags=re.I)
        match = comp.match(message.content)
        if match is not None:
            prefix = match[1]

        return commands.when_mentioned_or(prefix)(self, message)

    def add_to_db_writer(self, *, collection: str, entity: pymongo.UpdateOne | pymongo.UpdateMany) -> None:
        """Add an entity to the database writer."""
        self.__universal_db_writer.append((collection, entity))

    @tasks.loop(hours=1)
    async def update_to_db(self) -> None:
        """Update the database."""
        async with self.lock:
            logger.debug("lock acquird, writing to database")
            group: dict[str, list[pymongo.UpdateOne | pymongo.UpdateMany]] = {}
            for collection, entity in self.__universal_db_writer:
                group.setdefault(collection, []).append(entity)

            for collection, entities in group.items():
                col = self.sync_mongo["customBots"][collection]
                await asyncio.to_thread(col.bulk_write, entities, ordered=False)

            logger.debug("writing to database done, releasing lock and clearning the writer")
            self.__universal_db_writer = []

    async def execute_webhook_from_url(
        self,
        webhook_url: str,
        *,
        error_supperssor: tuple | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> discord.WebhookMessage | None:
        """Execute a webhook from a webhook url."""
        webhook = discord.Webhook.from_url(webhook_url, session=self.session, client=self, bot_token=self.config.token)
        return await self.execute_webhook(webhook, error_supperssor=error_supperssor, **kwargs)

    async def execute_webhook(
        self,
        webhook: discord.Webhook,
        *,
        error_supperssor: tuple | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> discord.WebhookMessage | None:
        """Execute a webhook."""
        error_supperssor = error_supperssor or (discord.NotFound, discord.Forbidden)

        try:
            return await webhook.send(**kwargs)
        except error_supperssor:
            pass

    COLOR_FMT = {
        "INFO": Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR": Fore.RED,
    }

    async def log_bot_event(self, **kw: Any) -> discord.WebhookMessage | None:  # noqa: ANN401
        """Log a bot event."""
        now = discord.utils.utcnow()
        now = f'{Fore.CYAN}{now.strftime("%Y-%m-%d %H:%M:%S")}'
        log_lvl = kw.pop("log_lvl", "INFO")
        log_lvl = f"{self.COLOR_FMT.get(log_lvl, Fore.WHITE)}{log_lvl}"

        if url := self.config["botlog_webhook"]:
            if content := kw.pop("content", None):
                cntnt = f"```ansi\n{now} - {log_lvl} - {Fore.WHITE}{content}\n```"
                kw["content"] = cntnt

            return await self.execute_webhook_from_url(url, **kw)
