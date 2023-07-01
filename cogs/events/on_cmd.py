from __future__ import annotations

import asyncio
import logging

from discord.ext import tasks
from pymongo import UpdateOne

from core import Bot, Cog, Context

log = logging.getLogger("events.on_cmd")


class OnCommand(Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.__commands_invoked = []
        self.collection = bot.mongo.customBots.commandCollection  # type: ignore
        self.__update_commands.start()
        self.lock = asyncio.Lock()

    async def cog_unload(self) -> None:
        if self.__update_commands.is_running():
            self.__update_commands.cancel()

    @Cog.listener()
    async def on_command(self, ctx: Context) -> None:
        assert ctx.guild and ctx.command and ctx.bot.user

        log.debug("%s invoked by %s (%s) in %s (%s)", ctx.command, ctx.author, ctx.author.id, ctx.guild, ctx.guild.id)
        data = UpdateOne(
            {"id": ctx.bot.user.id},
            {
                "$inc": {
                    f"command.{ctx.command.qualified_name}": 1,
                }
            },
            upsert=True,
        )
        self.__commands_invoked.append(data)

    @tasks.loop(minutes=1)
    async def __update_commands(self) -> None:
        async with self.lock:
            if self.__commands_invoked:
                lst = self.__commands_invoked.copy()
                log.debug("writing total of %s commands", len(lst))
                await self.collection.bulk_write(lst)
                log.debug("wrote total of %s commands", len(lst))
                self.__commands_invoked = []
