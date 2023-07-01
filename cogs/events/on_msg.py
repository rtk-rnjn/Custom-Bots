"""
MIT License

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

import discord
from discord.ext import tasks
from pymongo import UpdateOne

from core import Bot, Cog

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
            {"channel_id": message.channel.id},
            {
                "$inc": {
                    "message_sent": 1,
                },
                "$addToSet": {
                    "messages": {
                        "message_id": message.id,
                        "message_channel_id": message.channel.id,
                        "message_channel_name": str(message.channel),
                        "message_guild_id": message.guild.id,
                        "message_author_id": message.author.id,
                        "message_author_name": str(message.author),
                        "message_author_avatar": message.author.display_avatar.url,
                        "message_author_bot": message.author.bot,
                        "message_content": message.content,
                        "message_created_at": message.created_at,
                        "message_edited_at": message.edited_at,
                    },
                },
                "$pull": {"messages": {"message_created_at": {"$lt": message.created_at - datetime.timedelta(hours=12)}}},
            },
            upsert=True,
        )

        self.__messages_sent.append(data)

    @Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        assert before.guild and self.bot.user

        if before.author.bot or before.content == after.content:
            return

        data = UpdateOne(
            {"channel_id": after.channel.id, "messages.message_id": before.id},
            {
                "$set": {
                    "messages.$.message_content": after.content,
                    "messages.$.message_edited_at": after.edited_at,
                },
                "$pull": {"messages": {"message_created_at": {"$lt": after.created_at - datetime.timedelta(hours=12)}}},
                "$inc": {
                    "message_edited": 1,
                },
            },
        )

        self.__messages_sent.append(data)

    @Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        assert message.guild and self.bot.user

        if message.author.bot:
            return

        data = UpdateOne(
            {"channel_id": message.channel.id, "messages.message_id": message.id},
            {
                "$pull": {"messages": {"message_id": message.id}},
                "$inc": {
                    "message_deleted": 1,
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
