from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import tasks
from pymongo import UpdateOne

from core import Bot, Cog, Context

log = logging.getLogger("events.on_msg")


class OnMessage(Cog):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.__messages_sent = []
        self.collection = bot.mongo.customBots.messageCollection  # type: ignore
        self.lock = asyncio.Lock()

        self.__update_messages.start()

    async def cog_unload(self):
        if self.__update_messages.is_running():
            self.__update_messages.cancel()

    @Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        assert message.guild and self.bot.user

        if message.author.bot:
            return

        data = UpdateOne(
            {"id": self.bot.user.id},
            {
                "$inc": {
                    "message_count": 1,
                },
                "$addToSet": {
                    "messages": {
                        "message_id": message.id,
                        "message_author_id": message.author.id,
                        "message_author_name": message.author.name,
                        # "message_author_discriminator": message.author.discriminator,
                        "message_author_avatar": message.author.display_avatar.url,
                        "message_author_bot": message.author.bot,
                        "message_content": message.content,
                        "message_created_at": message.created_at,
                    },
                },
            },
            upsert=True,
        )

        self.__messages_sent.append(data)

    @Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        assert before.guild and before.author and self.bot.user

        if before.author.bot or before.content == after.content:
            return

        data = UpdateOne(
            {"id": self.bot.user.id, "messages.message_id": before.id},
            {
                "$set": {
                    "messages.$.message_content": after.content,
                },
            },
        )

        self.__messages_sent.append(data)

    @tasks.loop(minutes=1)
    async def __update_messages(self) -> None:
        async with self.lock:
            if self.__messages_sent:
                lst = self.__messages_sent.copy()
                log.debug("writing total of %s messages", len(lst))
                await self.collection.bulk_write(lst)
                log.debug("wrote total of %s messages", len(lst))
                self.__messages_sent = []
