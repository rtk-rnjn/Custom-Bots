from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord.ext import commands


class Context(commands.Context[commands.Bot]):
    if TYPE_CHECKING:
        from .bot import Bot

    bot: Bot

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.config = self.bot.main_db.configs

    async def send(self, *args, **kwargs) -> None:
        # check if the bot has permission to send messages

        permission = self.channel.permissions_for(self.me)  # type: ignore

        if not (
            permission.send_messages
            and permission.read_messages
            and permission.read_message_history
            and permission.embed_links
        ):
            try:
                await self.author.send(
                    f"Hey! I don't have permission to send messages in {self.channel.mention}.\n"
                    "> Please grant me the required permissions and try again."
                )
            except discord.Forbidden:
                pass

            return

        await super().send(*args, **kwargs)

    async def reply(self, *args, **kwargs):
        await self.send(*args, **kwargs, reference=kwargs.pop("reference", self.message), mention_author=False)
